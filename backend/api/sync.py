"""API routes for data synchronization."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.ingestion.mcsc_client import mcsc_client
from backend.models.case import SyncLog

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("")
async def trigger_sync(db: Session = Depends(get_db)):
    """Trigger a manual data sync from MCSC."""
    result = await mcsc_client.sync_all_cases(db=db)
    return result


@router.get("/history")
def get_sync_history(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get recent sync log entries."""
    logs = (
        db.query(SyncLog)
        .order_by(SyncLog.started_at.desc())
        .limit(limit)
        .all()
    )
    return {"logs": [log.to_dict() for log in logs]}
