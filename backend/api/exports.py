"""Export routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.services.export_service import ExportService

router = APIRouter(prefix="/api/exports", tags=["exports"])


@router.get("/public.json")
def public_json(db: Session = Depends(get_db)) -> dict:
    return ExportService(db).build_public_export()


@router.get("/public.csv")
def public_csv(db: Session = Depends(get_db)) -> Response:
    csv_text = ExportService(db).build_csv_export()
    return Response(content=csv_text, media_type="text/csv")
