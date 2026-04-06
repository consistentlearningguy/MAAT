"""Timeline and age enrichment for public exports."""

from __future__ import annotations

from datetime import datetime, timezone

from shared.utils.dates import days_between


def build_timeline(
    missing_since: datetime | None,
    updated_at: datetime | None,
    age: int | None,
) -> dict:
    """Build timeline fields for the public dashboard."""
    now = datetime.now(timezone.utc)
    elapsed_days = days_between(missing_since, now)
    estimated_current_age = age
    if age is not None and missing_since is not None and elapsed_days is not None:
        estimated_current_age = age + int(elapsed_days // 365)

    entries = []
    if missing_since:
        entries.append(
            {
                "label": "Official disappearance date",
                "date": missing_since.isoformat(),
                "kind": "official",
            }
        )
    if updated_at:
        entries.append(
            {
                "label": "Latest public update",
                "date": updated_at.isoformat(),
                "kind": "official",
            }
        )
    if elapsed_days is not None:
        entries.append(
            {
                "label": "Elapsed time since disappearance",
                "date": now.isoformat(),
                "kind": "derived",
                "value": elapsed_days,
            }
        )

    return {
        "elapsed_days": elapsed_days,
        "estimated_current_age": estimated_current_age,
        "timeline_entries": entries,
    }
