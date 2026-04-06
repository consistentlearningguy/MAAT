"""MCSC ArcGIS ingestion and normalization."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from backend.core.config import settings
from backend.enrichment.official_context import extract_official_context
from shared.constants.provinces import PROVINCE_LABELS
from shared.constants.statuses import HIGH_RISK_STATUSES, STATUS_LABELS
from shared.utils.text import normalize_whitespace, slugify

QUERY_FIELDS = [
    "objectid",
    "globalid",
    "status",
    "casestatus",
    "name",
    "age",
    "gender",
    "ethnicity",
    "city",
    "province",
    "missing",
    "description",
    "authname",
    "authemail",
    "authlink",
    "authphone",
    "authphonetwo",
    "thumb_url",
    "pic_url",
    "mcscemail",
    "mcscphone",
    "CreationDate",
    "EditDate",
]


def _timestamp_from_arcgis(value: int | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    except (ValueError, OSError, TypeError):
        return None


def normalize_case_feature(feature: dict) -> dict:
    """Normalize a raw ArcGIS feature into the internal case payload."""
    attributes = feature.get("attributes", {})
    geometry = feature.get("geometry", {})
    raw_province = attributes.get("province") or ""
    province = PROVINCE_LABELS.get(raw_province, raw_province) or "Unknown"
    status = (attributes.get("status") or "missing").lower()
    missing_since = _timestamp_from_arcgis(attributes.get("missing"))
    age = attributes.get("age")
    age_value = int(age) if isinstance(age, (int, float)) else None
    description_html = attributes.get("description") or ""
    city = normalize_whitespace(attributes.get("city"))
    official_context = extract_official_context(description_html, city=city, province=province)
    corrected_city = official_context.get("inferred_city") or city
    corrected_province = official_context.get("inferred_province") or province
    risk_flags = []

    if status in HIGH_RISK_STATUSES:
        risk_flags.append("high-priority-status")
    if age_value is not None and age_value <= 12:
        risk_flags.append("young-child")
    if missing_since:
        elapsed_days = max(0, int((datetime.now(timezone.utc) - missing_since).total_seconds() // 86400))
        if elapsed_days <= 7:
            risk_flags.append("recent-disappearance")
    if official_context["quality_warnings"]:
        risk_flags.append("official-field-conflict")

    return {
        "id": int(attributes["objectid"]),
        "source_record_id": attributes.get("globalid"),
        "slug": slugify(attributes.get("name") or f"case-{attributes.get('objectid')}"),
        "name": normalize_whitespace(attributes.get("name")),
        "aliases": [],
        "age": age_value,
        "gender": normalize_whitespace(attributes.get("gender")),
        "ethnicity": normalize_whitespace(attributes.get("ethnicity")),
        "city": corrected_city,
        "province": corrected_province,
        "latitude": geometry.get("y"),
        "longitude": geometry.get("x"),
        "status": status,
        "status_label": STATUS_LABELS.get(status, "Missing"),
        "case_status": (attributes.get("casestatus") or "").lower(),
        "missing_since": missing_since,
        "official_summary_html": description_html,
        "authority_name": normalize_whitespace(attributes.get("authname")),
        "authority_email": normalize_whitespace(attributes.get("authemail")),
        "authority_phone": normalize_whitespace(attributes.get("authphone")),
        "authority_phone_alt": normalize_whitespace(attributes.get("authphonetwo")),
        "authority_case_url": attributes.get("authlink"),
        "mcsc_email": normalize_whitespace(attributes.get("mcscemail")) or "tips@mcsc.ca",
        "mcsc_phone": normalize_whitespace(attributes.get("mcscphone")),
        "risk_flags": risk_flags,
        "source_feed": "Missing Children Society of Canada ArcGIS",
        "source_url": settings.mcsc_feature_server_url,
        "arcgis_created_at": _timestamp_from_arcgis(attributes.get("CreationDate")),
        "arcgis_updated_at": _timestamp_from_arcgis(attributes.get("EditDate")),
        "photos": [
            {
                "url": attributes.get("pic_url") or attributes.get("thumb_url"),
                "thumb_url": attributes.get("thumb_url"),
                "caption": "Official case photo",
                "source_url": attributes.get("pic_url") or attributes.get("thumb_url"),
                "is_primary": True,
            }
        ] if attributes.get("pic_url") or attributes.get("thumb_url") else [],
        "source_records": [
            {
                "source_name": "Missing Children Society of Canada",
                "source_type": "official-feed",
                "source_url": settings.mcsc_feature_server_url,
                "query_used": "casestatus='open'",
                "official": True,
                "trust_weight": 1.0,
                "attribution_label": "Official MCSC ArcGIS feed",
                "raw_excerpt": normalize_whitespace(description_html),
                "metadata_json": {
                    "status_label": STATUS_LABELS.get(status, "Missing"),
                    "raw_province": raw_province,
                    "summary_inferred_province": official_context.get("inferred_province"),
                    "official_location_text": official_context.get("location_text"),
                    "quality_warnings": official_context.get("quality_warnings", []),
                },
            }
        ],
    }


class MCSCArcGISClient:
    """Public ArcGIS client used by sync scripts and optional backend mode."""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.mcsc_feature_server_url

    async def fetch_open_cases(self) -> list[dict]:
        params = {
            "where": "casestatus='open'",
            "outFields": ",".join(QUERY_FIELDS),
            "returnGeometry": "true",
            "orderByFields": "missing DESC",
            "resultRecordCount": "1000",
            "f": "json",
        }
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.get(f"{self.base_url}/query", params=params)
            response.raise_for_status()
            payload = response.json()
        return payload.get("features", [])
