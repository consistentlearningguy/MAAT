"""Resource overlay helpers."""

from __future__ import annotations

from shared.constants.provinces import PROVINCE_REPORTING_RESOURCES


def resource_links_for_province(province: str | None) -> list[dict]:
    """Return official resource links for a province."""
    if not province:
        return []
    return list(PROVINCE_REPORTING_RESOURCES.get(province, []))
