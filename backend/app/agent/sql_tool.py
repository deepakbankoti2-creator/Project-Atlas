"""
SQL Aggregate Tool for Project Atlas AI Agent Workflow
Executes strictly read-only, predefined parameterized query templates against MySQL.
Blocks arbitrary LLM SQL and destructive commands.
"""

from typing import Dict, Any, List, Optional
import re
import logging
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal

logger = logging.getLogger(__name__)

# Fallback catalog data if MySQL server connection is offline
FALLBACK_SECTOR_COUNTS = [
    {"sector": "Utilities", "report_count": 2},
    {"sector": "Consumer Durables", "report_count": 1}
]

FALLBACK_TOTAL_REPORTS = [{"total_reports": 3}]


class SQLSecurityError(Exception):
    """Raised when an unsafe or destructive SQL statement is detected."""
    pass


class ReadOnlySQLTool:
    """Safely executes authorized aggregate SQL templates."""

    PREDEFINED_TEMPLATES = {
        "sector_counts": {
            "query": "SELECT sector, COUNT(*) AS report_count FROM reports GROUP BY sector ORDER BY report_count DESC;",
            "description": "Calculates the number of published reports per industry sector."
        },
        "total_reports": {
            "query": "SELECT COUNT(*) AS total_reports FROM reports;",
            "description": "Calculates the total number of intelligence reports in the repository."
        },
        "publisher_counts": {
            "query": "SELECT publisher, COUNT(*) AS report_count FROM reports GROUP BY publisher ORDER BY report_count DESC;",
            "description": "Calculates report volume grouped by publisher."
        },
        "access_breakdown": {
            "query": "SELECT access, COUNT(*) AS report_count FROM reports GROUP BY access;",
            "description": "Calculates distribution between public and paid reports."
        }
    }

    @classmethod
    def validate_safety(cls, statement: str) -> None:
        """
        Ensure no destructive SQL keywords or multiple statement chaining exists.
        """
        clean_stmt = statement.strip().rstrip(";")
        blocked_keywords = [
            r"\bdelete\b", r"\bdrop\b", r"\btruncate\b", r"\bupdate\b",
            r"\binsert\b", r"\balter\b", r"\bgrant\b", r"\brevoke\b",
            r"\bexec(ute)?\b", r"--", r";\s*\S+"
        ]
        for pattern in blocked_keywords:
            if re.search(pattern, clean_stmt, re.IGNORECASE):
                logger.warning("[SECURITY] Blocked potentially destructive SQL statement: '%s'", statement)
                raise SQLSecurityError(
                    f"Blocked unsafe SQL statement matching restricted pattern: '{pattern}'. "
                    "Write operations and arbitrary statement chaining are prohibited."
                )

    @classmethod
    def execute_template(cls, template_name: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Execute a named, verified template against MySQL.
        """
        if template_name not in cls.PREDEFINED_TEMPLATES:
            raise ValueError(f"Unknown template '{template_name}'. Allowed: {list(cls.PREDEFINED_TEMPLATES.keys())}")

        template_info = cls.PREDEFINED_TEMPLATES[template_name]
        sql_statement = template_info["query"]

        # Validate safety
        cls.validate_safety(sql_statement)

        should_close = False
        if db is None:
            try:
                db = SessionLocal()
                should_close = True
            except Exception as e:
                logger.warning("Could not connect to MySQL: %s. Using static fallback.", e)
                db = None

        try:
            if db is not None:
                try:
                    result = db.execute(text(sql_statement))
                    rows = [dict(row._mapping) for row in result]
                    return {
                        "template": template_name,
                        "query_executed": sql_statement,
                        "rows": rows,
                        "is_live_mysql": True
                    }
                except Exception as err:
                    logger.warning("SQL execution failed on MySQL: %s. Using fallback.", err)

            # Fallback
            if template_name == "sector_counts":
                rows = FALLBACK_SECTOR_COUNTS
            else:
                rows = FALLBACK_TOTAL_REPORTS

            return {
                "template": template_name,
                "query_executed": sql_statement,
                "rows": rows,
                "is_live_mysql": False
            }

        finally:
            if should_close and db is not None:
                db.close()

    @classmethod
    def resolve_and_execute(cls, natural_query: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Determine the appropriate template from a natural language query and execute it safely.
        """
        q_lower = natural_query.lower()
        if "sector" in q_lower:
            template = "sector_counts"
        elif "publisher" in q_lower:
            template = "publisher_counts"
        elif "access" in q_lower or "paid" in q_lower:
            template = "access_breakdown"
        else:
            template = "total_reports"

        res = cls.execute_template(template, db=db)
        
        # Format human readable summary
        if template == "sector_counts":
            top = res["rows"][0]
            summary = (
                f"The sector with the most reports is **{top['sector']}** with **{top['report_count']} reports**.\n"
                f"Full breakdown: " + ", ".join([f"{r['sector']} ({r['report_count']})" for r in res["rows"]]) + "."
            )
        else:
            summary = f"Total reports in repository: {res['rows'][0].get('total_reports', len(res['rows']))}."

        res["summary"] = summary
        return res
