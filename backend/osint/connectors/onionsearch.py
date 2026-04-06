"""OnionSearch experimental scaffold."""

from __future__ import annotations

from backend.core.config import settings
from backend.osint.connectors.base import ConnectorMetadata
from backend.osint.normalization.models import ConnectorRunResult, QueryContext


class OnionSearchConnector:
    """Experimental connector kept isolated and disabled by default."""

    metadata = ConnectorMetadata(
        name="onionsearch",
        source_kind="dark-web-capable",
        disabled_by_default=True,
        unstable=True,
        description="Experimental index/search adapter isolated behind feature flags.",
    )

    def enabled(self) -> bool:
        return bool(
            settings.enable_investigator_mode
            and settings.enable_dark_web_connectors
            and settings.enable_experimental_connectors
            and settings.onionsearch_binary
        )

    async def run(self, context: QueryContext) -> ConnectorRunResult:
        return ConnectorRunResult(
            warning="OnionSearch is intentionally isolated as unstable/experimental and is not enabled in the default build."
        )
