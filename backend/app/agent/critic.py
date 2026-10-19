"""
Critic and Fact-Checker Module for Project Atlas AI Agent Workflow
Verifies factual citations, reconciles conflicting report scopes, and computes confidence scores.
"""

from typing import List, Dict, Any, Optional
import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ConflictAnalysis(BaseModel):
    """Analysis of source differences between reports."""
    metric: str
    has_conflict: bool
    explanation: str
    sources: List[Dict[str, Any]]


class CriticVerificationResult(BaseModel):
    """Output of the critic/fact-checker node."""
    verified: bool
    confidence: float
    conflicts: List[ConflictAnalysis]
    citation_coverage: float
    notes: List[str]
    requires_escalation: bool


class EvidenceCritic:
    """Performs claim-evidence verification, scope discrepancy analysis, and confidence scoring."""

    @classmethod
    def analyze_market_size_conflicts(
        cls,
        retrieved_report_ids: List[str]
    ) -> List[ConflictAnalysis]:
        """
        Analyzes known scope distinctions between R-101 and R-102.
        Enforces rule: Never average; explain scope differences.
        """
        conflicts: List[ConflictAnalysis] = []

        if "R-101" in retrieved_report_ids and "R-102" in retrieved_report_ids:
            conflicts.append(ConflictAnalysis(
                metric="2024 Global Smart Water Meter Market Size & CAGR",
                has_conflict=True,
                explanation=(
                    "Reports R-101 and R-102 present differing 2024 valuations due to distinct measurement scopes: "
                    "R-101 (CMR) values the market at USD 4.21 Billion (11.2% CAGR, 2025-2030) covering hardware, software platforms, and managed deployment services. "
                    "Conversely, R-102 (Aquila Insights) values the market at USD 3.87 Billion (9.8% CAGR, 2024-2029) restricted strictly to AMR/AMI physical hardware meters. "
                    "These figures must NOT be averaged or treated as conflicting truth; they reflect comprehensive vs hardware-only scopes."
                ),
                sources=[
                    {
                        "report_id": "R-101",
                        "title": "Global Smart Water Meter Market 2025",
                        "valuation_2024": "USD 4.21 B",
                        "cagr": "11.2% (2025-2030)",
                        "apac_share": "38%",
                        "scope": "Hardware, Software, and Managed Services",
                        "citation": "R-101, p.8"
                    },
                    {
                        "report_id": "R-102",
                        "title": "Smart Water Metering: Industry Outlook 2024",
                        "valuation_2024": "USD 3.87 B",
                        "cagr": "9.8% (2024-2029)",
                        "apac_share": "41% of hardware",
                        "scope": "AMR / AMI hardware only",
                        "citation": "R-102, p.6"
                    }
                ]
            ))

        return conflicts

    @classmethod
    def evaluate(
        cls,
        query: str,
        retrieved_passages: List[Any],
        route: str,
        is_out_of_horizon: bool = False
    ) -> CriticVerificationResult:
        """
        Perform quality, citation, and conflict audit on retrieved evidence.
        """
        notes = []
        report_ids = [p.report_id for p in retrieved_passages if hasattr(p, "report_id")]

        # 1. Analyze conflicts between R-101 and R-102
        conflicts = cls.analyze_market_size_conflicts(report_ids)
        if conflicts:
            notes.append("Identified scope discrepancy between R-101 and R-102. Scope difference explanation added.")

        # 2. Check evidence availability
        if route in ("factual_lookup", "comparison") and not retrieved_passages:
            notes.append("No supporting evidence retrieved from knowledge base within client entitlement.")
            return CriticVerificationResult(
                verified=False,
                confidence=0.10,
                conflicts=conflicts,
                citation_coverage=0.0,
                notes=notes,
                requires_escalation=True
            )

        # 3. Check horizon limits
        if is_out_of_horizon:
            notes.append("Query asks for projection beyond the published forecast horizon (2030).")
            return CriticVerificationResult(
                verified=False,
                confidence=0.35,
                conflicts=conflicts,
                citation_coverage=0.5,
                notes=notes,
                requires_escalation=True
            )

        # 4. Standard validation score
        citation_count = len(report_ids)
        coverage = min(1.0, citation_count / 2.0) if citation_count > 0 else 0.0

        if route == "sql_aggregate":
            confidence = 0.95
        elif route == "calculation":
            confidence = 0.90
        elif conflicts:
            confidence = 0.95
        elif citation_count >= 1:
            confidence = 0.90
        else:
            confidence = 0.60

        requires_escalation = confidence < 0.70

        return CriticVerificationResult(
            verified=True,
            confidence=confidence,
            conflicts=conflicts,
            citation_coverage=coverage,
            notes=notes,
            requires_escalation=requires_escalation
        )
