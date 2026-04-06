"""Simple geospatial enrichment using bundled public reference layers."""

from __future__ import annotations

import json
from pathlib import Path

from backend.core.config import settings
from shared.utils.geo import nearest_points


def _load_reference_file(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def build_geo_context(latitude: float | None, longitude: float | None) -> list[dict]:
    """Build nearby public reference context."""
    if latitude is None or longitude is None:
        return []

    overlays = {
        "airport": _load_reference_file(settings.reference_dir / "airports.json"),
        "border-crossing": _load_reference_file(settings.reference_dir / "border_crossings.json"),
        "highway": _load_reference_file(settings.reference_dir / "highways.json"),
        "youth-service": _load_reference_file(settings.reference_dir / "youth_services.json"),
    }

    context = []
    for context_type, entries in overlays.items():
        for item in nearest_points(latitude, longitude, entries, limit=1):
            context.append(
                {
                    "context_type": context_type,
                    "label": item["label"],
                    "latitude": item.get("latitude"),
                    "longitude": item.get("longitude"),
                    "distance_km": item.get("distance_km"),
                    "source_url": item.get("source_url"),
                    "jurisdiction": item.get("jurisdiction"),
                    "metadata_json": item.get("metadata_json", {}),
                }
            )
    return sorted(context, key=lambda item: item.get("distance_km") or 9999)

