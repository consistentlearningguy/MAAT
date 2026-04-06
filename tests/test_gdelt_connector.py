import asyncio
from datetime import datetime, timezone

from backend.core.config import settings
from backend.osint.connectors.gdelt import GdeltDocConnector
from backend.osint.normalization.models import QueryContext


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeAsyncClient:
    def __init__(self):
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, params=None, headers=None):
        self.calls += 1
        query = params["query"]
        return FakeResponse(
            {
                "articles": [
                    {
                        "url": "https://news.example.org/story-one",
                        "title": f"{query} article",
                        "domain": "news.example.org",
                        "language": "English",
                        "seendate": "20260316T101500Z",
                        "sourcecountry": "Canada",
                    }
                ]
            }
        )


async def _no_sleep():
    return None


def test_gdelt_connector_normalizes_news_articles_and_deduplicates(monkeypatch):
    old_clear_web = settings.enable_clear_web_connectors
    settings.enable_clear_web_connectors = True
    monkeypatch.setattr("backend.osint.connectors.gdelt.rate_limit_sleep", _no_sleep)

    try:
        connector = GdeltDocConnector(client_factory=lambda timeout: FakeAsyncClient())
        context = QueryContext(
            case_id=1,
            name="Sample Case Toronto",
            aliases=["SCT"],
            city="Toronto",
            province="Ontario",
            age=14,
            missing_since=datetime(2026, 3, 14, tzinfo=timezone.utc),
            image_urls=[],
        )

        result = asyncio.run(connector.run(context))
    finally:
        settings.enable_clear_web_connectors = old_clear_web

    assert len(result.leads) == 1
    lead = result.leads[0]
    assert lead.category == "news-monitoring"
    assert lead.source_url == "https://news.example.org/story-one"
    assert lead.published_at == datetime(2026, 3, 16, 10, 15, tzinfo=timezone.utc)
    assert any(log["status"] == "completed" for log in result.query_logs)
    assert any("missing" in log["query_used"] or "last seen" in log["query_used"] for log in result.query_logs)
