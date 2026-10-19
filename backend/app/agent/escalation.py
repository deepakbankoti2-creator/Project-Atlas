"""
Escalation Service for Project Atlas AI Agent Workflow
Creates support tickets in MySQL when confidence is low or questions require human analyst review.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging
from sqlalchemy.orm import Session
from sqlalchemy import inspect
from backend.app.core.database import SessionLocal, engine, Base
from backend.app.models.schema import EscalationTicket

logger = logging.getLogger(__name__)

# In-memory ticket registry for offline fallback
OFFLINE_TICKETS: Dict[int, Dict[str, Any]] = {}
_ticket_counter = 1000


class EscalationService:
    """Creates and manages human-analyst escalation tickets."""

    @classmethod
    def ensure_table_exists(cls) -> None:
        """
        Idempotently create the escalations table if it does not already exist.
        Leaves existing reports, market_metrics, and clients tables completely untouched.
        """
        try:
            inspector = inspect(engine)
            if "escalations" not in inspector.get_table_names():
                logger.info("Creating missing 'escalations' table in MySQL...")
                Base.metadata.create_all(bind=engine, tables=[EscalationTicket.__table__], checkfirst=True)
                logger.info("Successfully created 'escalations' table.")
        except Exception as e:
            logger.debug("Could not verify/create escalations table in MySQL: %s", e)

    @classmethod
    def create_ticket(
        cls,
        client_id: str,
        query: str,
        reason: str,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Persist an escalation ticket in MySQL or in-memory fallback.
        """
        global _ticket_counter
        cls.ensure_table_exists()

        should_close = False
        if db is None:
            try:
                db = SessionLocal()
                should_close = True
            except Exception as conn_err:
                logger.warning("Could not open DB session for escalation: %s. Using fallback.", conn_err)
                db = None

        try:
            if db is not None:
                try:
                    ticket = EscalationTicket(
                        client_id=client_id,
                        query=query,
                        reason=reason,
                        status="open",
                        created_at=datetime.now(timezone.utc)
                    )
                    db.add(ticket)
                    db.commit()
                    db.refresh(ticket)
                    ticket_id = f"ESC-{ticket.id:04d}"
                    logger.info("Created escalation ticket %s in MySQL for client '%s'", ticket_id, client_id)
                    return {
                        "ticket_id": ticket_id,
                        "client_id": client_id,
                        "reason": reason,
                        "status": "open",
                        "created_at": str(ticket.created_at),
                        "is_live_mysql": True
                    }
                except Exception as save_err:
                    db.rollback()
                    logger.warning("Failed saving ticket to MySQL: %s. Falling back to memory.", save_err)

            # In-memory fallback
            _ticket_counter += 1
            ticket_id = f"ESC-{_ticket_counter:04d}"
            now_str = datetime.now(timezone.utc).isoformat()
            record = {
                "ticket_id": ticket_id,
                "client_id": client_id,
                "query": query,
                "reason": reason,
                "status": "open",
                "created_at": now_str,
                "is_live_mysql": False
            }
            OFFLINE_TICKETS[_ticket_counter] = record
            logger.info("Created in-memory escalation ticket %s for client '%s'", ticket_id, client_id)
            return record

        finally:
            if should_close and db is not None:
                db.close()
