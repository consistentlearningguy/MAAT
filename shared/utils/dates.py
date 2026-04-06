"""Date helpers shared across exporters, services, and tests."""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime | None) -> datetime | None:
    """Normalize a datetime to UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def isoformat(value: datetime | None) -> str | None:
    """Convert a datetime to ISO 8601."""
    normalized = ensure_utc(value)
    return normalized.isoformat() if normalized else None


def days_between(start: datetime | None, end: datetime | None) -> int | None:
    """Return whole-day difference between two datetimes."""
    left = ensure_utc(start)
    right = ensure_utc(end)
    if left is None or right is None:
        return None
    return max(0, int((right - left).total_seconds() // 86400))
