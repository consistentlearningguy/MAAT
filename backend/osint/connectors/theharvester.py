"""theHarvester adapter scaffold."""

from __future__ import annotations

from backend.core.config import settings
from backend.osint.connectors.base import ConnectorMetadata
from backend.osint.normalization.models import ConnectorRunResult, QueryContext


class TheHarvesterConnector:
    """Optional external-process scaffold for theHarvester."""

    metadata = ConnectorMetadata(
        name="theharvester",
        source_kind="clear-web",
        disabled_by_default=True,
        description="Optional investigator-only CLI adapter. Use selectively and normalize only lawful public results.",
    )

    def enabled(self) -> bool:
        return bool(settings.enable_investigator_mode and settings.enable_clear_web_connectors and settings.theharvester_binary)

    async def run(self, context: QueryContext) -> ConnectorRunResult:
        return ConnectorRunResult(
            warning=(
                "theHarvester adapter scaffold only. Enable with an explicit binary path and "
                "filter results so cyber/domain-centric output does not leak into public workflows."
            )
        )
