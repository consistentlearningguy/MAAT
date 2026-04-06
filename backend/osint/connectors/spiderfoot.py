"""SpiderFoot adapter scaffold."""

from __future__ import annotations

from backend.core.config import settings
from backend.osint.connectors.base import ConnectorMetadata
from backend.osint.normalization.models import ConnectorRunResult, QueryContext


class SpiderfootConnector:
    """Adapter scaffold for investigator-managed SpiderFoot instances."""

    metadata = ConnectorMetadata(
        name="spiderfoot",
        source_kind="clear-web",
        disabled_by_default=True,
        description="Optional adapter scaffold for a separate SpiderFoot instance.",
    )

    def enabled(self) -> bool:
        return bool(settings.enable_clear_web_connectors and settings.spiderfoot_url and settings.enable_investigator_mode)

    async def run(self, context: QueryContext) -> ConnectorRunResult:
        return ConnectorRunResult(
            warning=(
                "SpiderFoot adapter scaffold only. Configure a separate SpiderFoot instance and "
                "map relevant public modules before enabling."
            )
        )
