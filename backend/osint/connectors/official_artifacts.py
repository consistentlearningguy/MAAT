"""Connector that turns official case anchors into attributable evidence leads."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.core.config import settings
from backend.osint.connectors.base import ConnectorMetadata
from backend.osint.normalization.models import ConnectorRunResult, NormalizedLead, QueryContext


class OfficialArtifactsConnector:
    """Emit stable official artifacts so new cases have usable baseline evidence."""

    metadata = ConnectorMetadata(
        name="official-artifacts",
        source_kind="official",
        disabled_by_default=False,
        description="Converts authority links, official photos, and parsed last-seen anchors into evidence leads.",
    )

    def enabled(self) -> bool:
        return bool(settings.enable_investigator_mode)

    async def run(self, context: QueryContext) -> ConnectorRunResult:
        if not self.enabled():
            return ConnectorRunResult(warning="Official artifact connector is disabled.")
        if not context.name:
            return ConnectorRunResult(warning="Case is missing a primary name, so no official artifacts could be emitted.")

        leads: list[NormalizedLead] = []
        query_logs: list[dict[str, object]] = []
        found_at = datetime.now(timezone.utc)
        source_name = context.authority_name or "Official authority"
        published_at = context.missing_since
        primary_record_url = context.authority_case_url or context.case_reference_url or (context.source_urls[0] if context.source_urls else "")

        def add_lead(lead: NormalizedLead) -> None:
            leads.append(lead)

        if primary_record_url:
            add_lead(
                NormalizedLead(
                    connector_name=self.metadata.name,
                    source_kind=self.metadata.source_kind,
                    lead_type="official-bulletin",
                    category="official-anchor",
                    source_name=source_name,
                    source_url=primary_record_url,
                    query_used=primary_record_url,
                    found_at=found_at,
                    title=f"Official public record for {context.name}",
                    summary=(
                        f"Official authority page, case record, or public post for {context.name}. "
                        "Use this as the baseline public artifact before pivoting outward."
                    ),
                    content_excerpt=context.location_text or "",
                    published_at=published_at,
                    location_text=context.location_text,
                    source_trust=1.0,
                    rationale=[
                        "Direct authority-owned URL or case-specific official record attached to the case.",
                        "Useful as a preserved anchor for screenshots, archives, and cross-checking public claims.",
                    ],
                )
            )

        if context.location_text:
            location_source = primary_record_url
            if location_source:
                add_lead(
                    NormalizedLead(
                        connector_name=self.metadata.name,
                        source_kind=self.metadata.source_kind,
                        lead_type="official-last-seen",
                        category="official-last-seen",
                        source_name=source_name,
                        source_url=location_source,
                        query_used=context.location_text,
                        found_at=found_at,
                        title=f"Official last-seen location for {context.name}",
                        summary="Location string extracted from the official case narrative.",
                        content_excerpt=context.location_text,
                        published_at=published_at,
                        location_text=context.location_text,
                        source_trust=1.0,
                        rationale=[
                            "Parsed from the official case summary.",
                            "Use this anchor to judge whether later public mentions actually advance the timeline.",
                        ],
                    )
                )

        for image_url in context.image_urls[:2]:
            add_lead(
                NormalizedLead(
                    connector_name=self.metadata.name,
                    source_kind=self.metadata.source_kind,
                    lead_type="official-photo",
                    category="official-photo",
                    source_name=source_name,
                    source_url=image_url,
                    query_used=image_url,
                    found_at=found_at,
                    title=f"Official case photo for {context.name}",
                    summary="Official case image suitable for reverse-image review and archive preservation.",
                    content_excerpt=image_url,
                    published_at=published_at,
                    location_text=context.location_text,
                    source_trust=1.0,
                    rationale=[
                        "Official image URL attached to the case record.",
                        "Useful as a seed artifact for reverse-image and archive workflows.",
                    ],
                )
            )

        query_logs.append(
            {
                "connector_name": self.metadata.name,
                "source_kind": self.metadata.source_kind,
                "query_used": "[official case artifacts]",
                "status": "completed",
                "http_status": 200,
                "result_count": len(leads),
                "notes": "Generated reviewable evidence artifacts directly from official case fields.",
            }
        )

        if not leads:
            return ConnectorRunResult(
                warning="No official record URL, official location, or official photo was available to build artifact leads.",
                query_logs=query_logs,
            )

        return ConnectorRunResult(leads=leads, query_logs=query_logs)
