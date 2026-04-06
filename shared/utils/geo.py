"""Geo helpers for lightweight static-first enrichment."""

from __future__ import annotations

from math import atan2, cos, radians, sin, sqrt


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute the distance between two coordinates in kilometers."""
    radius_km = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return round(radius_km * c, 2)


def nearest_points(
    origin_lat: float | None,
    origin_lon: float | None,
    points: list[dict],
    limit: int = 3,
) -> list[dict]:
    """Return the nearest reference points to an origin."""
    if origin_lat is None or origin_lon is None:
        return []

    ranked = []
    for point in points:
        if point.get("latitude") is None or point.get("longitude") is None:
            continue
        distance = haversine_km(
            origin_lat,
            origin_lon,
            float(point["latitude"]),
            float(point["longitude"]),
        )
        ranked.append({**point, "distance_km": distance})

    ranked.sort(key=lambda item: item["distance_km"])
    return ranked[:limit]
