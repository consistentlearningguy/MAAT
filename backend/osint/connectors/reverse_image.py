"""Provider-based reverse image hook connector."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from backend.core.config import settings
from backend.osint.connectors.base import ConnectorMetadata, rate_limit_sleep
from backend.osint.normalization.models import ConnectorRunResult, NormalizedLead, QueryContext


class ReverseImageConnector:
    """Lawful reverse-image workflow hook.

    This connector does not attempt exhaustive social-media coverage and does not scrape
    behind logins. It only normalizes results from explicitly configured providers or
    the bundled mock fixture.
    """

    metadata = ConnectorMetadata(
        name="reverse-image-hook",
        source_kind="clear-web",
        disabled_by_default=True,
        description="Provider-based reverse-image hook for lawful public results with source attribution.",
    )

    def __init__(
        self,
        provider_mode: str | None = None,
        provider_url: str | None = None,
        mock_file: str | Path | None = None,
    ):
        self.provider_mode = provider_mode if provider_mode is not None else settings.reverse_image_provider_mode
        self.provider_url = provider_url if provider_url is not None else settings.reverse_image_provider_url
        resolved_mock = mock_file if mock_file is not None else settings.reverse_image_mock_file
        self.mock_file = Path(resolved_mock)

    def enabled(self) -> bool:
        return bool(settings.enable_investigator_mode and settings.enable_reverse_image_hooks)

    def _load_mock_matches(self) -> list[dict]:
        if not self.mock_file.exists():
            return []
        return json.loads(self.mock_file.read_text(encoding="utf-8-sig"))

    async def _fetch_provider_matches(self, image_url: str) -> list[dict]:
        if self.provider_mode == "mock" or not self.provider_url:
            return [item for item in self._load_mock_matches() if item.get("image_url") == image_url]

        async with httpx.AsyncClient(timeout=settings.connector_timeout_seconds) as client:
            response = await client.get(self.provider_url, params={"image_url": image_url})
            response.raise_for_status()
            payload = response.json()
        await rate_limit_sleep()
        return payload.get("matches", [])

    async def run(self, context: QueryContext) -> ConnectorRunResult:
        if not self.enabled():
            return ConnectorRunResult(warning="Reverse-image hooks are disabled by feature flag.")
        if not context.image_urls:
            return ConnectorRunResult(warning="No case photos are available for reverse-image lookup.")

        leads = []
        query_logs = []

        for image_url in context.image_urls:
            matches = await self._fetch_provider_matches(image_url)
            query_logs.append(
                {
                    "connector_name": self.metadata.name,
                    "source_kind": self.metadata.source_kind,
                    "query_used": image_url,
                    "status": "completed",
                    "http_status": 200,
                    "result_count": len(matches),
                    "notes": "Provider-based reverse-image hook. Not exhaustive social-media coverage.",
                }
            )
            for match in matches:
                leads.append(
                    NormalizedLead(
                        connector_name=self.metadata.name,
                        source_kind=self.metadata.source_kind,
                        lead_type="reverse-image-match",
                        category="reverse-image",
                        source_name=match.get("source_name", "Reverse image provider"),
                        source_url=match["source_url"],
                        query_used=image_url,
                        found_at=datetime.now(timezone.utc),
                        title=match.get("title", "Reverse image match"),
                        summary=match.get("summary", "Public image match returned by configured provider."),
                        content_excerpt=f"Matched case image URL: {image_url}",
                        published_at=(datetime.fromisoformat(match["published_at"].replace("Z", "+00:00")) if match.get("published_at") else None),
                        location_text=match.get("location_text"),
                        source_trust=float(match.get("source_trust", 0.4)),
                        rationale=[
                            "Result came from an explicitly configured reverse-image provider.",
                            "Source URL and image query were captured for analyst review.",
                            *match.get("rationale", []),
                        ],
                    )
                )

        return ConnectorRunResult(leads=leads, query_logs=query_logs)

