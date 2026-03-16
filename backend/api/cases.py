"""API routes for missing person cases."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func, extract
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models.case import MissingCase, CasePhoto

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.get("")
def list_cases(
    province: Optional[str] = Query(None, description="Filter by province code"),
    status: Optional[str] = Query(None, description="Filter by status (vulnerable, abudction, amberalert, childsearchalert, missing)"),
    case_status: Optional[str] = Query("open", description="Filter by case status (open, located, archived, expired)"),
    search: Optional[str] = Query(None, description="Search by name or city"),
    min_age: Optional[int] = Query(None, description="Minimum age filter"),
    max_age: Optional[int] = Query(None, description="Maximum age filter"),
    sort_by: str = Query("missing_since", description="Sort field"),
    order: str = Query("desc", description="Sort order (asc/desc)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List and search missing person cases."""
    query = db.query(MissingCase)

    # Apply filters
    if province:
        query = query.filter(MissingCase.province == province)
    if status:
        query = query.filter(MissingCase.status == status)
    if case_status:
        query = query.filter(MissingCase.case_status == case_status)
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (MissingCase.name.ilike(search_term))
            | (MissingCase.city.ilike(search_term))
            | (MissingCase.description.ilike(search_term))
        )
    if min_age is not None:
        query = query.filter(MissingCase.age >= min_age)
    if max_age is not None:
        query = query.filter(MissingCase.age <= max_age)

    # Get total count before pagination
    total = query.count()

    # Apply sorting
    sort_column = getattr(MissingCase, sort_by, MissingCase.missing_since)
    if order.lower() == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    # Apply pagination
    cases = query.offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "cases": [c.to_dict() for c in cases],
    }


@router.get("/stats")
def get_stats(
    case_status: Optional[str] = Query("open"),
    db: Session = Depends(get_db),
):
    """Get aggregate statistics about cases."""
    base_query = db.query(MissingCase)
    if case_status:
        base_query = base_query.filter(MissingCase.case_status == case_status)

    total = base_query.count()

    # By province
    by_province = (
        base_query.with_entities(
            MissingCase.province, func.count(MissingCase.objectid)
        )
        .group_by(MissingCase.province)
        .all()
    )

    # By status
    by_status = (
        base_query.with_entities(
            MissingCase.status, func.count(MissingCase.objectid)
        )
        .group_by(MissingCase.status)
        .all()
    )

    # By age brackets
    age_brackets = []
    brackets = [(0, 5), (6, 10), (11, 15), (16, 18), (19, 25), (26, 100)]
    for low, high in brackets:
        count = base_query.filter(
            MissingCase.age >= low, MissingCase.age <= high
        ).count()
        label = f"{low}-{high}" if high < 100 else f"{low}+"
        age_brackets.append({"range": label, "count": count})

    # By year of disappearance
    by_year = (
        base_query.with_entities(
            extract("year", MissingCase.missing_since).label("year"),
            func.count(MissingCase.objectid),
        )
        .filter(MissingCase.missing_since.isnot(None))
        .group_by("year")
        .order_by(extract("year", MissingCase.missing_since).desc())
        .all()
    )

    # Recent cases (last 30 days)
    from datetime import datetime, timezone, timedelta
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    recent_count = base_query.filter(
        MissingCase.missing_since >= thirty_days_ago
    ).count()

    # Amber alerts count
    amber_count = base_query.filter(MissingCase.status == "amberalert").count()

    return {
        "total": total,
        "recent_30_days": recent_count,
        "amber_alerts": amber_count,
        "by_province": {prov: count for prov, count in by_province if prov},
        "by_status": {status: count for status, count in by_status if status},
        "by_age": age_brackets,
        "by_year": {str(int(year)): count for year, count in by_year if year},
    }


@router.get("/geojson")
def get_geojson(
    province: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    case_status: Optional[str] = Query("open"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get cases as GeoJSON FeatureCollection for map rendering."""
    query = db.query(MissingCase).filter(
        MissingCase.latitude.isnot(None),
        MissingCase.longitude.isnot(None),
    )

    if province:
        query = query.filter(MissingCase.province == province)
    if status:
        query = query.filter(MissingCase.status == status)
    if case_status:
        query = query.filter(MissingCase.case_status == case_status)
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (MissingCase.name.ilike(search_term))
            | (MissingCase.city.ilike(search_term))
        )

    cases = query.all()

    features = [c.to_geojson_feature() for c in cases if c.latitude and c.longitude]

    return {
        "type": "FeatureCollection",
        "features": features,
    }


@router.get("/{objectid}")
def get_case(objectid: int, db: Session = Depends(get_db)):
    """Get a single case by objectid with photos."""
    case = db.query(MissingCase).filter(MissingCase.objectid == objectid).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Load photos
    photos = (
        db.query(CasePhoto)
        .filter(CasePhoto.case_objectid == objectid)
        .all()
    )

    result = case.to_dict()
    result["photos"] = [p.to_dict() for p in photos]
    return result
