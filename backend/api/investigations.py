"""Investigator-mode routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.database import get_db
from backend.models.case import Case
from backend.models.investigation import InvestigationRun, Lead, SearchQueryLog
from backend.osint.resource_pack import build_case_resource_pack
from backend.services.investigation_service import InvestigationService
from backend.services.review_service import ReviewService

router = APIRouter(prefix="/api/investigations", tags=["investigations"])


class ReviewPayload(BaseModel):
    decision: str
    notes: str | None = None


def _ensure_enabled() -> None:
    if not settings.enable_investigator_mode:
        raise HTTPException(status_code=403, detail="Investigator mode is disabled.")


def _get_run_or_404(db: Session, run_id: int) -> InvestigationRun:
    run = db.get(InvestigationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Investigation run not found.")
    return run


def _get_case_or_404(db: Session, case_id: int) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return case


@router.post("/{case_id}")
async def run_investigation(case_id: int, db: Session = Depends(get_db)) -> dict:
    _ensure_enabled()
    try:
        run = await InvestigationService(db).run_for_case(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"run_id": run.id, "status": run.status, "connectors": run.connector_names}


@router.get("/cases/{case_id}/runs")
def list_case_runs(
    case_id: int,
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> dict:
    _ensure_enabled()
    runs = (
        db.query(InvestigationRun)
        .filter(InvestigationRun.case_id == case_id)
        .order_by(InvestigationRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "runs": [
            {
                "id": run.id,
                "case_id": run.case_id,
                "status": run.status,
                "connectors": run.connector_names,
                "started_at": run.started_at.isoformat(),
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "lead_count": db.query(Lead).filter(Lead.investigation_run_id == run.id).count(),
                "query_count": db.query(SearchQueryLog).filter(
                    SearchQueryLog.investigation_run_id == run.id
                ).count(),
            }
            for run in runs
        ]
    }


@router.get("/cases/{case_id}/resource-pack")
def get_case_resource_pack(case_id: int, db: Session = Depends(get_db)) -> dict:
    _ensure_enabled()
    case = _get_case_or_404(db, case_id)
    return build_case_resource_pack(case)


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)) -> dict:
    _ensure_enabled()
    run = _get_run_or_404(db, run_id)
    leads = db.query(Lead).filter(Lead.investigation_run_id == run_id)
    query_logs = db.query(SearchQueryLog).filter(SearchQueryLog.investigation_run_id == run_id)
    total_leads = leads.count()
    reviewed_leads = leads.filter(Lead.reviewed.is_(True)).count()
    high_confidence = leads.filter(Lead.confidence >= 0.6).count()
    failed_queries = query_logs.filter(SearchQueryLog.status == "failed").count()
    warning_queries = query_logs.filter(SearchQueryLog.status == "warning").count()
    return {
        "id": run.id,
        "case_id": run.case_id,
        "status": run.status,
        "connectors": run.connector_names,
        "facts_summary": run.facts_summary,
        "inference_summary": run.inference_summary,
        "error_message": run.error_message,
        "started_at": run.started_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "stats": {
            "total_leads": total_leads,
            "reviewed_leads": reviewed_leads,
            "unreviewed_leads": total_leads - reviewed_leads,
            "high_confidence_leads": high_confidence,
            "query_logs": query_logs.count(),
            "failed_queries": failed_queries,
            "warning_queries": warning_queries,
        },
    }


@router.get("/runs/{run_id}/leads")
def get_run_leads(
    run_id: int,
    review_status: str | None = None,
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict:
    _ensure_enabled()
    _get_run_or_404(db, run_id)
    statement = db.query(Lead).filter(
        Lead.investigation_run_id == run_id,
        Lead.confidence >= min_confidence,
    )
    if review_status:
        statement = statement.filter(Lead.review_status == review_status)
    leads = statement.order_by(Lead.confidence.desc(), Lead.found_at.desc()).limit(limit).all()
    return {
        "leads": [
            {
                "id": lead.id,
                "title": lead.title,
                "summary": lead.summary,
                "content_excerpt": lead.content_excerpt,
                "source_name": lead.source_name,
                "source_kind": lead.source_kind,
                "source_url": lead.source_url,
                "query_used": lead.query_used,
                "location_text": lead.location_text,
                "category": lead.category,
                "confidence": lead.confidence,
                "source_trust": lead.source_trust,
                "corroboration_count": lead.corroboration_count,
                "rationale": lead.rationale,
                "review_status": lead.review_status,
                "reviewed": lead.reviewed,
                "human_reason": lead.human_reason,
                "found_at": lead.found_at.isoformat(),
                "published_at": lead.published_at.isoformat() if lead.published_at else None,
                "latitude": lead.latitude,
                "longitude": lead.longitude,
            }
            for lead in leads
        ]
    }


@router.get("/runs/{run_id}/query-logs")
def get_run_query_logs(run_id: int, db: Session = Depends(get_db)) -> dict:
    _ensure_enabled()
    _get_run_or_404(db, run_id)
    query_logs = (
        db.query(SearchQueryLog)
        .filter(SearchQueryLog.investigation_run_id == run_id)
        .order_by(SearchQueryLog.requested_at.desc())
        .all()
    )
    return {
        "query_logs": [
            {
                "id": log.id,
                "connector_name": log.connector_name,
                "source_kind": log.source_kind,
                "query_used": log.query_used,
                "requested_at": log.requested_at.isoformat(),
                "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                "status": log.status,
                "http_status": log.http_status,
                "result_count": log.result_count,
                "notes": log.notes,
            }
            for log in query_logs
        ]
    }


@router.patch("/leads/{lead_id}/review")
def review_lead(lead_id: int, payload: ReviewPayload, db: Session = Depends(get_db)) -> dict:
    _ensure_enabled()
    try:
        lead = ReviewService(db).review_lead(lead_id, payload.decision, payload.notes)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"lead_id": lead.id, "review_status": lead.review_status}
