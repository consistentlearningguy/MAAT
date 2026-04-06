"""Lead consolidation helpers for investigator-mode runs."""

from __future__ import annotations

from dataclasses import replace
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from backend.osint.normalization.models import NormalizedLead

_TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _normalize_url(value: str) -> str:
    parts = urlsplit((value or "").strip())
    filtered_query = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_PARAMS
    ]
    normalized_query = urlencode(sorted(filtered_query))
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/"),
            normalized_query,
            "",
        )
    )


def lead_identity_key(lead: NormalizedLead) -> tuple[str, str, str]:
    """Return a stable identity key for cross-query and cross-connector dedupe."""

    return (
        _normalize_url(lead.source_url),
        _normalize_text(lead.title),
        _normalize_text(lead.location_text),
    )


def merge_normalized_leads(leads: list[NormalizedLead]) -> list[NormalizedLead]:
    """Merge duplicate leads while preserving analyst-facing rationale."""

    merged: dict[tuple[str, str, str], NormalizedLead] = {}
    occurrences: dict[tuple[str, str, str], int] = {}

    for lead in leads:
        key = lead_identity_key(lead)
        if key not in merged:
            merged[key] = replace(lead, rationale=list(lead.rationale))
            occurrences[key] = 1
            continue

        current = merged[key]
        occurrences[key] += 1

        current.source_trust = max(current.source_trust, lead.source_trust)
        current.corroboration_count = max(current.corroboration_count, lead.corroboration_count, occurrences[key])
        current.found_at = max(current.found_at, lead.found_at)

        if lead.published_at and (current.published_at is None or lead.published_at > current.published_at):
            current.published_at = lead.published_at
        if not current.location_text and lead.location_text:
            current.location_text = lead.location_text
        if len(lead.summary or "") > len(current.summary or ""):
            current.summary = lead.summary
        if len(lead.content_excerpt or "") > len(current.content_excerpt or ""):
            current.content_excerpt = lead.content_excerpt

        for reason in lead.rationale:
            if reason not in current.rationale:
                current.rationale.append(reason)

        duplicate_reason = "Observed across multiple public query variants or connectors."
        if duplicate_reason not in current.rationale:
            current.rationale.append(duplicate_reason)

    return list(merged.values())
