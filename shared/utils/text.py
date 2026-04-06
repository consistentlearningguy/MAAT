"""Text helpers shared across scoring and exports."""

from __future__ import annotations

import re


def slugify(value: str) -> str:
    """Build a URL-safe slug."""
    lowered = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return lowered.strip("-") or "case"


def normalize_whitespace(value: str | None) -> str:
    """Collapse repeated whitespace."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def token_similarity(left: str, right: str) -> float:
    """Lightweight token-overlap similarity for transparent fuzzy matching."""
    left_tokens = {token for token in re.split(r"[^a-z0-9]+", left.lower()) if token}
    right_tokens = {token for token in re.split(r"[^a-z0-9]+", right.lower()) if token}
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    universe = len(left_tokens | right_tokens)
    return round(overlap / universe, 3)
