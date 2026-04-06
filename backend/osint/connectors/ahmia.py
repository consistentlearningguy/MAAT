"""Optional Ahmia connector for lawful onion indexing/search results."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx

from backend.core.config import settings
from backend.osint.connectors.base import ConnectorMetadata, rate_limit_sleep
from backend.osint.normalization.models import ConnectorRunResult, NormalizedLead, QueryContext


class AhmiaConnector:
    """Lawful onion index/search connector."""

    metadata = ConnectorMetadata(
        name="ahmia",
        source_kind="dark-web-capable",
        disabled_by_default=True,
        description="Lawful index/search-only connector via Ahmia. No crawling or access guidance.",
    )

    def enabled(self) -> bool:
        return bool(settings.enable_dark_web_connectors)

    async def run(self, context: QueryContext) -> ConnectorRunResult:
        if not self.enabled():
            return ConnectorRunResult(warning="Ahmia connector disabled by feature flag.")

        query = f'"{context.name}" {context.city or ""}'.strip()
        search_url = f"{settings.ahmia_search_url}?{urlencode({'q': query})}"

        async with httpx.AsyncClient(timeout=settings.connector_timeout_seconds) as client:
            response = await client.get(search_url)
            response.raise_for_status()
            text = response.text
        await rate_limit_sleep()

        leads = []
        for line in text.splitlines():
            if "result" not in line.lower() or "<a" not in line.lower():
                continue
            leads.append(
                NormalizedLead(
                    connector_name=self.metadata.name,
                    source_kind=self.metadata.source_kind,
                    lead_type="indexed-reference",
                    category="dark-web-indexing",
                    source_name="Ahmia",
                    source_url=search_url,
                    query_used=query,
                    found_at=datetime.now(timezone.utc),
                    title="Ahmia indexed result",
                    summary="Lawful onion-search index result captured for analyst review.",
                    content_excerpt="Review manually in investigator mode before treating as meaningful.",
                    source_trust=0.2,
                    rationale=["Indexed result from Ahmia search. Unverified and disabled by default."],
                )
            )
            if len(leads) >= 5:
                break

        return ConnectorRunResult(
            leads=leads,
            query_logs=[
                {
                    "connector_name": self.metadata.name,
                    "source_kind": self.metadata.source_kind,
                    "query_used": query,
                    "status": "completed",
                    "http_status": response.status_code,
                    "result_count": len(leads),
                    "notes": "Index/search-only connector. No direct onion navigation required.",
                }
            ],
        )
