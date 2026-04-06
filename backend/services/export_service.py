"""Public JSON/CSV export generation for the static dashboard."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from backend.enrichment.geospatial import build_geo_context
from backend.enrichment.official_context import extract_official_context
from backend.enrichment.timeline import build_timeline
from backend.models.case import Case
from shared.constants.statuses import HIGH_RISK_STATUSES, STATUS_LABELS
from shared.utils.dates import isoformat
from shared.utils.text import slugify


def _status_rank(status: str | None) -> int:
    if status in {"amberalert", "abudction", "abduction"}:
        return 3
    if status in {"vulnerable", "childsearchalert"}:
        return 2
    return 1


class ExportService:
    """Generates the public static dataset consumed by docs/."""

    def __init__(self, db: Session):
        self.db = db

    def build_public_export(self) -> dict:
        """Return the public export payload."""
        cases = (
            self.db.query(Case)
            .filter(Case.is_active.is_(True))
            .order_by(Case.missing_since.desc())
            .all()
        )

        exported_cases = []
        province_counts = {}
        status_counts = {}
        age_buckets = {"0-5": 0, "6-10": 0, "11-15": 0, "16-18": 0, "unknown": 0}
        update_trend = {}

        for case in cases:
            timeline = build_timeline(case.missing_since, case.arcgis_updated_at or case.updated_at, case.age)
            geo_context = build_geo_context(case.latitude, case.longitude)
            official_context = extract_official_context(
                case.official_summary_html,
                city=case.city,
                province=case.province,
            )
            if "official-field-conflict" in (case.risk_flags or []):
                warning = (
                    "A conflicting ArcGIS location field was detected and the case was re-anchored to the official summary location."
                )
                if warning not in official_context["quality_warnings"]:
                    official_context["quality_warnings"].append(warning)

            province = case.province or "Unknown"
            province_counts[province] = province_counts.get(province, 0) + 1
            status_label = STATUS_LABELS.get(case.status or "missing", "Missing")
            status_counts[status_label] = status_counts.get(status_label, 0) + 1

            if case.age is None:
                age_buckets["unknown"] += 1
            elif case.age <= 5:
                age_buckets["0-5"] += 1
            elif case.age <= 10:
                age_buckets["6-10"] += 1
            elif case.age <= 15:
                age_buckets["11-15"] += 1
            else:
                age_buckets["16-18"] += 1

            update_day = (case.arcgis_updated_at or case.updated_at or datetime.now(timezone.utc)).date().isoformat()
            update_trend[update_day] = update_trend.get(update_day, 0) + 1

            exported_cases.append(
                {
                    "id": case.id,
                    "slug": case.slug or slugify(case.name or f"case-{case.id}"),
                    "facts": {
                        "name": case.name or "Name withheld",
                        "aliases": case.aliases,
                        "age": case.age,
                        "gender": case.gender,
                        "ethnicity": case.ethnicity,
                        "city": case.city,
                        "province": case.province,
                        "status": case.status,
                        "status_label": status_label,
                        "case_status": case.case_status,
                        "missing_since": isoformat(case.missing_since),
                        "updated_at": isoformat(case.arcgis_updated_at or case.updated_at),
                        "authority_name": case.authority_name,
                        "authority_email": case.authority_email,
                        "authority_phone": case.authority_phone,
                        "authority_phone_alt": case.authority_phone_alt,
                        "authority_case_url": case.authority_case_url,
                        "mcsc_email": case.mcsc_email,
                        "mcsc_phone": case.mcsc_phone,
                        "official_summary_html": case.official_summary_html,
                        "official_context": official_context,
                        "coordinates": {
                            "latitude": case.latitude,
                            "longitude": case.longitude,
                        },
                    },
                    "inference": {
                        "risk_flags": case.risk_flags,
                        "risk_rank": _status_rank(case.status),
                        "elapsed_days": timeline["elapsed_days"],
                        "estimated_current_age": timeline["estimated_current_age"],
                        "summary": (
                            "Derived context only. Treat all inferred indicators as unverified and "
                            "report any relevant observations to the listed authority."
                        ),
                        "timeline_entries": timeline["timeline_entries"],
                        "what_to_report": [
                            "Where and when you saw the person or vehicle.",
                            "Screenshots, links, or photos from public sources.",
                            "Travel direction, transit stop, border/highway context, and timestamps.",
                        ],
                        "how_to_help_safely": [
                            "Share official case posts rather than rumor threads.",
                            "Do not contact relatives, confront subjects, or visit private addresses.",
                            "Route every lead to the listed authority or MCSC.",
                        ],
                    },
                    "photos": [
                        {
                            "url": photo.url,
                            "thumb_url": photo.thumb_url or photo.url,
                            "caption": photo.caption,
                            "is_primary": photo.is_primary,
                        }
                        for photo in case.photos
                    ],
                    "sources": [
                        {
                            "label": source.attribution_label or source.source_name,
                            "source_name": source.source_name,
                            "source_url": source.source_url,
                            "source_type": source.source_type,
                            "official": source.official,
                            "retrieved_at": isoformat(source.retrieved_at),
                            "trust_weight": source.trust_weight,
                        }
                        for source in case.source_records
                    ],
                    "resource_links": [
                        {
                            "label": resource.label,
                            "url": resource.url,
                            "category": resource.category,
                            "official": resource.official,
                            "authority_type": resource.authority_type,
                        }
                        for resource in case.resource_links
                    ],
                    "geo_context": geo_context,
                }
            )

        return {
            "meta": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "dataset_mode": "public-export",
                "source_name": "MCSC ArcGIS feed + public overlay enrichment",
                "safety_notice": (
                    "Official facts and inferred leads are separated. Report information to the listed "
                    "authority or MCSC. Do not intervene directly."
                ),
            },
            "stats": {
                "total_cases": len(exported_cases),
                "high_risk_cases": sum(1 for case in cases if case.status in HIGH_RISK_STATUSES),
                "province_distribution": province_counts,
                "status_distribution": status_counts,
                "age_distribution": age_buckets,
                "update_trend": update_trend,
            },
            "cases": exported_cases,
        }

    def write_public_export(self, path: Path) -> dict:
        """Write the public JSON export to disk."""
        payload = self.build_public_export()
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=True)
        return payload

    def build_csv_export(self) -> str:
        """Build a CSV export for investigators."""
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=["id", "name", "age", "city", "province", "status", "missing_since", "authority_name", "authority_case_url"],
        )
        writer.writeheader()
        for case in self.db.query(Case).filter(Case.is_active.is_(True)).all():
            writer.writerow(
                {
                    "id": case.id,
                    "name": case.name,
                    "age": case.age,
                    "city": case.city,
                    "province": case.province,
                    "status": case.status,
                    "missing_since": isoformat(case.missing_since),
                    "authority_name": case.authority_name,
                    "authority_case_url": case.authority_case_url,
                }
            )
        return buffer.getvalue()
