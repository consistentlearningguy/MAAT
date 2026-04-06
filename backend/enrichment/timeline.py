"""Timeline and age enrichment for public exports."""

from __future__ import annotations

from datetime import datetime, timezone

from shared.utils.dates import days_between


def build_timeline(
    missing_since: datetime | None,
    updated_at: datetime | None,
    age: int | None,
    leads: list[dict] | None = None,
) -> dict:
    """Build timeline fields for the public dashboard.

    When *leads* are supplied the timeline will include source-attributed
    entries derived from investigation data in addition to the official
    anchor dates.
    """
    now = datetime.now(timezone.utc)
    elapsed_days = days_between(missing_since, now)
    estimated_current_age = age
    if age is not None and missing_since is not None and elapsed_days is not None:
        estimated_current_age = age + int(elapsed_days // 365)

    entries: list[dict] = []
    if missing_since:
        entries.append(
            {
                "label": "Official disappearance date",
                "date": missing_since.isoformat(),
                "kind": "official",
                "source_name": "Missing Children Society of Canada",
                "source_url": None,
            }
        )
    if updated_at:
        entries.append(
            {
                "label": "Latest official case update",
                "date": updated_at.isoformat(),
                "kind": "official",
                "source_name": "MCSC / Investigating Authority",
                "source_url": None,
            }
        )

    # Lead-derived timeline events (source-attributed)
    if leads:
        seen_urls: set[str] = set()
        for lead in sorted(leads, key=lambda x: x.get("published_at") or "9999"):
            pub = lead.get("published_at")
            if not pub:
                continue
            url = lead.get("source_url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)

            conf = lead.get("confidence", 0)
            if conf < 0.3:
                continue

            kind = "news"
            cat = (lead.get("category") or "").lower()
            source_kind = (lead.get("source_kind") or "").lower()
            title_lower = (lead.get("title") or "").lower()

            if "official" in cat or "police" in cat or "rcmp" in title_lower:
                kind = "official"
            elif "sighting" in title_lower or "seen" in title_lower:
                kind = "sighting"
            elif "archive" in source_kind or "wayback" in source_kind:
                kind = "archive"
            elif "social" in cat or "reddit" in source_kind:
                kind = "social"

            entries.append(
                {
                    "label": lead.get("title") or "Lead activity",
                    "date": pub,
                    "kind": kind,
                    "source_name": lead.get("source_name"),
                    "source_url": url or None,
                    "confidence": conf,
                    "lead_id": lead.get("id"),
                }
            )

    if elapsed_days is not None:
        entries.append(
            {
                "label": "Elapsed time since disappearance",
                "date": now.isoformat(),
                "kind": "derived",
                "value": elapsed_days,
                "source_name": None,
                "source_url": None,
            }
        )

    entries.sort(key=lambda e: e.get("date", ""))

    return {
        "elapsed_days": elapsed_days,
        "estimated_current_age": estimated_current_age,
        "timeline_entries": entries,
    }
