"""Optional SearXNG connector for public search aggregation."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx

from backend.core.config import settings
from backend.osint.connectors.base import ConnectorMetadata, rate_limit_sleep
from backend.osint.normalization.models import ConnectorRunResult, NormalizedLead, QueryContext
from backend.osint.query_planner import build_investigator_query_plan


class SearxngConnector:
    """Public metasearch connector."""

    metadata = ConnectorMetadata(
        name="searxng",
        source_kind="clear-web",
        disabled_by_default=True,
        description="Optional metasearch aggregation through a configured SearXNG instance.",
    )

    def enabled(self) -> bool:
        return bool(settings.enable_clear_web_connectors and settings.searxng_url)

    async def run(self, context: QueryContext) -> ConnectorRunResult:
        if not self.enabled():
            return ConnectorRunResult(warning="SearXNG connector disabled or not configured.")

        query_plan = build_investigator_query_plan(context)
        if not query_plan:
            return ConnectorRunResult(
                warning="No reviewable Trace Labs-style public query variants could be built from the case facts."
            )

        leads: list[NormalizedLead] = []
        query_logs: list[dict] = []
        seen_urls: set[str] = set()

        async with httpx.AsyncClient(timeout=settings.connector_timeout_seconds) as client:
            for query in query_plan:
                params = {"q": query, "format": "json", "language": "en-CA"}
                request_url = f"{settings.searxng_url.rstrip('/')}/search?{urlencode(params)}"
                try:
                    response = await client.get(request_url)
                    response.raise_for_status()
                    payload = response.json()
                except Exception as exc:
                    query_logs.append(
                        {
                            "connector_name": self.metadata.name,
                            "source_kind": self.metadata.source_kind,
                            "query_used": query,
                            "status": "failed",
                            "http_status": getattr(getattr(exc, "response", None), "status_code", None),
                            "result_count": 0,
                            "notes": f"Query variant failed: {exc}",
                        }
                    )
                    continue

                await rate_limit_sleep()
                added = 0
                raw_items = payload.get("results", [])[:5]
                for item in raw_items:
                    source_url = item.get("url") or request_url
                    if source_url in seen_urls:
                        continue
                    seen_urls.add(source_url)
                    added += 1
                    leads.append(
                        NormalizedLead(
                            connector_name=self.metadata.name,
                            source_kind=self.metadata.source_kind,
                            lead_type="web-mention",
                            category="clear-web-search",
                            source_name=item.get("engine") or "SearXNG",
                            source_url=source_url,
                            query_used=query,
                            found_at=datetime.now(timezone.utc),
                            title=item.get("title") or "Untitled result",
                            summary=item.get("content") or "Public search result",
                            content_excerpt=item.get("content") or "",
                            source_trust=0.45,
                            rationale=[
                                "Matched through a configured SearXNG metasearch query.",
                                "Query planning included grouped public profile and timeline pivots.",
                                f"Observed under reviewable query variant: {query}",
                            ],
                        )
                    )

                query_logs.append(
                    {
                        "connector_name": self.metadata.name,
                        "source_kind": self.metadata.source_kind,
                        "query_used": query,
                        "status": "completed",
                        "http_status": response.status_code,
                        "result_count": added,
                        "notes": f"Query variant returned {len(raw_items)} raw results before dedupe.",
                    }
                )

        return ConnectorRunResult(leads=leads, query_logs=query_logs)
