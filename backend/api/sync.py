"""Sync and export routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.database import get_db
from backend.services.case_service import CaseService
from backend.services.export_service import ExportService

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/cases")
async def sync_cases(db: Session = Depends(get_db)) -> dict:
    return await CaseService(db).sync_from_mcsc()


@router.post("/public-export")
def export_public_data(db: Session = Depends(get_db)) -> dict:
    payload = ExportService(db).write_public_export(settings.public_export_path)
    return {"path": str(settings.public_export_path), "cases": len(payload["cases"])}
