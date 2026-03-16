"""API routes for face recognition operations.

Provides endpoints for:
- Indexing faces in case photos (bulk or per-case)
- Viewing face encodings for a case
- Cross-case face matching
- Uploading an image for face comparison
- Reviewing face matches
"""

import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, File
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.database import get_db, SessionLocal
from backend.models.case import MissingCase, CasePhoto
from backend.models.face import FaceEncoding, FaceMatch
from backend.analysis.face_engine import (
    index_all_photos,
    index_photo,
    find_cross_case_matches,
    save_cross_case_matches,
    match_uploaded_image,
)

router = APIRouter(prefix="/api/faces", tags=["faces"])


# ---------------------------------------------------------------------------
# Face indexing
# ---------------------------------------------------------------------------


@router.post("/index")
def index_faces(
    case_objectid: Optional[int] = Query(None, description="Index only this case's photos"),
    force: bool = Query(False, description="Re-index photos that already have encodings"),
    db: Session = Depends(get_db),
):
    """Index faces in case photos — extract, encode, and crop.

    If case_objectid is provided, only that case's photos are indexed.
    Otherwise, all photos in the database are indexed.

    This is a synchronous endpoint (blocking) since face detection can take
    a few seconds per photo. For large batches, consider running via script.
    """
    try:
        result = index_all_photos(db, force=force, case_objectid=case_objectid)
        return {
            "status": "completed",
            **result,
        }
    except Exception as e:
        logger.error(f"Face indexing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Face indexing failed: {str(e)}")


@router.get("/stats")
def face_stats(db: Session = Depends(get_db)):
    """Get summary statistics about the face index."""
    total_encodings = db.query(func.count(FaceEncoding.id)).scalar() or 0
    total_matches = db.query(func.count(FaceMatch.id)).scalar() or 0
    cases_with_faces = (
        db.query(func.count(func.distinct(FaceEncoding.case_objectid))).scalar() or 0
    )
    reviewed_matches = (
        db.query(func.count(FaceMatch.id))
        .filter(FaceMatch.reviewed == True)  # noqa: E712
        .scalar() or 0
    )

    return {
        "total_face_encodings": total_encodings,
        "total_cross_case_matches": total_matches,
        "cases_with_faces": cases_with_faces,
        "reviewed_matches": reviewed_matches,
    }


# ---------------------------------------------------------------------------
# View face encodings for a case
# ---------------------------------------------------------------------------


@router.get("/case/{case_objectid}")
def get_case_faces(
    case_objectid: int,
    db: Session = Depends(get_db),
):
    """Get all face encodings for a specific case."""
    # Verify case exists
    case = db.query(MissingCase).filter(MissingCase.objectid == case_objectid).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    faces = (
        db.query(FaceEncoding)
        .filter(FaceEncoding.case_objectid == case_objectid)
        .order_by(FaceEncoding.photo_id, FaceEncoding.face_index)
        .all()
    )

    return {
        "case_objectid": case_objectid,
        "case_name": case.name,
        "total_faces": len(faces),
        "faces": [f.to_dict() for f in faces],
    }


# ---------------------------------------------------------------------------
# Cross-case matching
# ---------------------------------------------------------------------------


@router.post("/match")
def run_cross_case_matching(
    case_objectid: Optional[int] = Query(None, description="Compare this case vs all others"),
    threshold: Optional[float] = Query(None, description="Distance threshold (default from config)"),
    save_results: bool = Query(True, description="Save matches to database"),
    db: Session = Depends(get_db),
):
    """Run cross-case face matching.

    If case_objectid is provided, compare that case's faces against all others.
    Otherwise, compare all faces against each other.
    """
    try:
        matches = find_cross_case_matches(
            db, case_objectid=case_objectid, threshold=threshold
        )

        saved = []
        if save_results and matches:
            saved = save_cross_case_matches(db, matches)

        return {
            "status": "completed",
            "total_matches": len(matches),
            "new_matches_saved": len(saved),
            "matches": matches[:50],  # Cap response size
        }
    except Exception as e:
        logger.error(f"Cross-case matching failed: {e}")
        raise HTTPException(status_code=500, detail=f"Matching failed: {str(e)}")


@router.get("/matches")
def get_face_matches(
    case_objectid: Optional[int] = Query(None, description="Filter by case"),
    reviewed: Optional[bool] = Query(None, description="Filter by review status"),
    min_confidence: Optional[float] = Query(None, description="Minimum confidence"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Get stored face matches with optional filters."""
    query = db.query(FaceMatch)

    if case_objectid is not None:
        query = query.filter(
            (FaceMatch.case_a_objectid == case_objectid) |
            (FaceMatch.case_b_objectid == case_objectid)
        )
    if reviewed is not None:
        query = query.filter(FaceMatch.reviewed == reviewed)
    if min_confidence is not None:
        query = query.filter(FaceMatch.confidence >= min_confidence)

    total = query.count()
    matches = (
        query.order_by(desc(FaceMatch.confidence))
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Enrich with case names and crop paths
    enriched = []
    for m in matches:
        d = m.to_dict()
        # Get case names
        case_a = db.query(MissingCase).filter(MissingCase.objectid == m.case_a_objectid).first()
        case_b = db.query(MissingCase).filter(MissingCase.objectid == m.case_b_objectid).first()
        d["case_a_name"] = case_a.name if case_a else None
        d["case_b_name"] = case_b.name if case_b else None

        # Get crop paths
        face_a = db.query(FaceEncoding).filter(FaceEncoding.id == m.face_a_id).first()
        face_b = db.query(FaceEncoding).filter(FaceEncoding.id == m.face_b_id).first()
        d["face_a_crop"] = face_a.crop_path if face_a else None
        d["face_b_crop"] = face_b.crop_path if face_b else None

        enriched.append(d)

    return {
        "total": total,
        "matches": enriched,
    }


# ---------------------------------------------------------------------------
# Upload image for comparison
# ---------------------------------------------------------------------------


@router.post("/search")
async def search_by_upload(
    file: UploadFile = File(..., description="Image to search for matching faces"),
    threshold: Optional[float] = Query(None, description="Distance threshold"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Upload an image and compare against all indexed faces.

    Returns the best matching cases sorted by similarity.
    """
    # Validate file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Save to temp file
    tmp_path: str | None = None
    try:
        suffix = Path(file.filename or "upload.jpg").suffix or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        results = match_uploaded_image(tmp_path, db, threshold=threshold, limit=limit)

        return {
            "total_matches": len(results),
            "matches": results,
        }

    except Exception as e:
        logger.error(f"Upload face search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Face search failed: {str(e)}")
    finally:
        # Clean up temp file
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Review face matches
# ---------------------------------------------------------------------------


class FaceMatchReviewBody(BaseModel):
    reviewed: bool
    is_same_person: Optional[bool] = None
    review_notes: Optional[str] = None


@router.patch("/matches/{match_id}")
def review_face_match(
    match_id: int,
    body: FaceMatchReviewBody,
    db: Session = Depends(get_db),
):
    """Review a face match — confirm or reject as same person."""
    match = db.query(FaceMatch).filter(FaceMatch.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Face match not found")

    match.reviewed = body.reviewed  # type: ignore[assignment]
    if body.is_same_person is not None:
        match.is_same_person = body.is_same_person  # type: ignore[assignment]
    if body.review_notes is not None:
        match.review_notes = body.review_notes  # type: ignore[assignment]

    db.commit()
    db.refresh(match)

    return match.to_dict()
