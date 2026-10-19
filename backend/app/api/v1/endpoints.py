from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from typing import List, Dict, Any, Optional

from backend.app.core.database import get_db, engine
from backend.app.models.schema import Report, MarketMetric, Client
from backend.app.core.vector_store import vector_store
from backend.app.services.ingestion import IngestionService
from backend.app.services.retrieval import rag_service, RetrievalResponse
from backend.app.services.rag_generator import rag_generator, RAGAnswerResponse
from backend.app.services.entitlement import ClientNotFoundError

router = APIRouter()


class IngestRequest(BaseModel):
    report_id: Optional[str] = None
    force_reindex: bool = False


class RAGQueryRequest(BaseModel):
    client_id: str = Field(..., description="Client ID e.g. C-01, C-02")
    question: str = Field(..., description="User natural language question")
    top_k: int = Field(5, ge=1, le=20, description="Max passages to retrieve")


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


@router.post("/ingest")
def trigger_ingestion(request: IngestRequest = IngestRequest()):
    """Trigger PDF ingestion pipeline for all or a specific report."""
    service = IngestionService(vector_store_instance=vector_store)
    targets = [request.report_id] if request.report_id else None
    summary = service.ingest_all(target_report_ids=targets, force_reindex=request.force_reindex)
    return summary


@router.get("/vector-status")
def get_vector_status():
    """Retrieve ChromaDB collection metrics and indexed reports."""
    return vector_store.get_stats()


@router.post("/retrieve", response_model=RetrievalResponse)
def secure_retrieve(request: RAGQueryRequest, db: Session = Depends(get_db)):
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


@router.post("/chat", response_model=RAGAnswerResponse)
def rag_chat(request: RAGQueryRequest, db: Session = Depends(get_db)):
    """
    End-to-end RAG chat pipeline.
    Enforces entitlements, sanitizes context, and generates cited answer.
    """
    try:
        return rag_generator.generate_answer(
            client_id=request.client_id,
            query=request.question,
            top_k=request.top_k,
            db=db
        )
    except ClientNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat generation error: {str(e)}")
