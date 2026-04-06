"""Helpers for extracting structured anchors from official case summaries."""

from __future__ import annotations

from html import unescape
import re

from shared.constants.provinces import PROVINCE_LABELS
from shared.utils.text import normalize_whitespace

FIELD_ALIASES = {
    "missing since": "missing_since_text",
    "location": "location_text",
    "age": "age_text",
    "height": "height",
    "weight": "weight",
    "hair color": "hair_color",
    "eye color": "eye_color",
    "last seen wearing": "last_seen_wearing",
    "circumstances": "circumstances",
}


def _canonical_province_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}

    def _push(key: str, value: str) -> None:
        normalized = re.sub(r"[^A-Z]", "", key.upper())
        if normalized:
            lookup[normalized] = value

    for code, label in PROVINCE_LABELS.items():
        _push(code, label)
        _push(label, label)

    for label in set(PROVINCE_LABELS.values()):
        _push(label, label)

    return lookup


PROVINCE_LOOKUP = _canonical_province_lookup()


def _summary_lines(summary_html: str | None) -> list[str]:
    text = summary_html or ""
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>|</div>|</li>|</tr>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return [
        normalize_whitespace(line)
        for line in text.splitlines()
        if normalize_whitespace(line)
    ]


def _extract_fields(lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in lines:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized_key = normalize_whitespace(key).strip().lower()
        target_key = FIELD_ALIASES.get(normalized_key)
        cleaned_value = normalize_whitespace(value)
        if target_key and cleaned_value and target_key not in fields:
            fields[target_key] = cleaned_value
    return fields


def _infer_province(location_text: str | None) -> str | None:
    if not location_text:
        return None

    parts = [normalize_whitespace(part).strip(" ,.") for part in location_text.split(",")]
    for part in reversed(parts):
        normalized = re.sub(r"[^A-Z]", "", part.upper())
        if normalized in PROVINCE_LOOKUP:
            return PROVINCE_LOOKUP[normalized]

    tokens = re.findall(r"[A-Za-z.]+", location_text)
    for token in reversed(tokens):
        normalized = re.sub(r"[^A-Z]", "", token.upper())
        if normalized in PROVINCE_LOOKUP:
            return PROVINCE_LOOKUP[normalized]

    return None


def _infer_city(location_text: str | None, current_city: str | None) -> str | None:
    if current_city and location_text and current_city.lower() in location_text.lower():
        return current_city
    if not location_text:
        return current_city

    parts = [normalize_whitespace(part).strip(" ,.") for part in location_text.split(",") if normalize_whitespace(part)]
    if len(parts) >= 2 and _infer_province(parts[-1]):
        return parts[-2]
    if len(parts) >= 1 and current_city:
        return current_city
    return current_city or None


def extract_official_context(
    summary_html: str | None,
    *,
    city: str | None = None,
    province: str | None = None,
) -> dict[str, object]:
    """Extract structured anchors from an official case summary."""

    lines = _summary_lines(summary_html)
    fields = _extract_fields(lines)
    location_text = fields.get("location_text")
    inferred_province = _infer_province(location_text) or province
    inferred_city = _infer_city(location_text, city)

    descriptors = [
        f"Height {fields['height']}" if fields.get("height") else None,
        f"Weight/build {fields['weight']}" if fields.get("weight") else None,
        f"Hair {fields['hair_color']}" if fields.get("hair_color") else None,
        f"Eyes {fields['eye_color']}" if fields.get("eye_color") else None,
        f"Clothing {fields['last_seen_wearing']}" if fields.get("last_seen_wearing") else None,
    ]

    quality_warnings: list[str] = []
    if province and inferred_province and province != inferred_province:
        quality_warnings.append(
            f"ArcGIS province field says {province}, but the official summary location points to {inferred_province}."
        )
    if city and inferred_city and city != inferred_city and city.lower() not in (location_text or "").lower():
        quality_warnings.append(
            f"Structured city field says {city}, but the parsed summary location looks closer to {inferred_city}."
        )

    return {
        "summary_lines": lines,
        "fields": fields,
        "location_text": location_text,
        "missing_since_text": fields.get("missing_since_text"),
        "inferred_city": inferred_city,
        "inferred_province": inferred_province,
        "descriptor_chips": [value for value in descriptors if value],
        "quality_warnings": quality_warnings,
    }
