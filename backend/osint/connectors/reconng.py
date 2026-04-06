"""Recon-ng adapter scaffold."""

from __future__ import annotations

from backend.core.config import settings
from backend.osint.connectors.base import ConnectorMetadata
from backend.osint.normalization.models import ConnectorRunResult, QueryContext


class ReconNgConnector:
    """Optional experimental scaffold for Recon-ng."""

    metadata = ConnectorMetadata(
        name="recon-ng",
        source_kind="clear-web",
        disabled_by_default=True,
        unstable=True,
        description="Investigator-only scaffold for legacy Recon-ng workflows.",
    )

    def enabled(self) -> bool:
        return bool(
            settings.enable_investigator_mode
            and settings.enable_clear_web_connectors
            and settings.enable_experimental_connectors
            and settings.reconng_binary
        )

    async def run(self, context: QueryContext) -> ConnectorRunResult:
        return ConnectorRunResult(
            warning="Recon-ng is treated as legacy/experimental. Scaffold only; no default runtime integration."
        )
