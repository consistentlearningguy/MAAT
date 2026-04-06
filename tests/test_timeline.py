from datetime import datetime, timedelta, timezone

from backend.enrichment.timeline import build_timeline


def test_build_timeline_returns_elapsed_and_estimated_age():
    missing_since = datetime.now(timezone.utc) - timedelta(days=370)
    updated_at = datetime.now(timezone.utc)

    timeline = build_timeline(missing_since, updated_at, 14)

    assert timeline["elapsed_days"] >= 370
    assert timeline["estimated_current_age"] == 15
    assert len(timeline["timeline_entries"]) == 3
