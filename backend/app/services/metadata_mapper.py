"""
Metadata Mapper Module for Project Atlas
Loads report metadata from the MySQL database and merges with market metric regional indicators.
"""

from typing import Dict, Any, List, Optional
import logging
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal
from backend.app.models.schema import Report, MarketMetric

logger = logging.getLogger(__name__)

# Known seed metadata for offline fallback
FALLBACK_METADATA: Dict[str, Dict[str, Any]] = {
    "R-101": {
        "id": "R-101",
        "title": "Global Smart Water Meter Market 2025",
        "publisher": "CMR",
        "publication_year": 2025,
        "sector": "Utilities",
        "access": "paid",
        "region": "Global, APAC"
    },
    "R-102": {
        "id": "R-102",
        "title": "Smart Water Metering: Industry Outlook 2024",
        "publisher": "Aquila Insights (third party)",
        "publication_year": 2024,
        "sector": "Utilities",
        "access": "public",
        "region": "Global, APAC"
    },
    "R-103": {
        "id": "R-103",
        "title": "Residential Water Purifier Market",
        "publisher": "CMR",
        "publication_year": 2025,
        "sector": "Consumer Durables",
        "access": "paid",
        "region": "Global"
    }
}


class MetadataMapper:
    """Retrieves and maps report metadata from MySQL tables."""

    @staticmethod
    def get_report_metadata(report_id: str, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
        """
        Fetch metadata for a single report from MySQL. Falls back to catalog if DB unavailable.
        """
        all_meta = MetadataMapper.get_all_reports_metadata(db=db)
        return all_meta.get(report_id)

    @staticmethod
    def get_all_reports_metadata(db: Optional[Session] = None) -> Dict[str, Dict[str, Any]]:
        """
        Retrieve all report metadata mapped with regions and publication years.
        """
        should_close = False
        if db is None:
            try:
                db = SessionLocal()
                should_close = True
            except Exception as e:
                logger.warning("Could not establish MySQL session for metadata: %s. Using fallback catalog.", e)
                return FALLBACK_METADATA.copy()

        reports_map: Dict[str, Dict[str, Any]] = {}

        try:
            reports = db.query(Report).all()
            if not reports:
                logger.info("No reports found in MySQL database, falling back to static seed catalog.")
                return FALLBACK_METADATA.copy()

            # Query all market metrics to aggregate distinct regions per report
            metrics = db.query(MarketMetric).all()
            regions_by_report: Dict[str, set] = {}
            for m in metrics:
                if m.report_id and m.region:
                    regions_by_report.setdefault(m.report_id, set()).add(m.region)

            for r in reports:
                # Extract publication year
                pub_year = 0
                if hasattr(r.published, "year"):
                    pub_year = r.published.year
                elif r.published:
                    pub_year = int(str(r.published).split("-")[0])

                # Get aggregated regions
                regions_set = regions_by_report.get(r.id, set())
                region_str = ", ".join(sorted(regions_set)) if regions_set else "Global"

                # Normalize access string
                access_val = r.access.value if hasattr(r.access, "value") else str(r.access)

                reports_map[r.id] = {
                    "id": r.id,
                    "title": r.title,
                    "publisher": r.publisher,
                    "publication_year": pub_year,
                    "sector": r.sector,
                    "access": access_val,
                    "region": region_str
                }

            logger.info("Loaded metadata for %d reports from MySQL.", len(reports_map))
            return reports_map

        except Exception as query_err:
            logger.warning("Error querying MySQL report metadata: %s. Using fallback catalog.", query_err)
            return FALLBACK_METADATA.copy()

        finally:
            if should_close and db is not None:
                db.close()
