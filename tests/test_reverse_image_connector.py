import asyncio
import json

from backend.core.config import settings
from backend.osint.connectors.reverse_image import ReverseImageConnector
from backend.osint.normalization.models import QueryContext


def test_reverse_image_connector_creates_attributable_sources(tmp_path):
    fixture = tmp_path / "reverse_image_mock.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "image_url": "https://example.org/case-photo.jpg",
                    "source_name": "Mock Public Image Index",
                    "source_url": "https://public.example.org/match",
                    "title": "Public image match",
                    "summary": "Public image result with a reviewable source URL.",
                    "published_at": "2026-03-18T19:00:00Z",
                    "location_text": "Toronto, Ontario",
                    "source_trust": 0.55,
                    "rationale": ["Provider returned a visually similar result."],
                }
            ]
        ),
        encoding="utf-8",
    )

    old_investigator = settings.enable_investigator_mode
    old_reverse = settings.enable_reverse_image_hooks
    settings.enable_investigator_mode = True
    settings.enable_reverse_image_hooks = True

    try:
        connector = ReverseImageConnector(provider_mode="mock", mock_file=fixture)
        context = QueryContext(
            case_id=1,
            name="Sample Case Toronto",
            aliases=[],
            city="Toronto",
            province="Ontario",
            age=14,
            missing_since=None,
            image_urls=["https://example.org/case-photo.jpg"],
        )
        result = asyncio.run(connector.run(context))
    finally:
        settings.enable_investigator_mode = old_investigator
        settings.enable_reverse_image_hooks = old_reverse

    assert len(result.leads) == 1
    assert result.leads[0].source_url == "https://public.example.org/match"
    assert result.leads[0].query_used == "https://example.org/case-photo.jpg"
    assert result.leads[0].rationale
    assert result.query_logs[0]["result_count"] == 1
