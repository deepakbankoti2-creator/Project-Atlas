from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from typing import List, Dict, Any, Optional

from backend.app.core.database import get_db, engine
from backend.app.models.schema import Report, MarketMetric, Client, EscalationTicket
from backend.app.core.vector_store import vector_store
from backend.app.services.ingestion import IngestionService
from backend.app.services.retrieval import rag_service, RetrievalResponse
from backend.app.agent.workflow import agent_workflow, WorkflowOutput
from backend.app.agent.escalation import OFFLINE_TICKETS
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


class FeedbackRequest(BaseModel):
    conversation_id: int
    client_id: str
    rating: str = Field(..., description="'up' or 'down'")
    comment: Optional[str] = None


OFFLINE_CONVERSATIONS: List[Dict[str, Any]] = []
OFFLINE_FEEDBACK: List[Dict[str, Any]] = []


@router.post("/chat", response_model=WorkflowOutput)
def agent_chat(request: RAGQueryRequest, db: Session = Depends(get_db)):
    """
    Execute Project Atlas LangGraph agent workflow.
    Routes to SQL, Python calculator, entitlement-checked retrieval, or safety refusal.
    Stores the conversation in MySQL (or in-memory fallback).
    """
    try:
        output = agent_workflow.run(
            client_id=request.client_id,
            query=request.question
        )
    except ClientNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent workflow error: {str(e)}")

    import json
    from datetime import datetime
    citations_data = [c.model_dump() if hasattr(c, "model_dump") else dict(c) for c in output.citations]
    conv_id = None
    try:
        conv_record = Conversation(
            client_id=request.client_id,
            question=request.question,
            answer=output.answer,
            citations_json=json.dumps(citations_data),
            confidence=str(output.confidence),
            conflicts_json=json.dumps(output.conflicts),
            derived_values_json=json.dumps(output.derived_values),
            escalated=1 if output.escalated else 0,
            escalation_ticket_id=output.escalation_ticket_id,
            route=output.route,
            created_at=datetime.utcnow()
        )
        db.add(conv_record)
        db.commit()
        db.refresh(conv_record)
        conv_id = conv_record.id
    except Exception:
        db.rollback()
        conv_id = len(OFFLINE_CONVERSATIONS) + 1
        OFFLINE_CONVERSATIONS.append({
            "id": conv_id,
            "client_id": request.client_id,
            "question": request.question,
            "answer": output.answer,
            "citations": citations_data,
            "confidence": output.confidence,
            "conflicts": output.conflicts,
            "derived_values": output.derived_values,
            "escalated": output.escalated,
            "escalation_ticket_id": output.escalation_ticket_id,
            "route": output.route,
            "created_at": str(datetime.utcnow())
        })

    output.conversation_id = conv_id
    return output


@router.post("/feedback")
def submit_feedback(request: FeedbackRequest, db: Session = Depends(get_db)):
    """
    Store thumbs-up or thumbs-down feedback for a conversation.
    """
    from datetime import datetime
    if request.rating not in ("up", "down"):
        raise HTTPException(status_code=400, detail="Rating must be 'up' or 'down'.")

    try:
        fb_record = Feedback(
            conversation_id=request.conversation_id,
            client_id=request.client_id,
            rating=request.rating,
            comment=request.comment,
            created_at=datetime.utcnow()
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
            "created_at": str(datetime.utcnow())
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


@router.get("/escalations")
def list_escalations(db: Session = Depends(get_db)):
    """Retrieve all human-analyst review escalation tickets."""
    try:
        tickets = db.query(EscalationTicket).order_by(EscalationTicket.id.desc()).all()
        return [
            {
                "ticket_id": f"ESC-{t.id:04d}",
                "client_id": t.client_id,
                "query": t.query,
                "reason": t.reason,
                "status": t.status,
                "created_at": str(t.created_at)
            }
            for t in tickets
        ]
    except Exception:
        # Fallback to in-memory tickets if DB offline
        return list(OFFLINE_TICKETS.values())

