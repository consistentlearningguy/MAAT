"""Case sync and query services."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.enrichment.resources import resource_links_for_province
from backend.ingestion.mcsc import MCSCArcGISClient, normalize_case_feature
from backend.models.case import Case, CasePhoto, ResourceLink, SourceRecord
from shared.constants.statuses import HIGH_RISK_STATUSES


class CaseService:
    """Operations for normalized cases."""

    def __init__(self, db: Session):
        self.db = db

    async def sync_from_mcsc(self) -> dict:
        """Sync open cases from the public ArcGIS feed into SQLite."""
        client = MCSCArcGISClient()
        features = await client.fetch_open_cases()
        normalized_cases = [normalize_case_feature(feature) for feature in features]

        seen_ids = set()
        added = 0
        updated = 0

        for payload in normalized_cases:
            seen_ids.add(payload["id"])
            existing = self.db.get(Case, payload["id"])
            photos = payload.pop("photos", [])
            source_records = payload.pop("source_records", [])
            payload.pop("status_label", None)

            if existing is None:
                existing = Case(**payload)
                self.db.add(existing)
                self.db.flush()
                added += 1
            else:
                for key, value in payload.items():
                    setattr(existing, key, value)
                updated += 1

            existing.photos.clear()
            for photo in photos:
                existing.photos.append(CasePhoto(**photo))

            existing.source_records.clear()
            for source in source_records:
                existing.source_records.append(SourceRecord(**source))

            existing.resource_links.clear()
            for resource in resource_links_for_province(existing.province):
                existing.resource_links.append(
                    ResourceLink(
                        province=existing.province,
                        category=resource["category"],
                        label=resource["label"],
                        url=resource["url"],
                        authority_type=resource.get("authority_type"),
                        official=True,
                    )
                )

        for existing in self.db.scalars(select(Case)).all():
            if existing.id not in seen_ids:
                existing.is_active = False
                existing.case_status = "resolved_or_removed"

        self.db.commit()
        return {"added": added, "updated": updated, "total": len(normalized_cases)}

    def list_cases(self) -> list[Case]:
        """List active cases."""
        statement = select(Case).where(Case.is_active.is_(True)).order_by(Case.missing_since.desc())
        return list(self.db.scalars(statement).all())

    def stats(self) -> dict:
        """Return simple aggregate stats for dashboard and exports."""
        total = self.db.scalar(select(func.count()).select_from(Case).where(Case.is_active.is_(True))) or 0
        high_risk = (
            self.db.scalar(
                select(func.count()).select_from(Case).where(
                    Case.is_active.is_(True),
                    Case.status.in_(HIGH_RISK_STATUSES),
                )
            )
            or 0
        )
        return {"total": total, "high_risk": high_risk}
