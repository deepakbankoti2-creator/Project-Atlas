"""
API Endpoints for Project Atlas
Provides public and authenticated routes for:
- Chat & Copilot AI reasoning with pre-retrieval entitlement filtering
- Administrative report ingestion pipeline
- Escalation review queue
- Safe dependency health monitoring
"""

import time
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
import requests

from backend.app.core.config import settings
from backend.app.core.database import get_db, engine
from backend.app.core.auth import verify_admin_key
from backend.app.core.vector_store import vector_store
from backend.app.models.schema import (
    Report, MarketMetric, Client, EscalationTicket, Conversation, Feedback
)
from backend.app.services.ingestion import IngestionService
from backend.app.services.retrieval import rag_service, RetrievalResponse
from backend.app.services.entitlement import entitlement_service, ClientNotFoundError
from backend.app.agent.workflow import agent_workflow, WorkflowOutput
from backend.app.agent.escalation import OFFLINE_TICKETS

logger = logging.getLogger("atlas.endpoints")

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic Request & Response Models
# ---------------------------------------------------------------------------

class CitationResponse(BaseModel):
    report_id: str = Field(..., description="Report identifier, e.g. R-101")
    page: int = Field(..., description="Source document page number")
    quote: str = Field(default="", description="Verbatim supporting quote from passage")
    title: Optional[str] = Field(default="", description="Report title")


class ChatRequest(BaseModel):
    client_id: str = Field(
        ..., min_length=1, max_length=50, description="Client identifier e.g. C-01, C-02"
    )
    question: str = Field(
        ..., min_length=1, max_length=2000, description="User natural language research query"
    )
    top_k: int = Field(5, ge=1, le=20, description="Max passages to retrieve")


# Backward compatibility alias
RAGQueryRequest = ChatRequest


class ChatResponse(BaseModel):
    answer: str = Field(..., description="Cited analysis and executive answer")
    citations: List[CitationResponse] = Field(
        default_factory=list, description="Passages supporting the answer"
    )
    confidence: float = Field(..., description="Fact-check and evidence confidence score (0.0 to 1.0)")
    conflicts: List[Dict[str, Any]] = Field(
        default_factory=list, description="Identified scope or methodological differences"
    )
    derived_values: List[Dict[str, Any]] = Field(
        default_factory=list, description="Calculated projections and formulas"
    )
    escalated: bool = Field(False, description="Whether inquiry was escalated to human analyst")
    escalation_ticket_id: Optional[str] = Field(None, description="Support ticket ID if escalated")
    route: Optional[str] = Field(None, description="Router classification")
    conversation_id: Optional[int] = Field(None, description="Saved conversation ID in database")
    latency_ms: Optional[float] = Field(None, description="Processing latency in milliseconds")


class IngestRequest(BaseModel):
    report_id: Optional[str] = Field(None, description="Optional specific report ID to ingest")
    force_reindex: bool = Field(False, description="Whether to re-extract and re-index existing chunks")


class IngestResponse(BaseModel):
    status: str
    reports_processed: int
    chunks_created: int
    errors: List[str] = []
    duration_sec: float


class EscalationTicketItem(BaseModel):
    ticket_id: str
    client_id: str
    query: str
    reason: str
    status: str
    created_at: str


class DependencyStatus(BaseModel):
    database: str
    chromadb: str
    ollama: str


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    database_target: str
    dependencies: DependencyStatus


class FeedbackRequest(BaseModel):
    conversation_id: int
    client_id: str
    rating: str = Field(..., description="'up' or 'down'")
    comment: Optional[str] = None


# In-memory fallbacks when MySQL is unreachable
OFFLINE_CONVERSATIONS: List[Dict[str, Any]] = []
OFFLINE_FEEDBACK: List[Dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Core Endpoints
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """
    Report service health and safe dependency status (MySQL, ChromaDB, Ollama).
    Does not expose sensitive credentials, passwords, or connection strings.
    """
    # 1. MySQL check
    db_status = "disconnected"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
            db_status = "connected"
    except Exception as e:
        logger.warning("Database health check ping failed: %s", e)
        db_status = "disconnected (fallback catalog active)"

    # 2. ChromaDB check
    chroma_status = "unavailable"
    try:
        stats = vector_store.get_stats()
        total = stats.get("total_chunks", 0)
        chroma_status = f"connected ({total} chunks indexed)"
    except Exception as e:
        logger.warning("ChromaDB health check failed: %s", e)
        chroma_status = "unavailable"

    # 3. Ollama check
    ollama_status = "unavailable"
    try:
        resp = requests.get(
            f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/version",
            timeout=1.5
        )
        if resp.status_code == 200:
            ver = resp.json().get("version", "unknown")
            ollama_status = f"available (version {ver})"
        else:
            ollama_status = "unavailable (deterministic fallback active)"
    except Exception:
        ollama_status = "unavailable (deterministic fallback active)"

    overall_status = "healthy"
    if db_status == "disconnected" and chroma_status == "unavailable":
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        version="1.0.0",
        timestamp=datetime.now(timezone.utc).isoformat() + "Z",
        database_target=settings.DB_NAME,
        dependencies=DependencyStatus(
            database=db_status,
            chromadb=chroma_status,
            ollama=ollama_status
        )
    )


@router.post("/chat", response_model=ChatResponse)
def agent_chat(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    """
    Execute Project Atlas LangGraph agent workflow:
    1. Validates client ID existence in database/catalog.
    2. Enforces pre-retrieval entitlement filtering.
    3. Executes agent routing (SQL, calculator, retrieval, critic, writer).
    4. Persists conversation record with citations and audit data.
    """
    # Reject blank inputs
    cleaned_client = request.client_id.strip()
    cleaned_question = request.question.strip()
    if not cleaned_client or not cleaned_question:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="client_id and question cannot be blank."
        )

    # Validate client exists before continuing
    try:
        entitlement_service.get_client_entitlement(cleaned_client, db=db)
    except ClientNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client '{cleaned_client}' not found. Please provide a registered client ID."
        )

    start_time = time.perf_counter()
    try:
        output: WorkflowOutput = agent_workflow.run(
            client_id=cleaned_client,
            query=cleaned_question
        )
    except Exception as e:
        logger.error("Agent workflow error for client '%s': %s", cleaned_client, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent workflow error: {str(e)}"
        )

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

    # Format citations conforming to schema
    formatted_citations: List[CitationResponse] = []
    for c in output.citations:
        c_dict = c.model_dump() if hasattr(c, "model_dump") else dict(c)
        formatted_citations.append(CitationResponse(
            report_id=c_dict.get("report_id", ""),
            page=c_dict.get("page", c_dict.get("page_number", 1)),
            quote=c_dict.get("quote", ""),
            title=c_dict.get("title", "")
        ))

    # Persist conversation
    citations_data = [c.model_dump() for c in formatted_citations]
    conv_id = None
    try:
        conv_record = Conversation(
            client_id=cleaned_client,
            question=cleaned_question,
            answer=output.answer,
            citations_json=json.dumps(citations_data),
            confidence=str(output.confidence),
            conflicts_json=json.dumps(output.conflicts),
            derived_values_json=json.dumps(output.derived_values),
            escalated=1 if output.escalated else 0,
            escalation_ticket_id=output.escalation_ticket_id,
            route=output.route,
            created_at=datetime.now(timezone.utc)
        )
        db.add(conv_record)
        db.commit()
        db.refresh(conv_record)
        conv_id = conv_record.id
    except Exception as e:
        db.rollback()
        conv_id = len(OFFLINE_CONVERSATIONS) + 1
        OFFLINE_CONVERSATIONS.append({
            "id": conv_id,
            "client_id": cleaned_client,
            "question": cleaned_question,
            "answer": output.answer,
            "citations": citations_data,
            "confidence": output.confidence,
            "conflicts": output.conflicts,
            "derived_values": output.derived_values,
            "escalated": output.escalated,
            "escalation_ticket_id": output.escalation_ticket_id,
            "route": output.route,
            "created_at": str(datetime.now(timezone.utc))
        })

    return ChatResponse(
        answer=output.answer,
        citations=formatted_citations,
        confidence=output.confidence,
        conflicts=output.conflicts,
        derived_values=output.derived_values,
        escalated=output.escalated,
        escalation_ticket_id=output.escalation_ticket_id,
        route=output.route,
        conversation_id=conv_id,
        latency_ms=elapsed_ms
    )


@router.post("/ingest", response_model=IngestResponse)
def trigger_ingestion(
    request: IngestRequest = IngestRequest(),
    admin_token: str = Depends(verify_admin_key)
) -> IngestResponse:
    """
    Trigger PDF report ingestion pipeline.
    Requires administrative API key authentication ('X-API-Key' or 'Authorization: Bearer <token>').
    """
    logger.info("Admin triggered ingestion (target: %s, force_reindex: %s)", request.report_id, request.force_reindex)
    service = IngestionService(vector_store_instance=vector_store)
    targets = [request.report_id] if request.report_id else None
    summary = service.ingest_all(target_report_ids=targets, force_reindex=request.force_reindex)
    
    return IngestResponse(
        status=summary.get("status", "completed"),
        reports_processed=summary.get("reports_processed", 0),
        chunks_created=summary.get("chunks_created", 0),
        errors=summary.get("errors", []),
        duration_sec=summary.get("duration_sec", 0.0)
    )


@router.get("/escalations", response_model=List[EscalationTicketItem])
def list_escalations(
    db: Session = Depends(get_db),
    admin_token: str = Depends(verify_admin_key)
) -> List[EscalationTicketItem]:
    """
    Retrieve analyst review escalation tickets.
    Requires administrative API key authentication.
    """
    results: List[EscalationTicketItem] = []
    try:
        tickets = db.query(EscalationTicket).order_by(EscalationTicket.id.desc()).all()
        for t in tickets:
            results.append(EscalationTicketItem(
                ticket_id=f"ESC-{t.id:04d}",
                client_id=t.client_id,
                query=t.query,
                reason=t.reason,
                status=t.status,
                created_at=str(t.created_at)
            ))
        return results
    except Exception as e:
        logger.warning("Database unavailable for escalations query (%s). Returning in-memory tickets.", e)
        for t in OFFLINE_TICKETS.values():
            results.append(EscalationTicketItem(
                ticket_id=t["ticket_id"],
                client_id=t["client_id"],
                query=t["query"],
                reason=t["reason"],
                status=t["status"],
                created_at=t["created_at"]
            ))
        return results


# ---------------------------------------------------------------------------
# Supporting Portal & Inspection Endpoints
# ---------------------------------------------------------------------------

@router.get("/db-status")
def get_db_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Inspect database connection and existing tables."""
    try:
        active_db = db.execute(text("SELECT DATABASE();")).scalar()
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        table_counts = {}
        for tbl in tables:
            cnt = db.execute(text(f"SELECT COUNT(*) FROM `{tbl}`;")).scalar()
            table_counts[tbl] = cnt

        return {
            "status": "connected",
            "database": active_db,
            "tables": tables,
            "row_counts": table_counts
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")


@router.get("/reports")
def list_reports(db: Session = Depends(get_db)):
    """List existing intelligence reports."""
    reports = db.query(Report).all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "publisher": r.publisher,
            "published": str(r.published),
            "sector": r.sector,
            "access": r.access
        }
        for r in reports
    ]


@router.get("/reports/{report_id}/metrics")
def list_report_metrics(report_id: str, db: Session = Depends(get_db)):
    """List market metrics for a specific report."""
    metrics = db.query(MarketMetric).filter(MarketMetric.report_id == report_id).all()
    return [
        {
            "id": m.id,
            "report_id": m.report_id,
            "metric": m.metric,
            "region": m.region,
            "period": m.period,
            "value": m.value,
            "scope_note": m.scope_note
        }
        for m in metrics
    ]


@router.get("/clients")
def list_clients(db: Session = Depends(get_db)):
    """List clients and their purchased reports."""
    clients = db.query(Client).all()
    return [
        {
            "id": c.id,
            "company": c.company,
            "contact_email": c.contact_email,
            "purchased_reports": c.purchased_reports
        }
        for c in clients
    ]


@router.get("/vector-status")
def get_vector_status():
    """Retrieve ChromaDB collection metrics and indexed reports."""
    return vector_store.get_stats()


@router.post("/retrieve", response_model=RetrievalResponse)
def secure_retrieve(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Execute entitlement-enforced retrieval.
    Pre-filters ChromaDB by client access before any text is returned.
    """
    try:
        return rag_service.retrieve(
            client_id=request.client_id,
            query=request.question,
            top_k=request.top_k,
            db=db
        )
    except ClientNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval error: {str(e)}")


@router.post("/feedback")
def submit_feedback(request: FeedbackRequest, db: Session = Depends(get_db)):
    """Store thumbs-up or thumbs-down feedback for a conversation."""
    if request.rating not in ("up", "down"):
        raise HTTPException(status_code=400, detail="Rating must be 'up' or 'down'.")

    try:
        fb_record = Feedback(
            conversation_id=request.conversation_id,
            client_id=request.client_id,
            rating=request.rating,
            comment=request.comment,
            created_at=datetime.now(timezone.utc)
        )
        db.add(fb_record)
        db.commit()
        db.refresh(fb_record)
        return {"status": "success", "feedback_id": fb_record.id, "rating": fb_record.rating}
    except Exception:
        db.rollback()
        fb_id = len(OFFLINE_FEEDBACK) + 1
        OFFLINE_FEEDBACK.append({
            "id": fb_id,
            "conversation_id": request.conversation_id,
            "client_id": request.client_id,
            "rating": request.rating,
            "comment": request.comment,
            "created_at": str(datetime.now(timezone.utc))
        })
        return {"status": "success", "feedback_id": fb_id, "rating": request.rating, "storage": "in-memory"}


@router.get("/conversations")
def list_conversations(client_id: Optional[str] = None, db: Session = Depends(get_db)):
    """Retrieve history of conversations, optionally filtered by client_id."""
    try:
        query = db.query(Conversation)
        if client_id:
            query = query.filter(Conversation.client_id == client_id)
        records = query.order_by(Conversation.id.desc()).limit(50).all()
        return [
            {
                "id": r.id,
                "client_id": r.client_id,
                "question": r.question,
                "answer": r.answer,
                "confidence": r.confidence,
                "escalated": bool(r.escalated),
                "escalation_ticket_id": r.escalation_ticket_id,
                "route": r.route,
                "created_at": str(r.created_at)
            }
            for r in records
        ]
    except Exception:
        if client_id:
            return [c for c in OFFLINE_CONVERSATIONS if c["client_id"] == client_id]
        return OFFLINE_CONVERSATIONS
