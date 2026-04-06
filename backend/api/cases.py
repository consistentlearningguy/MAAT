"""Case routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.core.database import get_db
from backend.models.case import Case
from backend.models.investigation import InvestigationRun, Lead
from backend.services.case_service import CaseService
from backend.services.export_service import ExportService

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.get("")
def list_cases(db: Session = Depends(get_db)) -> dict:
    service = CaseService(db)
    cases = service.list_cases()
    return {
        "total": len(cases),
        "cases": [_serialize_case_summary(case) for case in cases],
    }


def _serialize_case_summary(case: Case) -> dict:
    """Serialize a case with fields needed by the dashboard sidebar."""
    primary_photo = next((p for p in case.photos if p.is_primary), None) if case.photos else None
    photo_url = primary_photo.url if primary_photo else (case.photos[0].url if case.photos else None)
    return {
        "id": case.id,
        "name": case.name,
        "province": case.province,
        "city": case.city,
        "status": case.status,
        "age": case.age,
        "gender": case.gender,
        "missing_since": case.missing_since.isoformat() if case.missing_since else None,
        "latitude": case.latitude,
        "longitude": case.longitude,
        "photo_url": photo_url,
    }


@router.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict:
    base_stats = ExportService(db).build_public_export().get("stats", {})
    # Add investigation stats for dashboard
    investigated_count = db.query(func.count(func.distinct(InvestigationRun.case_id))).scalar() or 0
    total_leads = db.query(func.count(Lead.id)).scalar() or 0
    base_stats["investigated_count"] = investigated_count
    base_stats["total_leads"] = total_leads
    return base_stats


@router.get("/{case_id}")
def get_case(case_id: int, db: Session = Depends(get_db)) -> dict:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    primary_photo = next((p for p in case.photos if p.is_primary), None) if case.photos else None
    photo_url = primary_photo.url if primary_photo else (case.photos[0].url if case.photos else None)
    return {
        "id": case.id,
        "name": case.name,
        "aliases": case.aliases or [],
        "age": case.age,
        "gender": case.gender,
        "province": case.province,
        "city": case.city,
        "status": case.status,
        "missing_since": case.missing_since.isoformat() if case.missing_since else None,
        "latitude": case.latitude,
        "longitude": case.longitude,
        "photo_url": photo_url,
        "official_summary_html": case.official_summary_html,
        "authority_name": case.authority_name,
        "authority_email": case.authority_email,
        "authority_phone": case.authority_phone,
        "authority_case_url": case.authority_case_url,
        "mcsc_email": case.mcsc_email,
        "mcsc_phone": case.mcsc_phone,
        "risk_flags": case.risk_flags or [],
        "photos": [{"url": p.url, "caption": p.caption, "is_primary": p.is_primary} for p in (case.photos or [])],
    }
