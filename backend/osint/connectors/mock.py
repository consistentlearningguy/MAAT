"""Mock connector used for tests and local demos."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.core.config import settings
from backend.osint.connectors.base import ConnectorMetadata
from backend.osint.normalization.models import ConnectorRunResult, NormalizedLead, QueryContext


class MockConnector:
    """Connector that returns deterministic demo leads."""

    metadata = ConnectorMetadata(
        name="mock-public-search",
        source_kind="clear-web",
        disabled_by_default=True,
        description="Test connector that emits deterministic public-search results when explicitly enabled.",
    )

    def enabled(self) -> bool:
        return bool(settings.enable_mock_connector)

    async def run(self, context: QueryContext) -> ConnectorRunResult:
        lead = NormalizedLead(
            connector_name=self.metadata.name,
            source_kind=self.metadata.source_kind,
            lead_type="web-mention",
            category="clear-web-search",
            source_name="Mock Search",
            source_url=f"https://example.org/search?q={context.name.replace(' ', '+')}",
            query_used=f'"{context.name}" {context.city or ""}'.strip(),
            found_at=datetime.now(timezone.utc),
            title=f"Demo search result for {context.name}",
            summary="Deterministic result used for local verification of normalization and scoring.",
            content_excerpt="This is not a live lead. It verifies connector isolation and graceful degradation.",
            source_trust=0.2,
            rationale=["Mock connector result for tests and offline development."],
        )
        return ConnectorRunResult(
            leads=[lead],
            query_logs=[
                {
                    "connector_name": self.metadata.name,
                    "source_kind": self.metadata.source_kind,
                    "query_used": lead.query_used,
                    "status": "completed",
                    "http_status": 200,
                    "result_count": 1,
                }
            ],
        )
