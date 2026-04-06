"""Optional investigator-mode orchestration."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.enrichment.official_context import extract_official_context
from backend.models.case import Case
from backend.models.investigation import InvestigationRun, Lead, SearchQueryLog
from backend.osint.aggregation import merge_normalized_leads
from backend.osint.connectors.registry import enabled_connectors
from backend.osint.normalization.models import QueryContext
from backend.osint.scoring.lead_scoring import score_lead


class InvestigationService:
    """Runs configured connectors and persists normalized leads."""

    def __init__(self, db: Session):
        self.db = db

    async def run_for_case(self, case_id: int) -> InvestigationRun:
        """Run all enabled connectors for a case."""
        case = self.db.get(Case, case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found.")

        connectors = enabled_connectors()
        run = InvestigationRun(
            case_id=case.id,
            status="running",
            connector_names=[connector.metadata.name for connector in connectors],
            feature_flags=settings.feature_flags,
            facts_summary="Official facts from MCSC/public police resources only.",
            inference_summary="Leads below are unverified and require analyst review before any action.",
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        official_context = extract_official_context(
            case.official_summary_html,
            city=case.city,
            province=case.province,
        )
        query_context = QueryContext(
            case_id=case.id,
            name=case.name or "",
            aliases=case.aliases or [],
            city=case.city,
            province=case.province,
            age=case.age,
            missing_since=case.missing_since,
            location_text=official_context.get("location_text"),
            authority_name=case.authority_name,
            authority_case_url=case.authority_case_url,
            case_reference_url=(
                f"{settings.mcsc_feature_server_url}/query?where=objectid%3D{case.id}&outFields=*"
                "&returnGeometry=true&f=json"
            ),
            source_urls=[
                value
                for value in [case.authority_case_url, case.source_url, *(record.source_url for record in case.source_records)]
                if value
            ],
            image_urls=[photo.url for photo in case.photos if photo.url],
        )

        collected_leads = []
        connector_failures = []

        try:
            for connector in connectors:
                try:
                    result = await connector.run(query_context)
                except Exception as exc:
                    connector_failures.append(f"{connector.metadata.name}: {exc}")
                    run.query_logs.append(
                        SearchQueryLog(
                            connector_name=connector.metadata.name,
                            source_kind=connector.metadata.source_kind,
                            query_used="[connector invocation]",
                            status="failed",
                            notes=str(exc),
                            completed_at=datetime.now(timezone.utc),
                        )
                    )
                    continue

                if result.warning:
                    run.query_logs.append(
                        SearchQueryLog(
                            connector_name=connector.metadata.name,
                            source_kind=connector.metadata.source_kind,
                            query_used="[connector warning]",
                            status="warning",
                            notes=result.warning,
                            completed_at=datetime.now(timezone.utc),
                        )
                    )

                for query_log in result.query_logs:
                    run.query_logs.append(
                        SearchQueryLog(
                            connector_name=query_log["connector_name"],
                            source_kind=query_log["source_kind"],
                            query_used=query_log["query_used"],
                            status=query_log.get("status", "completed"),
                            http_status=query_log.get("http_status"),
                            result_count=query_log.get("result_count", 0),
                            notes=query_log.get("notes"),
                            completed_at=datetime.now(timezone.utc),
                        )
                    )

                collected_leads.extend(result.leads)

            normalized_leads = merge_normalized_leads(collected_leads)
            for normalized in normalized_leads:
                scored = score_lead(case, normalized)
                run.leads.append(
                    Lead(
                        case_id=case.id,
                        lead_type=normalized.lead_type,
                        category=normalized.category,
                        source_kind=normalized.source_kind,
                        source_name=normalized.source_name,
                        source_url=normalized.source_url,
                        query_used=normalized.query_used,
                        title=normalized.title,
                        summary=normalized.summary,
                        content_excerpt=normalized.content_excerpt,
                        published_at=normalized.published_at,
                        found_at=normalized.found_at,
                        location_text=normalized.location_text,
                        latitude=normalized.latitude,
                        longitude=normalized.longitude,
                        confidence=scored.score,
                        source_trust=normalized.source_trust,
                        corroboration_count=normalized.corroboration_count,
                        rationale=scored.rationale,
                        human_reason="Generated by optional investigator-mode connectors.",
                    )
                )

            if connector_failures and normalized_leads:
                run.status = "completed_with_warnings"
            elif connector_failures and not normalized_leads:
                run.status = "failed"
            else:
                run.status = "completed"

            run.inference_summary = (
                f"{len(normalized_leads)} deduplicated lead(s) across {len(run.query_logs)} query log entries. "
                "All leads remain unverified until manually reviewed."
            )
            if connector_failures:
                run.error_message = " | ".join(connector_failures)

            run.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(run)
            return run
        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            run.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            raise
