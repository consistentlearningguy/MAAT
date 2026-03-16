"""Username enumeration engine.

Generates plausible usernames from a person's name and checks whether
accounts exist on major social media platforms. This is the core of
digital footprint tracking — if a missing teen creates or uses an
account after their disappearance date, that's a lead.

We implement our own lightweight checker rather than shelling out to
sherlock, because:
1. We need async (sherlock is sync/subprocess)
2. We need fine-grained control over which platforms to check
3. We need to integrate results directly into our DB
4. We only care about high-value platforms with reliable detection

IMPORTANT: Each platform needs its own validation logic. Simple HTTP
status checks produce massive false positives (Instagram, Facebook,
Snapchat, Spotify, Telegram all return 200 for non-existent users).
We use a combination of:
- Platform-specific APIs (Reddit, GitHub, Roblox have JSON APIs)
- Redirect-based detection (some platforms redirect non-existent users)
- Content-based detection (check response body for "not found" text)
- Known false-positive filtering (skip platforms that can't be checked reliably)
"""

import asyncio
import random
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from loguru import logger


# User-Agent pool — rotated per request batch
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


# --- Platform-specific checkers ---
# Each returns True if the account exists, False if it doesn't, None if unsure.
# Unsure results are discarded (we prefer false negatives to false positives).


async def _check_github(client: httpx.AsyncClient, username: str) -> Optional[dict]:
    """GitHub: JSON API returns 404 for non-existent users. Very reliable."""
    url = f"https://api.github.com/users/{username}"
    try:
        resp = await client.get(url, timeout=10.0)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "platform": "GitHub",
                "username": username,
                "url": f"https://github.com/{username}",
                "status_code": 200,
                "exists": True,
                "extra": {"name": data.get("name"), "bio": data.get("bio")},
            }
    except Exception as e:
        logger.debug(f"  [GitHub] @{username}: {e}")
    return None


async def _check_reddit(client: httpx.AsyncClient, username: str) -> Optional[dict]:
    """Reddit: JSON API returns 404 for non-existent users. Reliable."""
    url = f"https://www.reddit.com/user/{username}/about.json"
    try:
        resp = await client.get(url, timeout=10.0)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("kind") == "t2" and data.get("data", {}).get("name"):
                return {
                    "platform": "Reddit",
                    "username": username,
                    "url": f"https://www.reddit.com/user/{username}",
                    "status_code": 200,
                    "exists": True,
                }
    except Exception as e:
        logger.debug(f"  [Reddit] @{username}: {e}")
    return None


async def _check_youtube(client: httpx.AsyncClient, username: str) -> Optional[dict]:
    """YouTube: Returns 404 for non-existent @handles. Reliable."""
    url = f"https://www.youtube.com/@{username}"
    try:
        resp = await client.get(url, timeout=10.0, follow_redirects=True)
        if resp.status_code == 200:
            text = resp.text[:10000].lower()
            # YouTube 404 pages contain specific indicators
            if "this page isn" in text or "404" in text or '"error"' in text:
                return None
            # Real channel pages contain channel metadata
            if '"channelid"' in text or '"externalid"' in text or "@" + username.lower() in text:
                return {
                    "platform": "YouTube",
                    "username": username,
                    "url": url,
                    "status_code": 200,
                    "exists": True,
                }
        elif resp.status_code == 404:
            return None
    except Exception as e:
        logger.debug(f"  [YouTube] @{username}: {e}")
    return None


async def _check_twitch(client: httpx.AsyncClient, username: str) -> Optional[dict]:
    """Twitch: Profile pages return 404 for non-existent users (after redirects)."""
    url = f"https://www.twitch.tv/{username}"
    try:
        resp = await client.get(url, timeout=10.0, follow_redirects=True)
        if resp.status_code == 200:
            text = resp.text[:10000].lower()
            # Twitch 404 pages contain specific text
            if ("content is unavailable" in text or
                    "sorry, unless you" in text or
                    "this content is" in text or
                    f'"{username.lower()}"' not in text):
                # Not found, or ambiguous — skip
                # Only confirm if username appears in page metadata
                if f'"{username.lower()}"' in text or f"@{username.lower()}" in text:
                    return {
                        "platform": "Twitch",
                        "username": username,
                        "url": url,
                        "status_code": 200,
                        "exists": True,
                    }
                return None
            return {
                "platform": "Twitch",
                "username": username,
                "url": url,
                "status_code": 200,
                "exists": True,
            }
    except Exception as e:
        logger.debug(f"  [Twitch] @{username}: {e}")
    return None


async def _check_steam(client: httpx.AsyncClient, username: str) -> Optional[dict]:
    """Steam: Profile page contains specific error text for non-existent custom URLs."""
    url = f"https://steamcommunity.com/id/{username}"
    try:
        resp = await client.get(url, timeout=10.0, follow_redirects=True)
        if resp.status_code == 200:
            text = resp.text[:15000].lower()
            not_found = [
                "the specified profile could not be found",
                "error_ctn",
            ]
            if any(nf in text for nf in not_found):
                return None
            # Verify it looks like a real profile
            if "profile_header" in text or "playeravatar" in text:
                return {
                    "platform": "Steam",
                    "username": username,
                    "url": url,
                    "status_code": 200,
                    "exists": True,
                }
    except Exception as e:
        logger.debug(f"  [Steam] @{username}: {e}")
    return None


async def _check_roblox(client: httpx.AsyncClient, username: str) -> Optional[dict]:
    """Roblox: Has a proper JSON API for username lookup. Very reliable."""
    url = "https://users.roblox.com/v1/usernames/users"
    try:
        resp = await client.post(
            url,
            json={"usernames": [username], "excludeBannedUsers": False},
            timeout=10.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            users = data.get("data", [])
            if users:
                user = users[0]
                return {
                    "platform": "Roblox",
                    "username": username,
                    "url": f"https://www.roblox.com/users/{user['id']}/profile",
                    "status_code": 200,
                    "exists": True,
                    "extra": {"display_name": user.get("displayName")},
                }
    except Exception as e:
        logger.debug(f"  [Roblox] @{username}: {e}")
    return None


async def _check_pinterest(client: httpx.AsyncClient, username: str) -> Optional[dict]:
    """Pinterest: Returns 404 for non-existent users. Fairly reliable."""
    url = f"https://www.pinterest.com/{username}/"
    try:
        resp = await client.get(url, timeout=10.0, follow_redirects=True)
        if resp.status_code == 200:
            text = resp.text[:10000].lower()
            if "looking for" in text or "page not found" in text or resp.url.path == "/":
                return None
            return {
                "platform": "Pinterest",
                "username": username,
                "url": url,
                "status_code": 200,
                "exists": True,
            }
    except Exception as e:
        logger.debug(f"  [Pinterest] @{username}: {e}")
    return None


async def _check_soundcloud(client: httpx.AsyncClient, username: str) -> Optional[dict]:
    """SoundCloud: Returns 404 for non-existent users. Reliable."""
    url = f"https://soundcloud.com/{username}"
    try:
        resp = await client.get(url, timeout=10.0, follow_redirects=True)
        if resp.status_code == 404:
            return None
        if resp.status_code == 200:
            text = resp.text[:5000].lower()
            if "we can't find that" in text or "page not found" in text:
                return None
            return {
                "platform": "SoundCloud",
                "username": username,
                "url": url,
                "status_code": 200,
                "exists": True,
            }
    except Exception as e:
        logger.debug(f"  [SoundCloud] @{username}: {e}")
    return None


async def _check_deviantart(client: httpx.AsyncClient, username: str) -> Optional[dict]:
    """DeviantArt: Returns proper error page for non-existent users."""
    url = f"https://www.deviantart.com/{username}"
    try:
        resp = await client.get(url, timeout=10.0, follow_redirects=True)
        if resp.status_code == 404:
            return None
        if resp.status_code == 200:
            text = resp.text[:5000].lower()
            if "page not found" in text or "this page doesn't exist" in text:
                return None
            return {
                "platform": "DeviantArt",
                "username": username,
                "url": url,
                "status_code": 200,
                "exists": True,
            }
    except Exception as e:
        logger.debug(f"  [DeviantArt] @{username}: {e}")
    return None


async def _check_wattpad(client: httpx.AsyncClient, username: str) -> Optional[dict]:
    """Wattpad: Returns 404 for non-existent users."""
    url = f"https://www.wattpad.com/user/{username}"
    try:
        resp = await client.get(url, timeout=10.0, follow_redirects=True)
        if resp.status_code == 404:
            return None
        if resp.status_code == 200:
            text = resp.text[:5000].lower()
            if "page not found" in text or "sorry, this" in text:
                return None
            return {
                "platform": "Wattpad",
                "username": username,
                "url": url,
                "status_code": 200,
                "exists": True,
            }
    except Exception as e:
        logger.debug(f"  [Wattpad] @{username}: {e}")
    return None


async def _check_medium(client: httpx.AsyncClient, username: str) -> Optional[dict]:
    """Medium: Returns 404 for non-existent users."""
    url = f"https://medium.com/@{username}"
    try:
        resp = await client.get(url, timeout=10.0, follow_redirects=True)
        if resp.status_code == 404:
            return None
        if resp.status_code == 200:
            text = resp.text[:5000].lower()
            if "page not found" in text or "out of nothing" in text or "404" in text:
                return None
            return {
                "platform": "Medium",
                "username": username,
                "url": url,
                "status_code": 200,
                "exists": True,
            }
    except Exception as e:
        logger.debug(f"  [Medium] @{username}: {e}")
    return None


async def _check_linktree(client: httpx.AsyncClient, username: str) -> Optional[dict]:
    """Linktree: Returns 404 for non-existent pages."""
    url = f"https://linktr.ee/{username}"
    try:
        resp = await client.get(url, timeout=10.0, follow_redirects=True)
        if resp.status_code == 404:
            return None
        if resp.status_code == 200:
            text = resp.text[:5000].lower()
            if "page not found" in text or "nothing to see" in text:
                return None
            return {
                "platform": "Linktree",
                "username": username,
                "url": url,
                "status_code": 200,
                "exists": True,
            }
    except Exception as e:
        logger.debug(f"  [Linktree] @{username}: {e}")
    return None


async def _check_vimeo(client: httpx.AsyncClient, username: str) -> Optional[dict]:
    """Vimeo: Returns 404 for non-existent users."""
    url = f"https://vimeo.com/{username}"
    try:
        resp = await client.get(url, timeout=10.0, follow_redirects=True)
        if resp.status_code == 404:
            return None
        if resp.status_code == 200:
            text = resp.text[:5000].lower()
            if "page not found" in text or "sorry, we couldn" in text:
                return None
            return {
                "platform": "Vimeo",
                "username": username,
                "url": url,
                "status_code": 200,
                "exists": True,
            }
    except Exception as e:
        logger.debug(f"  [Vimeo] @{username}: {e}")
    return None


async def _check_flickr(client: httpx.AsyncClient, username: str) -> Optional[dict]:
    """Flickr: Returns redirect to 'page not found' for non-existent users."""
    url = f"https://www.flickr.com/people/{username}/"
    try:
        resp = await client.get(url, timeout=10.0, follow_redirects=True)
        if resp.status_code == 404:
            return None
        if resp.status_code == 200:
            text = resp.text[:5000].lower()
            if "page not found" in text or "not a valid" in text:
                return None
            return {
                "platform": "Flickr",
                "username": username,
                "url": url,
                "status_code": 200,
                "exists": True,
            }
    except Exception as e:
        logger.debug(f"  [Flickr] @{username}: {e}")
    return None


async def _check_askfm(client: httpx.AsyncClient, username: str) -> Optional[dict]:
    """Ask.fm: Returns 404 for non-existent users."""
    url = f"https://ask.fm/{username}"
    try:
        resp = await client.get(url, timeout=10.0, follow_redirects=True)
        if resp.status_code == 404:
            return None
        if resp.status_code == 200:
            text = resp.text[:5000].lower()
            if "page not found" in text or "user not found" in text:
                return None
            return {
                "platform": "Ask.fm",
                "username": username,
                "url": url,
                "status_code": 200,
                "exists": True,
            }
    except Exception as e:
        logger.debug(f"  [Ask.fm] @{username}: {e}")
    return None


# Platforms we SKIP because they can't be reliably checked without login/JS:
# - Instagram: Returns login wall (200) for all usernames when not logged in
# - TikTok: JavaScript-rendered, 200 for everything in raw HTML
# - Twitter/X: Requires login for profile viewing since 2023
# - Facebook: Returns login wall (200) for all usernames
# - Snapchat: Returns 200 branding page for all /add/ URLs
# - Spotify: Returns 200 for any /user/ URL
# - Telegram: Returns 200 "open in app" page for all URLs
# - Tumblr: Subdomains often return 200 with parked/default pages
#
# These platforms would require either:
# 1. API keys / OAuth tokens
# 2. Browser automation (Playwright/Selenium)
# 3. Mobile app API reverse engineering
# None of which we implement in this phase.

# Map of platform name -> checker function
PLATFORM_CHECKERS = {
    "GitHub": _check_github,
    "Reddit": _check_reddit,
    "YouTube": _check_youtube,
    "Twitch": _check_twitch,
    "Steam": _check_steam,
    "Roblox": _check_roblox,
    "Pinterest": _check_pinterest,
    "SoundCloud": _check_soundcloud,
    "DeviantArt": _check_deviantart,
    "Wattpad": _check_wattpad,
    "Medium": _check_medium,
    "Linktree": _check_linktree,
    "Vimeo": _check_vimeo,
    "Flickr": _check_flickr,
    "Ask.fm": _check_askfm,
}

# Platforms that need browser automation (listed for transparency, not checked)
SKIPPED_PLATFORMS = [
    "Instagram", "TikTok", "Twitter/X", "Facebook", "Snapchat",
    "Spotify", "Telegram", "Tumblr",
]


def generate_usernames(
    name: str,
    age: Optional[int] = None,
    missing_since: Optional[datetime] = None,
) -> list[str]:
    """Generate plausible username variations from a person's name.

    For a name like "Talon Horton" (age 16, missing since 2025), generates:
    - talonhorton, talon.horton, talon_horton
    - talon.h, talonh, t.horton, thorton
    - talon, horton (if uncommon enough)
    - talonhorton2009, talonhorton09 (with birth year estimated from missing_since - age)

    Returns deduplicated list sorted by likelihood.
    """
    if not name or not name.strip():
        return []

    # Clean the name
    clean = re.sub(r'[^\w\s-]', '', name.strip().lower())
    parts = clean.split()

    if len(parts) == 0:
        return []

    usernames = set()

    if len(parts) == 1:
        w = parts[0]
        usernames.update([w, f"{w}_", f"_{w}"])
    else:
        first = parts[0]
        last = parts[-1]
        middle_parts = parts[1:-1] if len(parts) > 2 else []

        # Core variations (most likely)
        usernames.update([
            f"{first}{last}",           # talonhorton
            f"{first}.{last}",          # talon.horton
            f"{first}_{last}",          # talon_horton
            f"{first}-{last}",          # talon-horton
            f"{first}{last[0]}",        # talonh
            f"{first}.{last[0]}",       # talon.h
            f"{first}_{last[0]}",       # talon_h
            f"{first[0]}{last}",        # thorton
            f"{first[0]}.{last}",       # t.horton
            f"{first[0]}_{last}",       # t_horton
            f"{last}{first}",           # hortontalon
            f"{last}.{first}",          # horton.talon
            f"{last}_{first}",          # horton_talon
            first,                       # talon
            last,                        # horton
        ])

        # With middle name if present
        for mid in middle_parts:
            usernames.update([
                f"{first}{mid}{last}",
                f"{first}.{mid}.{last}",
                f"{first}_{mid}_{last}",
                f"{first[0]}{mid[0]}{last}",
            ])

        # Age/birth year variations (teens often include these)
        if age is not None:
            # Estimate birth year from age at time of disappearance
            if missing_since:
                reference_year = missing_since.year
            else:
                reference_year = datetime.now().year
            birth_year = reference_year - age
            birth_year_short = birth_year % 100

            for base in [f"{first}{last}", f"{first}.{last}", f"{first}_{last}", first]:
                usernames.update([
                    f"{base}{birth_year}",         # talonhorton2009
                    f"{base}{birth_year_short}",    # talonhorton09
                    f"{base}{age}",                 # talonhorton16
                    f"{base}_{birth_year}",
                    f"{base}_{birth_year_short}",
                    f"{base}_{age}",
                ])

        # Common teen suffixes
        for base in [f"{first}{last}", first]:
            usernames.update([
                f"{base}x",
                f"{base}xx",
                f"{base}xo",
                f"x{base}x",
                f"_{base}_",
                f"the{base}",
                f"real{base}",
                f"its{base}",
                f"not{base}",
                f"{base}official",
            ])

    # Filter out too-short usernames (high false positive rate)
    usernames = {u for u in usernames if len(u) >= 3 and u.strip()}

    # Sort: exact name combos first (highest value), then variations
    result = sorted(usernames, key=lambda u: (
        0 if any(p in u for p in parts) and len(u) > 5 else 1,
        len(u),
    ))

    return result


async def search_all_usernames(
    name: str,
    age: Optional[int] = None,
    missing_since: Optional[datetime] = None,
    max_concurrent: int = 5,
    max_usernames: int = 20,
) -> list[dict]:
    """Generate usernames from a name and check all of them across all platforms.

    This is the main entry point. Given a missing person's name and age,
    it generates plausible usernames and checks each one across platforms
    that can be reliably queried without login/API keys.

    Returns a flat list of all hits: [{"platform", "username", "url", "exists"}, ...]
    """
    usernames = generate_usernames(name, age, missing_since)[:max_usernames]

    if not usernames:
        logger.warning(f"No usernames generated for name='{name}'")
        return []

    platforms = list(PLATFORM_CHECKERS.keys())
    logger.info(
        f"Checking {len(usernames)} username variations across "
        f"{len(platforms)} platforms (skipping {len(SKIPPED_PLATFORMS)} "
        f"unreliable platforms: {', '.join(SKIPPED_PLATFORMS)})"
    )

    semaphore = asyncio.Semaphore(max_concurrent)
    all_hits = []

    # Use a single shared httpx client for all requests (connection pooling)
    ua = random.choice(USER_AGENTS)
    async with httpx.AsyncClient(
        headers={"User-Agent": ua},
        follow_redirects=True,
        timeout=12.0,
    ) as client:

        for i, username in enumerate(usernames):
            logger.debug(f"  Checking username {i+1}/{len(usernames)}: @{username}")

            # Check all platforms concurrently for this username
            async def _check_with_semaphore(checker_fn, uname):
                async with semaphore:
                    return await checker_fn(client, uname)

            tasks = [
                _check_with_semaphore(checker_fn, username)
                for checker_fn in PLATFORM_CHECKERS.values()
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.debug(f"  Platform check error: {result}")
                elif result is not None:
                    result["generated_from"] = name
                    all_hits.append(result)

            # Small delay between usernames to avoid rate limiting
            if i < len(usernames) - 1:
                await asyncio.sleep(0.3)

    logger.info(f"Username search complete: {len(all_hits)} verified accounts found for '{name}'")
    return all_hits
