from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from typing import List, Dict, Any

from backend.app.core.database import get_db, engine
from backend.app.models.schema import Report, MarketMetric, Client

router = APIRouter()


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
