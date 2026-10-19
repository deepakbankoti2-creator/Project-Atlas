"""
Query Router for Project Atlas AI Agent Workflow
Classifies user questions into distinct operational categories.
"""

from typing import Tuple, List
import re
import logging
from backend.app.services.security import SecurityGuard

logger = logging.getLogger(__name__)

# Out of scope domain patterns (politics, sports, entertainment, general world trivia)
OUT_OF_SCOPE_PATTERNS = [
    r"who\s+will\s+win\s+(the\s+)?(election|presidency|match|cup)",
    r"election",
    r"president",
    r"prime\s+minister",
    r"politics?",
    r"football|cricket|nba|super\s*bowl",
    r"recipe|how\s+to\s+cook",
    r"capital\s+of\s+[a-z]+",
    r"tell\s+me\s+a\s+joke"
]

# SQL Aggregate indicators
SQL_AGGREGATE_PATTERNS = [
    r"which\s+sector\s+has\s+the\s+most\s+reports",
    r"how\s+many\s+reports",
    r"count\s+(of\s+)?reports",
    r"most\s+reports\s+in\s+your\s+library",
    r"total\s+number\s+of\s+reports",
    r"reports\s+per\s+sector",
    r"publisher\s+with\s+the\s+most"
]

# Calculation / Projection indicators
CALCULATION_PATTERNS = [
    r"what\s+will\s+the\s+.*market\s+be\s+worth\s+in\s+20\d\d",
    r"projected\s+value\s+in\s+20\d\d",
    r"cagr\s+projection",
    r"calculate",
    r"growth\s+rate\s+projection",
    r"worth\s+in\s+2030",
    r"worth\s+in\s+2035",
    r"market\s+in\s+20\d\d"
]

# Comparison indicators
COMPARISON_PATTERNS = [
    r"compare\s+r-?\d+\s+and\s+r-?\d+",
    r"which\s+report\s+should\s+i\s+trust",
    r"difference\s+between\s+r-?\d+\s+and\s+r-?\d+",
    r"conflicting\s+sources",
    r"discrepanc(y|ies)",
    r"compare\s+reports"
]


class QueryRouter:
    """Classifies user queries to route them to the appropriate agent workflow branch."""

    @staticmethod
    def classify(query: str) -> Tuple[str, float]:
        """
        Classify the query into:
        - 'unsafe': Prompt injection, destructive actions, confidential data requests.
        - 'out_of_scope': Politics, non-market trivia, unrelated subjects.
        - 'sql_aggregate': Aggregations, counts, and statistical inquiries across catalog tables.
        - 'calculation': Numeric projections, CAGR estimates, future valuation calculations.
        - 'comparison': Trust questions, conflicting sources, cross-report comparisons.
        - 'factual_lookup': Standard retrieval and market fact queries.

        Returns:
            Tuple[route: str, confidence: float]
        """
        q = query.strip()
        q_lower = q.lower()

        # 1. Unsafe detection (security guardrails always take highest priority)
        is_injection, _ = SecurityGuard.detect_injection(q)
        if is_injection:
            logger.info("[ROUTER] Classified as 'unsafe' due to prompt injection signatures.")
            return "unsafe", 1.0

        if re.search(r"\b(delete|drop|truncate|alter|insert|update)\b.*\b(table|row|database|from)\b", q_lower):
            logger.info("[ROUTER] Classified as 'unsafe' due to destructive SQL intent.")
            return "unsafe", 1.0

        # 2. Out of scope detection
        for pattern in OUT_OF_SCOPE_PATTERNS:
            if re.search(pattern, q_lower):
                logger.info("[ROUTER] Classified as 'out_of_scope'.")
                return "out_of_scope", 0.95

        # 3. SQL Aggregate detection
        for pattern in SQL_AGGREGATE_PATTERNS:
            if re.search(pattern, q_lower):
                logger.info("[ROUTER] Classified as 'sql_aggregate'.")
                return "sql_aggregate", 0.95

        # 4. Calculation detection
        for pattern in CALCULATION_PATTERNS:
            if re.search(pattern, q_lower):
                logger.info("[ROUTER] Classified as 'calculation'.")
                return "calculation", 0.90

        # 5. Comparison detection
        for pattern in COMPARISON_PATTERNS:
            if re.search(pattern, q_lower):
                logger.info("[ROUTER] Classified as 'comparison'.")
                return "comparison", 0.90

        # 6. Default to factual lookup
        logger.info("[ROUTER] Classified as 'factual_lookup'.")
        return "factual_lookup", 0.85
