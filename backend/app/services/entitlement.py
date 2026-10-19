"""
Entitlement and Authorization Service for Project Atlas
Enforces client access control by resolving purchased and public reports before retrieval.
"""

from typing import List, Dict, Any, Optional
import logging
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal
from backend.app.models.schema import Client, Report, ReportAccessEnum

logger = logging.getLogger(__name__)


class ClientNotFoundError(Exception):
    """Raised when client ID is not found in database or catalog."""
    pass


class ClientEntitlement(BaseModel):
    """Client profile and access boundaries."""
    client_id: str
    company: str
    contact_email: str
    purchased_reports: List[str]
    accessible_reports: List[str]  # purchased_reports + public reports
    restricted_reports: List[str]  # known paid reports that the client has NOT purchased


# Fallback catalog matching MySQL seed data for offline resilience & testing
SEED_CLIENTS: Dict[str, Dict[str, Any]] = {
    "C-01": {
        "company": "Northwind Utilities",
        "contact_email": "ops@example.com",
        "purchased_reports": ["R-101", "R-103", "R-104", "R-106"]
    },
    "C-02": {
        "company": "Blue Delta Infra",
        "contact_email": "procurement@example.com",
        "purchased_reports": ["R-103", "R-106"]
    }
}

SEED_REPORTS: Dict[str, Dict[str, Any]] = {
    "R-101": {"title": "Global Smart Water Meter Market 2025", "access": "paid"},
    "R-102": {"title": "Smart Water Metering: Industry Outlook 2024", "access": "public"},
    "R-103": {"title": "Residential Water Purifier Market", "access": "paid"},
    "R-104": {"title": "EV Battery Recycling Market 2025", "access": "paid"},
    "R-105": {"title": "Commercial Building Energy Management Systems Market 2024", "access": "public"},
    "R-106": {"title": "Healthcare Generative AI Market 2025", "access": "paid"}
}



class EntitlementService:
    """Service to validate client identity and compute allowed report IDs."""

    @staticmethod
    def get_client_entitlement(client_id: str, db: Optional[Session] = None) -> ClientEntitlement:
        """
        Validate client ID and resolve accessible vs restricted report IDs.

        Authorization Rule:
        1. Client must exist in database / catalog.
        2. Accessible reports = reports in client's purchased list + all 'public' reports.
        3. Restricted reports = all catalog 'paid' reports that are NOT in purchased list.

        Args:
            client_id: Unique client identifier (e.g., 'C-01', 'C-02').
            db: Optional active SQLAlchemy session.

        Returns:
            ClientEntitlement model.

        Raises:
            ClientNotFoundError: If client is not recognized.
        """
        client_id_clean = client_id.strip()
        should_close = False

        if db is None:
            try:
                db = SessionLocal()
                should_close = True
            except Exception as conn_err:
                logger.warning("Could not establish MySQL connection: %s. Using seed catalog.", conn_err)
                db = None

        try:
            if db is not None:
                try:
                    # 1. Query client
                    client_record = db.query(Client).filter(Client.id == client_id_clean).first()
                    if client_record is None:
                        # Check fallback if not in MySQL
                        if client_id_clean not in SEED_CLIENTS:
                            raise ClientNotFoundError(f"Client ID '{client_id_clean}' does not exist.")
                        client_data = SEED_CLIENTS[client_id_clean]
                        company = client_data["company"]
                        email = client_data["contact_email"]
                        purchased = client_data["purchased_reports"]
                    else:
                        company = client_record.company
                        email = client_record.contact_email
                        purchased = [
                            r.strip() for r in client_record.purchased_reports.split(",") if r.strip()
                        ]

                    # 2. Query all reports to determine public vs paid
                    reports = db.query(Report).all()
                    if reports:
                        public_reports = [
                            r.id for r in reports
                            if (r.access.value if hasattr(r.access, "value") else str(r.access)) == "public"
                        ]
                        all_paid_reports = [
                            r.id for r in reports
                            if (r.access.value if hasattr(r.access, "value") else str(r.access)) == "paid"
                        ]
                    else:
                        public_reports = [rid for rid, d in SEED_REPORTS.items() if d["access"] == "public"]
                        all_paid_reports = [rid for rid, d in SEED_REPORTS.items() if d["access"] == "paid"]

                except Exception as query_err:
                    logger.warning("Error querying MySQL: %s. Using seed catalog.", query_err)
                    if client_id_clean not in SEED_CLIENTS:
                        raise ClientNotFoundError(f"Client ID '{client_id_clean}' does not exist.")
                    client_data = SEED_CLIENTS[client_id_clean]
                    company = client_data["company"]
                    email = client_data["contact_email"]
                    purchased = client_data["purchased_reports"]
                    public_reports = [rid for rid, d in SEED_REPORTS.items() if d["access"] == "public"]
                    all_paid_reports = [rid for rid, d in SEED_REPORTS.items() if d["access"] == "paid"]
            else:
                if client_id_clean not in SEED_CLIENTS:
                    raise ClientNotFoundError(f"Client ID '{client_id_clean}' does not exist.")
                client_data = SEED_CLIENTS[client_id_clean]
                company = client_data["company"]
                email = client_data["contact_email"]
                purchased = client_data["purchased_reports"]
                public_reports = [rid for rid, d in SEED_REPORTS.items() if d["access"] == "public"]
                all_paid_reports = [rid for rid, d in SEED_REPORTS.items() if d["access"] == "paid"]

            # Compute combined accessible reports (purchased + public, deduplicated and sorted)
            accessible = sorted(list(set(purchased + public_reports)))

            # Restricted reports are paid reports the client has NOT purchased
            restricted = sorted([r for r in all_paid_reports if r not in purchased])

            return ClientEntitlement(
                client_id=client_id_clean,
                company=company,
                contact_email=email,
                purchased_reports=purchased,
                accessible_reports=accessible,
                restricted_reports=restricted
            )

        finally:
            if should_close and db is not None:
                db.close()

    get_client_entitlements = get_client_entitlement


entitlement_service = EntitlementService()
get_client_entitlements = EntitlementService.get_client_entitlement


