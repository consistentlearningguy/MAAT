"""Lead scoring and confidence calculation.

This is the brain of the investigation system. It takes raw results from
the username search and web mention scanner, scores them by confidence,
and decides what's worth presenting to an analyst.

Scoring factors:
- Name uniqueness (rare names = higher confidence on matches)
- Platform relevance (TikTok/Instagram for teens > LinkedIn)
- Temporal relevance (post-disappearance activity > old content)
- Geographic relevance (mentions of nearby cities = higher value)
- Content relevance (mentions "missing", "seen", "sighting" = high value)
- Source reliability (news > random blog > anonymous forum)
"""

import re
from datetime import datetime, timezone, timedelta
from typing import Optional


# --- Name Uniqueness ---

# Common first names that produce false positives
COMMON_FIRST_NAMES = {
    "james", "john", "robert", "michael", "david", "william", "richard",
    "joseph", "thomas", "charles", "christopher", "daniel", "matthew",
    "anthony", "mark", "donald", "steven", "paul", "andrew", "joshua",
    "mary", "patricia", "jennifer", "linda", "barbara", "elizabeth",
    "susan", "jessica", "sarah", "karen", "lisa", "nancy", "betty",
    "margaret", "sandra", "ashley", "dorothy", "kimberly", "emily",
    "alex", "sam", "jordan", "taylor", "morgan", "casey", "jamie",
    "tyler", "dylan", "brandon", "justin", "ryan", "sean", "connor",
    "logan", "mason", "aiden", "ethan", "noah", "liam", "emma", "olivia",
    "sophia", "isabella", "mia", "charlotte", "amelia", "harper", "evelyn",
}


def name_uniqueness_score(name: str) -> float:
    """Score how unique a name is (0.0 = very common, 1.0 = very unique).
    
    More unique names have higher confidence when we find matches,
    because a "Talon Horton" match is far more likely to be the right
    person than a "Michael Smith" match.
    """
    if not name:
        return 0.0

    parts = name.strip().lower().split()
    if not parts:
        return 0.0

    first = parts[0]
    has_last = len(parts) > 1

    # Single name only
    if not has_last:
        return 0.1 if first in COMMON_FIRST_NAMES else 0.3

    # Common first name
    if first in COMMON_FIRST_NAMES:
        return 0.2  # Low confidence even with last name
    
    # Uncommon first name
    if len(first) >= 5 and first not in COMMON_FIRST_NAMES:
        return 0.7  # Unusual names are much more identifiable
    
    return 0.4  # Default for average names


# --- Username Hit Scoring ---

# Platforms most used by Canadian teens
TEEN_PLATFORM_WEIGHT = {
    "TikTok": 1.0,
    "Instagram": 1.0,
    "Snapchat": 0.95,
    "Twitter/X": 0.8,
    "YouTube": 0.7,
    "Reddit": 0.7,
    "Twitch": 0.7,
    "Roblox": 0.8,   # Younger teens
    "Steam": 0.6,
    "Discord": 0.8,
    "Facebook": 0.4,  # Less common for teens
    "Wattpad": 0.6,
    "SoundCloud": 0.5,
    "Tumblr": 0.4,
    "Pinterest": 0.3,
    "GitHub": 0.3,
    "LinkedIn": 0.1,  # Very unlikely for missing children
}


def score_username_hit(
    username: str,
    platform: str,
    person_name: str,
    person_age: Optional[int] = None,
) -> float:
    """Score a username hit.
    
    Considers:
    - How closely the username matches the person's name
    - How relevant the platform is for the person's age group
    - Name uniqueness (rare name match = higher confidence)
    """
    score = 0.0
    name_lower = person_name.strip().lower()
    parts = name_lower.split()
    username_lower = username.lower()

    # Base: name uniqueness (less weight so common names aren't capped too low)
    uniqueness = name_uniqueness_score(person_name)
    score += uniqueness * 0.25  # 25% weight on name uniqueness

    # Username-to-name match quality
    name_match = 0.0
    if len(parts) >= 2:
        first, last = parts[0], parts[-1]
        full = first + last

        if full == username_lower or f"{first}.{last}" == username_lower:
            name_match = 1.0  # Exact match
        elif first in username_lower and last in username_lower:
            name_match = 0.8  # Both parts present
        elif full in username_lower:
            name_match = 0.7  # Full name in username
        elif first in username_lower or last in username_lower:
            name_match = 0.3  # Partial match
    elif parts:
        if parts[0] == username_lower:
            name_match = 0.5
        elif parts[0] in username_lower:
            name_match = 0.2

    score += name_match * 0.40  # 40% weight on name match

    # Platform relevance
    platform_weight = TEEN_PLATFORM_WEIGHT.get(platform, 0.5)
    
    # Adjust for age
    if person_age is not None:
        if person_age <= 12:
            # Younger kids: Roblox, YouTube more relevant
            if platform in ("Roblox", "YouTube"):
                platform_weight = min(1.0, platform_weight + 0.2)
            elif platform in ("TikTok", "Twitter/X", "Reddit"):
                platform_weight = max(0.0, platform_weight - 0.2)
        elif person_age >= 16:
            # Older teens: Instagram, TikTok, Snapchat dominate
            if platform in ("Instagram", "TikTok", "Snapchat"):
                platform_weight = min(1.0, platform_weight + 0.1)

    score += platform_weight * 0.35  # 35% weight on platform

    return round(min(1.0, max(0.0, score)), 3)


# --- Web Mention Scoring ---

# Keywords that indicate high-value content
HIGH_VALUE_KEYWORDS = [
    "sighting", "spotted", "seen", "found", "located", "safe",
    "returned home", "recovered", "reunited",
]

MEDIUM_VALUE_KEYWORDS = [
    "missing", "disappeared", "search", "help find", "have you seen",
    "last seen", "amber alert", "police", "rcmp", "investigation",
]

LOCATION_KEYWORDS = [
    "was seen in", "spotted in", "last seen in", "heading to",
    "believed to be in", "may be in", "travelled to", "seen near",
]

# Source reliability
SOURCE_WEIGHT = {
    "google_news": 0.85,   # News articles are reliable
    "reddit": 0.5,         # Mixed — can be useful but also noise
    "duckduckgo": 0.4,     # General web — lowest baseline
}


def _ensure_utc_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize a datetime to UTC-aware.
    
    Fixes the timezone mismatch between SQLite (naive) and web sources (aware).
    SQLite stores datetimes without timezone info, but Google News/Reddit
    return timezone-aware datetimes. Subtracting the two raises TypeError.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def score_web_mention(
    title: str,
    content: str,
    source: str,
    content_date: Optional[datetime] = None,
    missing_since: Optional[datetime] = None,
    person_name: str = "",
    city: Optional[str] = None,
    province: Optional[str] = None,
) -> float:
    """Score a web mention for relevance and actionability.
    
    High scores = likely actionable intelligence
    Low scores = probably just a news article repeating known info
    """
    score = 0.0
    text = (title + " " + content).lower()
    name_lower = person_name.strip().lower()

    # Normalize datetimes to avoid tz-aware vs tz-naive comparison crash
    content_date = _ensure_utc_aware(content_date)
    missing_since = _ensure_utc_aware(missing_since)

    # Source reliability (30% weight)
    source_score = SOURCE_WEIGHT.get(source, 0.4)
    score += source_score * 0.3

    # Content relevance (40% weight)
    content_score = 0.0
    
    # Check for high-value keywords (sightings, found, etc.)
    for kw in HIGH_VALUE_KEYWORDS:
        if kw in text:
            content_score = max(content_score, 0.9)
            break

    # Check for medium-value keywords
    if content_score < 0.5:
        for kw in MEDIUM_VALUE_KEYWORDS:
            if kw in text:
                content_score = max(content_score, 0.5)
                break

    # Check for location information
    for kw in LOCATION_KEYWORDS:
        if kw in text:
            content_score = min(1.0, content_score + 0.2)
            break

    # Name in title is higher value than just in body
    if name_lower and name_lower in title.lower():
        content_score = min(1.0, content_score + 0.1)

    score += content_score * 0.4

    # Temporal relevance (20% weight)
    temporal_score = 0.3  # default if no dates
    if content_date and missing_since:
        days_after = (content_date - missing_since).days
        if days_after >= 0:
            if days_after <= 7:
                temporal_score = 1.0   # Very recent after disappearance
            elif days_after <= 30:
                temporal_score = 0.8
            elif days_after <= 90:
                temporal_score = 0.6
            elif days_after <= 365:
                temporal_score = 0.4
            else:
                temporal_score = 0.2
        else:
            temporal_score = 0.05  # Before disappearance — not useful
    elif content_date:
        # No missing_since, but we have content date — recent is better
        age_days = (datetime.now(timezone.utc) - content_date).days
        if age_days <= 7:
            temporal_score = 0.8
        elif age_days <= 30:
            temporal_score = 0.6
        elif age_days <= 90:
            temporal_score = 0.4
        else:
            temporal_score = 0.2

    score += temporal_score * 0.2

    # Geographic relevance bonus (10% weight)
    geo_score = 0.0
    if city and city.lower() in text:
        geo_score = 0.7
    
    province_names = {
        "Alberta", "British Columbia", "Manitoba", "New Brunswick",
        "Newfoundland", "Northwest Territories", "Nova Scotia", "Nunavut",
        "Ontario", "Prince Edward Island", "Quebec", "Saskatchewan", "Yukon",
    }
    for prov in province_names:
        if prov.lower() in text:
            geo_score = max(geo_score, 0.4)
            break

    score += geo_score * 0.1

    return round(min(1.0, max(0.0, score)), 3)


def classify_lead(confidence: float) -> str:
    """Classify a lead by confidence level.

    Currently used as a utility — will be integrated into the
    investigation pipeline in Phase 7 (Intelligence Hub).

    Returns: "high", "medium", "low", or "noise"
    """
    if confidence >= 0.7:
        return "high"
    elif confidence >= 0.45:
        return "medium"
    elif confidence >= 0.2:
        return "low"
    else:
        return "noise"
