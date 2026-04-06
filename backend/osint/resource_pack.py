"""Trace Labs-inspired investigator resource packs."""

from __future__ import annotations

import re
from urllib.parse import urlencode

from backend.core.config import settings
from backend.enrichment.official_context import extract_official_context
from backend.models.case import Case
from backend.osint.normalization.models import QueryContext
from backend.osint.query_planner import build_news_query_plan, build_trace_labs_query_groups

TRACE_LABS_PREP_URL = "https://docs.tracelabs.org/prepare-for-a-ctf"
TRACE_LABS_SCORING_URL = "https://docs.tracelabs.org/searchparty/searchparty-scoring-system"
TRACE_LABS_VM_URL = "https://github.com/tracelabs/tlosint-vm/releases"
CANADAS_MISSING_URL = "https://canadasmissing.ca/"
RCMP_MISSING_URL = "https://rcmp.ca/en/missing-persons"
MISSING_KIDS_URL = "https://missingkids.ca/en/missing-children-database/"
NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_TURBO_URL = "https://overpass-turbo.eu/"


def _search_url(base_url: str, query: str, **extra: str) -> str:
    params = {"q": query, **extra}
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode(params)}"


def _search_launchers(query: str) -> list[dict[str, str]]:
    launchers = [
        {"label": "Bing", "url": _search_url("https://www.bing.com/search", query)},
        {"label": "DuckDuckGo", "url": _search_url("https://duckduckgo.com/", query)},
        {"label": "Brave", "url": _search_url("https://search.brave.com/search", query)},
    ]
    if settings.searxng_url:
        launchers.insert(
            0,
            {
                "label": "SearXNG",
                "url": _search_url(
                    f"{settings.searxng_url.rstrip('/')}/search",
                    query,
                    format="html",
                    language="en-CA",
                ),
            },
        )
    return launchers


def _context_from_case(case: Case) -> QueryContext:
    official_context = _case_official_context(case)
    return QueryContext(
        case_id=case.id,
        name=case.name or "",
        aliases=case.aliases or [],
        city=case.city,
        province=case.province,
        age=case.age,
        missing_since=case.missing_since,
        location_text=official_context.get("location_text"),
        image_urls=[photo.url for photo in case.photos if photo.url],
    )


def _case_official_context(case: Case) -> dict[str, object]:
    context = extract_official_context(
        case.official_summary_html,
        city=case.city,
        province=case.province,
    )
    if "official-field-conflict" in (case.risk_flags or []):
        warning = (
            "A conflicting ArcGIS location field was detected and the case was re-anchored to the official summary location."
        )
        if warning not in context["quality_warnings"]:
            context["quality_warnings"].append(warning)
    return context


def _strip_html(value: str | None) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", value or "").split())


def _location_query(case: Case, official_context: dict[str, object]) -> str:
    location_text = str(official_context.get("location_text") or "").strip()
    if location_text:
        return location_text
    parts = [part for part in [case.city, case.province, "Canada"] if part]
    return ", ".join(parts)


def _dedupe_launchers(launchers: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for launcher in launchers:
        url = launcher.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(launcher)
    return deduped


def _official_urls(case: Case) -> list[str]:
    urls: list[str] = []
    for value in (
        case.authority_case_url,
        case.source_url,
        *(photo.source_url for photo in case.photos),
        *(record.source_url for record in case.source_records),
    ):
        candidate = str(value or "").strip()
        if candidate and candidate not in urls:
            urls.append(candidate)
    return urls


def _gdelt_artlist_url(query: str) -> str:
    return f"{settings.gdelt_doc_api_url}?{urlencode({'query': query, 'mode': 'ArtList', 'format': 'json', 'maxrecords': 50, 'sort': 'DateDesc'})}"


def _nominatim_search_url(query: str) -> str:
    return f"{NOMINATIM_SEARCH_URL}?{urlencode({'q': query, 'format': 'jsonv2', 'limit': 10})}"


def _overpass_wizard_url(query: str) -> str:
    return f"{OVERPASS_TURBO_URL}?{urlencode({'w': query, 'R': ''})}"


def _wayback_lookup_url(target_url: str | None = None) -> str:
    if not target_url:
        return "https://web.archive.org/"
    return f"https://web.archive.org/web/*/{target_url}"


def _map_launchers(case: Case, official_context: dict[str, object]) -> list[dict[str, str]]:
    if case.latitude is not None and case.longitude is not None:
        coordinate_query = f"{case.latitude},{case.longitude}"
        return [
            {
                "label": "OpenStreetMap",
                "url": f"https://www.openstreetmap.org/?mlat={case.latitude}&mlon={case.longitude}#map=13/{case.latitude}/{case.longitude}",
            },
            {
                "label": "Google Maps",
                "url": f"https://www.google.com/maps/search/?api=1&{urlencode({'query': coordinate_query})}",
            },
        ]

    location_query = _location_query(case, official_context)
    if not location_query:
        return []

    return [
        {
            "label": "OpenStreetMap",
            "url": f"https://www.openstreetmap.org/search?{urlencode({'query': location_query})}",
        },
        {
            "label": "Google Maps",
            "url": f"https://www.google.com/maps/search/?api=1&{urlencode({'query': location_query})}",
        },
    ]


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> list[str]:
    normalized = text.lower()
    return [keyword for keyword in keywords if keyword in normalized]


def _coverage_status(score: int, full_threshold: int) -> str:
    if score >= full_threshold:
        return "covered"
    if score > 0:
        return "partial"
    return "missing"


def _coverage_label(status: str) -> str:
    return {
        "covered": "Anchored",
        "partial": "Partial",
        "missing": "Gap",
    }.get(status, status.title())


def _build_category_coverage(case: Case, context: QueryContext, official_context: dict[str, object]) -> dict[str, object]:
    summary_text = _strip_html(case.official_summary_html)
    family_hits = _keyword_hits(
        summary_text,
        ("mother", "father", "mom", "dad", "sister", "brother", "friend", "family", "guardian"),
    )
    employment_hits = _keyword_hits(
        summary_text,
        ("school", "student", "classmate", "college", "university", "work", "employer", "coworker"),
    )
    official_urls = _official_urls(case)

    categories: list[dict[str, object]] = []

    basic_evidence = []
    basic_gaps = []
    if context.name:
        basic_evidence.append("Primary name")
    else:
        basic_gaps.append("No primary name in the case record")
    if context.aliases:
        basic_evidence.append("Alias list")
    else:
        basic_gaps.append("No aliases or handles in structured data")
    if context.age is not None:
        basic_evidence.append("Official age")
    if case.gender or case.ethnicity:
        basic_evidence.append("Demographic descriptors")
    if official_context.get("descriptor_chips"):
        basic_evidence.append("Parsed appearance details")
    if context.image_urls:
        basic_evidence.append("Official case photo")
    else:
        basic_gaps.append("No case photo available for reverse-image pivots")
    basic_status = _coverage_status(len(basic_evidence), 4)
    categories.append(
        {
            "slug": "basic-subject-info",
            "title": "Basic Subject Info",
            "status": basic_status,
            "status_label": _coverage_label(basic_status),
            "summary": "Identity anchors already present in official case facts.",
            "evidence": basic_evidence,
            "gaps": basic_gaps,
            "recommended_action": "Use General Name Sweep and Social Profile Sweep to turn aliases into attributable profiles.",
        }
    )

    family_evidence = [f"Official summary mentions {', '.join(family_hits[:3])}"] if family_hits else []
    family_gaps = ["No structured family or close-contact identifiers are stored in the case model."]
    family_status = "partial" if family_hits else "missing"
    categories.append(
        {
            "slug": "family-friends",
            "title": "Family / Friends",
            "status": family_status,
            "status_label": _coverage_label(family_status),
            "summary": "Relationship pivots usually require corroborating posts, obituaries, tagged photos, or official narratives.",
            "evidence": family_evidence,
            "gaps": family_gaps,
            "recommended_action": "Prioritize the Family And Friends Pivot group and preserve direct post URLs if relatives surface.",
        }
    )

    employment_evidence = [
        f"Official summary hints at {', '.join(employment_hits[:3])}"
    ] if employment_hits else []
    employment_gaps = ["No structured school, employer, or club identifiers are stored yet."]
    employment_status = "partial" if employment_hits else "missing"
    categories.append(
        {
            "slug": "employment-education",
            "title": "Employment / Education",
            "status": employment_status,
            "status_label": _coverage_label(employment_status),
            "summary": "School and work links are high-value when they can be tied to a public roster, article, or profile.",
            "evidence": employment_evidence,
            "gaps": employment_gaps,
            "recommended_action": "Use the Employment And School Pivot group to target public school, club, and employer references.",
        }
    )

    day_last_seen_evidence = []
    day_last_seen_gaps = []
    if context.missing_since:
        day_last_seen_evidence.append("Official missing date")
    else:
        day_last_seen_gaps.append("No missing-since date is available")
    if official_context.get("location_text"):
        day_last_seen_evidence.append("Specific last-seen location")
    elif case.city or case.province:
        day_last_seen_evidence.append("Broad location anchor")
    else:
        day_last_seen_gaps.append("No city or province anchor is available")
    if summary_text:
        day_last_seen_evidence.append("Official narrative summary")
    if official_context.get("fields", {}).get("last_seen_wearing"):
        day_last_seen_evidence.append("Last-seen clothing description")
    day_last_seen_status = "covered" if context.missing_since and (case.city or case.province) else _coverage_status(len(day_last_seen_evidence), 2)
    categories.append(
        {
            "slug": "day-last-seen",
            "title": "Day Last Seen",
            "status": day_last_seen_status,
            "status_label": _coverage_label(day_last_seen_status),
            "summary": "Date and broad-location anchors determine whether a lead actually advances the case.",
            "evidence": day_last_seen_evidence,
            "gaps": day_last_seen_gaps,
            "recommended_action": "Cross-check any lead against the official date and location before escalating it.",
        }
    )

    timeline_evidence = []
    timeline_gaps = ["No corroborated post-missing events are stored yet."]
    if context.missing_since:
        timeline_evidence.append("Baseline timeline anchor")
    if case.arcgis_updated_at or case.updated_at:
        timeline_evidence.append("Public update timestamp")
    if official_urls:
        timeline_evidence.append("Public URL available for archive review")
    if case.alert_snapshots:
        timeline_evidence.append("Stored alert snapshots")
        timeline_gaps = []
    timeline_status = _coverage_status(len(timeline_evidence), 3)
    categories.append(
        {
            "slug": "advancing-timeline",
            "title": "Advancing Timeline",
            "status": timeline_status,
            "status_label": _coverage_label(timeline_status),
            "summary": "The dashboard should separate baseline official facts from newer public events and archive captures.",
            "evidence": timeline_evidence,
            "gaps": timeline_gaps,
            "recommended_action": "Use GDELT and Wayback to identify attributable updates after the official disappearance date.",
        }
    )

    geo_evidence = []
    geo_gaps = []
    if case.latitude is not None and case.longitude is not None:
        geo_evidence.append("Coordinates")
    if official_context.get("location_text"):
        geo_evidence.append("Official location string")
    elif case.city or case.province:
        geo_evidence.append("Broad place labels")
    else:
        geo_gaps.append("No city/province anchor exists for geo pivots")
    if case.geo_contexts:
        geo_evidence.append("Nearby reference overlays")
    if official_context.get("quality_warnings"):
        geo_gaps.extend(official_context["quality_warnings"])
    geo_status = "covered" if case.latitude is not None and case.longitude is not None else _coverage_status(len(geo_evidence), 2)
    categories.append(
        {
            "slug": "location-geo",
            "title": "Location / Geo",
            "status": geo_status,
            "status_label": _coverage_label(geo_status),
            "summary": "Maps are strongest when tied to exact anchors, transit nodes, and attributable last-seen context.",
            "evidence": geo_evidence,
            "gaps": geo_gaps,
            "recommended_action": "Use Nominatim and Overpass to turn broad locations into reviewable map context, not exact-location claims.",
        }
    )

    ordered = sorted(categories, key=lambda item: (item["status"] == "covered", item["status"] == "partial"), reverse=False)
    next_steps = []
    for category in ordered:
        action = str(category.get("recommended_action") or "").strip()
        if action and action not in next_steps:
            next_steps.append(action)

    anchored = sum(1 for category in categories if category["status"] != "missing")
    covered = sum(1 for category in categories if category["status"] == "covered")
    return {
        "summary": f"{anchored} of {len(categories)} Trace Labs-style categories have some official anchor.",
        "description": (
            "Coverage is derived from current structured case facts only. It shows where the case board is already grounded "
            "and where analysts still need attributable public evidence."
        ),
        "covered_count": covered,
        "anchored_count": anchored,
        "category_count": len(categories),
        "categories": categories,
        "next_steps": next_steps[:4],
    }


def _query_group(group: dict[str, object]) -> dict[str, object]:
    queries = list(group.get("queries", []))
    return {
        "slug": group["slug"],
        "title": group["title"],
        "trace_labs_category": group["trace_labs_category"],
        "summary": group["summary"],
        "mode": "search pivots",
        "items": [
            {
                "label": group["title"],
                "description": group["summary"],
                "queries": queries[:4],
                "launchers": _search_launchers(queries[0]) if queries else [],
                "notes": [
                    "Keep the search passive and no-touch.",
                    "Capture direct URLs and screenshots for anything worth escalating.",
                ],
            }
        ],
    }


def _official_cross_check_group(case: Case, context: QueryContext, official_context: dict[str, object]) -> dict[str, object]:
    location = (
        official_context.get("inferred_city")
        or case.city
        or official_context.get("inferred_province")
        or case.province
        or "Canada"
    )
    portal_query = f'site:canadasmissing.ca "{context.name}" "{location}"'.strip()
    missingkids_query = f'site:missingkids.ca "{context.name}" "{location}"'.strip()
    rcmp_query = f'site:rcmp.ca/en/missing-persons "{context.name}"'.strip()
    official_urls = _official_urls(case)

    items = [
        {
            "label": "Official Database Cross-Check",
            "description": "Verify whether the case or related public notices already appear in national or NGO case databases.",
            "queries": [portal_query, missingkids_query, rcmp_query],
            "launchers": _dedupe_launchers(
                _search_launchers(portal_query)
                + [
                    {"label": "Canada's Missing", "url": CANADAS_MISSING_URL},
                    {"label": "RCMP Missing Persons", "url": RCMP_MISSING_URL},
                    {"label": "MissingKids.ca", "url": MISSING_KIDS_URL},
                ]
            ),
            "notes": [
                "Use this to confirm the latest public wording, photos, and authority contact details.",
                "A duplicate official record is corroboration, not a new lead.",
            ],
        }
    ]

    if official_context.get("location_text") or official_context.get("descriptor_chips"):
        items.append(
            {
                "label": "Official Last-Seen Anchor",
                "description": "Direct facts parsed from the official summary for fast analyst triage.",
                "queries": [
                    value
                    for value in [
                        official_context.get("location_text"),
                        official_context.get("missing_since_text"),
                    ]
                    if value
                ],
                "launchers": [],
                "notes": [
                    *(official_context.get("descriptor_chips") or []),
                    *(official_context.get("quality_warnings") or []),
                ],
                "target_value": official_context.get("location_text"),
            }
        )

    if official_urls:
        items.append(
            {
                "label": "Known Official Pages",
                "description": "Direct public pages already tied to the case and worth preserving in the archive workflow.",
                "queries": [],
                "launchers": [
                    *(
                        {"label": f"Official URL {index + 1}", "url": url}
                        for index, url in enumerate(official_urls[:3])
                    ),
                    {"label": "Wayback Lookup", "url": _wayback_lookup_url(official_urls[0])},
                ],
                "notes": [
                    "Archive any official page that changes wording, photos, or contact numbers.",
                ],
                "target_value": official_urls[0],
            }
        )

    return {
        "slug": "official-cross-check",
        "title": "Official Cross-Checks",
        "trace_labs_category": "Basic Subject Info",
        "summary": "Ground the case in official or NGO sources before treating a public find as novel.",
        "mode": "official sources",
        "items": items,
    }


def _news_archive_group(case: Case, context: QueryContext, official_context: dict[str, object]) -> dict[str, object]:
    news_queries = build_news_query_plan(context, limit=4)
    official_target = _official_urls(case)[0] if _official_urls(case) else None
    location_query = _location_query(case, official_context)

    items = [
        {
            "label": "GDELT News Pivot",
            "description": "Search public news coverage and timeline spikes with a reviewable, date-sorted article feed.",
            "queries": news_queries,
            "launchers": (
                [{"label": "GDELT ArtList", "url": _gdelt_artlist_url(news_queries[0])}]
                + (_search_launchers(news_queries[0]) if news_queries else [])
            )
            if news_queries
            else [],
                "notes": [
                    "Compare article dates to the official disappearance date before calling a result an advancement.",
                    "Prefer direct article URLs over search snippets.",
                    "If GDELT rate-limits the API, use the search launchers and capture direct article URLs manually.",
                ],
            },
        {
            "label": "Archive Recovery",
            "description": "Preserve public pages that disappear, change wording, or swap images over time.",
            "queries": [official_target] if official_target else [],
            "launchers": _dedupe_launchers(
                [
                    {"label": "Wayback Lookup", "url": _wayback_lookup_url(official_target)},
                    {"label": "Internet Archive", "url": "https://archive.org/"},
                ]
            ),
            "notes": [
                "Archive searches work best once you have a concrete public URL worth preserving.",
                "Treat archive captures as evidence artifacts with dates and screenshots.",
            ],
            "target_value": official_target,
        },
    ]

    if location_query:
        items.append(
            {
                "label": "Local News Sweep",
                "description": "Search for city- and province-bounded coverage that may mention last-seen context or appeals.",
                "queries": [f'"{context.name}" "{location_query}" news'],
                "launchers": _search_launchers(f'"{context.name}" "{location_query}" news'),
                "notes": [
                    "Local coverage often contains names of schools, teams, stations, or family members.",
                ],
            }
        )

    return {
        "slug": "news-archive-monitoring",
        "title": "News And Archive Monitoring",
        "trace_labs_category": "Day Last Seen / Advancing The Timeline",
        "summary": "Use news indexes and archive captures to separate baseline case facts from later public developments.",
        "mode": "timeline pivots",
        "items": items,
    }


def _geo_open_data_group(case: Case, official_context: dict[str, object]) -> dict[str, object]:
    location_query = _location_query(case, official_context)
    map_launchers = _map_launchers(case, official_context)
    transit_query = f"public_transport in {location_query}" if location_query else ""
    school_query = f"amenity=school in {location_query}" if location_query else ""
    support_query = f"social_facility in {location_query}" if location_query else ""

    return {
        "slug": "geo-open-data",
        "title": "Geo And Open Data Pivots",
        "trace_labs_category": "Location / Day Last Seen",
        "summary": "Turn broad place strings into reviewable map context using open geocoding and OpenStreetMap data.",
        "mode": "open data",
        "items": [
            {
                "label": "Nominatim Geocode",
                "description": "Resolve city- and province-level place anchors into mappable coordinates and alternate place records.",
                "queries": [location_query] if location_query else [],
                "launchers": (
                    [{"label": "Nominatim", "url": _nominatim_search_url(location_query)}] + map_launchers
                )
                if location_query
                else map_launchers,
                "notes": [
                    "Geocoding should support case context, not imply a current exact location.",
                ],
            },
            {
                "label": "Overpass Turbo Context",
                "description": "Inspect nearby transit, schools, or support facilities as public context around the official place anchor.",
                "queries": [query for query in [transit_query, school_query, support_query] if query],
                "launchers": _dedupe_launchers(
                    [
                        {"label": "Transit", "url": _overpass_wizard_url(transit_query)} if transit_query else {},
                        {"label": "Schools", "url": _overpass_wizard_url(school_query)} if school_query else {},
                        {"label": "Support", "url": _overpass_wizard_url(support_query)} if support_query else {},
                    ]
                ),
                "notes": [
                    "Use this to build map context around official anchors, then route any credible tip to the listed authority.",
                ],
            },
        ],
    }


def _photo_resource_group(case: Case, image_urls: list[str], official_context: dict[str, object]) -> dict[str, object]:
    reverse_image_item = {
        "label": "Reverse-Image Pivot",
        "description": "Review public image matches and alternate photos without scraping behind logins.",
        "queries": [],
        "launchers": [
            {"label": "TinEye", "url": "https://tineye.com/"},
            {"label": "Google Lens", "url": "https://lens.google.com/"},
            {"label": "Yandex Images", "url": "https://yandex.com/images/"},
        ],
        "notes": [
            "Paste the official case photo URL into the selected reverse-image tool.",
            "Capture alternate backgrounds, clothing, or account avatars if they appear.",
        ],
        "target_value": image_urls[0] if image_urls else None,
    }

    archive_item = {
        "label": "Map And Area Context",
        "description": "Use map pivots alongside the app's existing transit, border, airport, and highway overlays.",
        "queries": [_location_query(case, official_context)] if _location_query(case, official_context) else [],
        "launchers": _map_launchers(case, official_context),
        "notes": [
            "Cross-check only public locations and route any credible tip to the listed authority.",
            "Do not treat a broad city match as a current exact location.",
        ],
    }

    return {
        "slug": "photo-archive-geo",
        "title": "Photo And Map Pivot",
        "trace_labs_category": "Basic / Advanced Subject Info",
        "summary": "Manual pivots for reverse-image review and map context once an official photo or place anchor exists.",
        "mode": "manual tools",
        "items": [reverse_image_item, archive_item],
    }


def build_case_resource_pack(case: Case) -> dict[str, object]:
    """Build a passive investigator resource pack for one case."""

    official_context = _case_official_context(case)
    context = _context_from_case(case)
    groups = [
        _official_cross_check_group(case, context, official_context),
        *(_query_group(group) for group in build_trace_labs_query_groups(context)),
        _news_archive_group(case, context, official_context),
        _geo_open_data_group(case, official_context),
        _photo_resource_group(case, context.image_urls[:2], official_context),
    ]

    return {
        "case_id": case.id,
        "case_name": case.name,
        "methodology": {
            "name": "Passive OSINT Case Pack",
            "summary": (
                "Case-specific pivots derived from Trace Labs no-touch missing-person workflows and expanded with "
                "official cross-check, news, archive, and open-geo resources."
            ),
            "notes": [
                "Passive only: no contacting relatives, joining closed groups, or password resets.",
                "Favour direct links, screenshots, and attributable public sources over paraphrased notes.",
                "Exact location claims require corroboration and manual routing to the listed authority.",
            ],
            "references": [
                TRACE_LABS_PREP_URL,
                TRACE_LABS_SCORING_URL,
                TRACE_LABS_VM_URL,
                "https://api.gdeltproject.org/api/v2/doc/doc",
                "https://nominatim.org/release-docs/5.0/api/Search/",
                "https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_API_by_Example",
            ],
        },
        "official_context": official_context,
        "coverage": _build_category_coverage(case, context, official_context),
        "groups": groups,
    }
