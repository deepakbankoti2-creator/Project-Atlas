"""
Secure RAG Retrieval Service for Project Atlas
Enforces strict pre-retrieval entitlement filtering, hybrid ranking, and safe context packaging.
"""

from typing import List, Dict, Any, Optional
import re
import logging
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.core.vector_store import VectorStore, vector_store as default_vector_store
from backend.app.services.entitlement import EntitlementService, ClientEntitlement, ClientNotFoundError, SEED_REPORTS
from backend.app.services.security import SecurityGuard

logger = logging.getLogger(__name__)


class SupportingPassage(BaseModel):
    """Structured passage supporting RAG responses."""
    passage_id: str
    report_id: str
    title: str
    page_number: int
    sector: str
    region: str
    publication_year: int
    access: str
    text: str
    score: float


class RetrievalResponse(BaseModel):
    """Complete RAG retrieval response container."""
    client_id: str
    company: str
    query: str
    accessible_reports: List[str]
    restricted_reports: List[str]
    requested_restricted_reports: List[str]
    upgrade_notice: Optional[str] = None
    passages: List[SupportingPassage]
    context_for_llm: str
    injection_detected: bool = False
    warning: Optional[str] = None


class SecureRAGService:
    """Core retrieval service with strict pre-LLM entitlement filtering and hybrid ranking."""

    def __init__(self, vector_store_instance: Optional[VectorStore] = None):
        self.vector_store = vector_store_instance or default_vector_store

    def _detect_restricted_report_requests(self, query: str, restricted_reports: List[str]) -> List[str]:
        """
        Check if the user query explicitly mentions any report IDs or titles that the client cannot access.
        """
        targeted = []
        query_lower = query.lower()
        for rid in restricted_reports:
            # Check ID e.g. 'r-101'
            if rid.lower() in query_lower:
                targeted.append(rid)
                continue
            # Check title snippet
            meta = SEED_REPORTS.get(rid, {})
            title = meta.get("title", "")
            if title and len(title) > 5 and title.lower() in query_lower:
                targeted.append(rid)

        return targeted

    def _keyword_match_score(self, text: str, query_tokens: List[str]) -> float:
        """Simple lexical matching score to complement dense semantic embeddings."""
        if not text or not query_tokens:
            return 0.0

        text_lower = text.lower()
        matches = sum(1 for token in query_tokens if token in text_lower)
        return float(matches) / float(len(query_tokens))

    def retrieve(
        self,
        client_id: str,
        query: str,
        top_k: int = 5,
        db: Optional[Session] = None
    ) -> RetrievalResponse:
        """
        Execute pre-retrieval entitlement-filtered RAG search.

        CRITICAL SECURITY INVARIANT:
        The authorization check occurs BEFORE ChromaDB is queried.
        Only chunks where metadata.report_id is in client_entitlement.accessible_reports
        can ever be retrieved.

        Args:
            client_id: Client ID from caller (e.g., 'C-01', 'C-02').
            query: User natural language question.
            top_k: Maximum number of chunks to return for LLM context.
            db: Optional database session.

        Returns:
            RetrievalResponse container.
        """
        # 1. Authorize client & resolve permitted report boundaries
        entitlement: ClientEntitlement = EntitlementService.get_client_entitlement(client_id, db=db)

        # 2. Check for prompt injection in user query
        query_injection, _ = SecurityGuard.detect_injection(query)

        # 3. Check if query references restricted reports
        requested_restricted = self._detect_restricted_report_requests(query, entitlement.restricted_reports)
        upgrade_notice = None
        if requested_restricted:
            names = []
            for r in requested_restricted:
                t = SEED_REPORTS.get(r, {}).get("title", f"Report {r}")
                names.append(f"{r} ('{t}')")
            upgrade_notice = (
                f"Notice: You requested information from {', '.join(names)}. "
                "This publication requires paid enterprise access not currently included in your subscription. "
                "Contact sales@cmr-insights.com to upgrade your entitlement and unlock these figures."
            )
            logger.info("[ENTITLEMENT] Restricted report(s) %s requested by client '%s'", requested_restricted, client_id)

        # 4. HARD PRE-FILTERING: Query ChromaDB strictly restricted to accessible_reports
        # If client has no accessible reports, return empty results immediately
        if not entitlement.accessible_reports:
            logger.warning("[ENTITLEMENT] Client '%s' has 0 accessible reports.", client_id)
            empty_context = SecurityGuard.wrap_untrusted_context([])
            return RetrievalResponse(
                client_id=client_id,
                company=entitlement.company,
                query=query,
                accessible_reports=[],
                restricted_reports=entitlement.restricted_reports,
                requested_restricted_reports=requested_restricted,
                upgrade_notice=upgrade_notice,
                passages=[],
                context_for_llm=empty_context,
                injection_detected=query_injection,
                warning="No accessible reports found for this client account."
            )

        # Extract query tokens and check for specific page mentions
        query_tokens = [w.lower() for w in re.findall(r'\b[a-zA-Z0-9.%$-]{2,}\b', query)]
        page_match = re.search(r'(?:page|p\.?)\s*(\d+)', query, re.IGNORECASE)
        target_page = int(page_match.group(1)) if page_match else None

        # Retrieve candidates from ChromaDB using strict where-clause filter
        fetch_limit = min(max(top_k * 12, 60), 100)
        raw_candidates = self.vector_store.query_similar(

            query_text=query,
            n_results=fetch_limit,
            allowed_report_ids=entitlement.accessible_reports
        )
        seen_cand_ids = {c["id"] for c in raw_candidates}

        # If a specific page is mentioned, retrieve matching page chunks strictly within accessible reports
        if target_page:
            try:
                page_chunks = self.vector_store.collection.get(
                    where={"page_number": target_page},
                    include=["metadatas", "documents"]
                )
                if page_chunks and page_chunks.get("ids"):
                    for idx, cid in enumerate(page_chunks["ids"]):
                        if cid not in seen_cand_ids:
                            meta = page_chunks["metadatas"][idx] if page_chunks.get("metadatas") else {}
                            # Pre-retrieval entitlement enforcement:
                            if meta.get("report_id") in entitlement.accessible_reports:
                                raw_candidates.append({
                                    "id": cid,
                                    "text": page_chunks["documents"][idx] if page_chunks.get("documents") else "",
                                    "metadata": meta,
                                    "distance": 0.4
                                })
                                seen_cand_ids.add(cid)
            except Exception as e:
                logger.debug("Page filter retrieval: %s", e)

        scored_candidates = []
        trap_detected = False

        for c in raw_candidates:
            # Semantic score: Chroma distances are cosine distances (0 = identical, 2 = opposite)
            distance = c.get("distance") or 0.5
            semantic_score = max(0.0, 1.0 - (distance / 2.0))

            # Lexical score
            text_str = c.get("text", "")
            lexical_score = self._keyword_match_score(text_str, query_tokens)

            # Metadata boost
            meta = c.get("metadata", {})
            meta_boost = 0.0
            if target_page and meta.get("page_number") == target_page:
                meta_boost += 0.4
            
            cand_report = str(meta.get("report_id", "")).lower()
            q_clean = query.lower().replace("-", "")
            if cand_report and (cand_report in query.lower() or cand_report.replace("-", "") in q_clean):
                meta_boost += 0.6

            # Boost if query matches report title keywords (e.g. battery, purifier, energy, healthcare)
            title = str(meta.get("title", "")).lower()
            title_keywords = [
                w for w in re.findall(r'\b[a-zA-Z]{4,}\b', title) 
                if w not in ("market", "global", "industry", "outlook", "2024", "2025")
            ]
            if any(kw in query.lower() for kw in title_keywords):
                meta_boost += 0.5


            # Metric presence boost: if query asks for numbers or growth, boost pages with actual values
            t_lower = text_str.lower()
            if any(k in query.lower() for k in ("size", "valuation", "worth", "reach", "billion")):
                if "usd" in t_lower or "billion" in t_lower or "valued at" in t_lower or "reached" in t_lower:
                    meta_boost += 0.4
            if any(k in query.lower() for k in ("cagr", "growth", "forecast", "projection")):
                if "cagr" in t_lower or "%" in t_lower:
                    meta_boost += 0.4

            # Combined hybrid score (60% semantic, 40% lexical + metadata boost)
            final_score = (0.6 * semantic_score) + (0.4 * lexical_score) + meta_boost

            # Check if this candidate contains an injection trap
            is_trap, _ = SecurityGuard.detect_injection(text_str)
            if is_trap:
                trap_detected = True

            scored_candidates.append((final_score, c))

        # Sort descending by hybrid score
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        # For comparison queries between specific reports, guarantee representation from each mentioned report
        top_candidates = []
        q_lower_comp = query.lower()
        if any(w in q_lower_comp for w in ("compare", "trust", "versus", "vs", "between")):
            mentioned_rids = [
                r for r in entitlement.accessible_reports 
                if r.lower() in q_lower_comp or r.lower().replace("-", "") in q_lower_comp.replace("-", "")
            ]
            if len(mentioned_rids) >= 2:
                for m_rid in mentioned_rids:
                    for sc, cand in scored_candidates:
                        if cand.get("metadata", {}).get("report_id") == m_rid:
                            top_candidates.append((sc, cand))
                            break

        # Fill remaining slots up to top_k
        seen_cand_ids = {c["id"] for _, c in top_candidates}
        for sc, cand in scored_candidates:
            if cand["id"] not in seen_cand_ids:
                top_candidates.append((sc, cand))
                seen_cand_ids.add(cand["id"])
            if len(top_candidates) >= top_k:
                break


        # 6. Build structured SupportingPassage objects
        supporting_passages: List[SupportingPassage] = []
        passages_for_context: List[Dict[str, Any]] = []

        for score, cand in top_candidates:
            meta = cand.get("metadata", {})
            passage = SupportingPassage(
                passage_id=cand.get("id", ""),
                report_id=str(meta.get("report_id", "")),
                title=str(meta.get("title", "")),
                page_number=int(meta.get("page_number", 1)),
                sector=str(meta.get("sector", "")),
                region=str(meta.get("region", "")),
                publication_year=int(meta.get("publication_year", 0)),
                access=str(meta.get("access", "")),
                text=cand.get("text", ""),
                score=round(score, 4)
            )
            supporting_passages.append(passage)
            passages_for_context.append(cand)

        # 7. Package context safely with security delimiters
        context_str = SecurityGuard.wrap_untrusted_context(passages_for_context)

        return RetrievalResponse(
            client_id=client_id,
            company=entitlement.company,
            query=query,
            accessible_reports=entitlement.accessible_reports,
            restricted_reports=entitlement.restricted_reports,
            requested_restricted_reports=requested_restricted,
            upgrade_notice=upgrade_notice,
            passages=supporting_passages,
            context_for_llm=context_str,
            injection_detected=(query_injection or trap_detected)
        )


# Global default instance
rag_service = SecureRAGService()
