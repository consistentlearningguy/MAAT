"""Investigation orchestrator.

This is the SINGLE entry point for running an OSINT investigation against
a missing person case. Both the CLI (scripts) and the API background task
call run_investigation() here — there is no duplicate orchestration code.

It:
1. Optionally creates an Investigation record in the DB (or uses one provided)
2. Fetches the case details (name, age, city, province, missing_since)
3. Runs the username enumeration engine
4. Runs the web mention scanner
5. Runs face recognition (index + cross-case match + reverse image search)
6. Scores all results using the lead scoring system
7. Saves scored results as Lead records in the DB
8. Updates the Investigation record with summary counts

Usage:
    from backend.analysis.investigate import run_investigation
    result = await run_investigation(case_objectid=8037, db=session)
"""

import asyncio
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy.orm import Session

from backend.models.case import MissingCase
from backend.models.investigation import Investigation, Lead
from backend.analysis.username_search import search_all_usernames
from backend.analysis.web_mentions import scan_web_mentions
from backend.analysis.lead_scoring import score_username_hit, score_web_mention
from backend.analysis.face_engine import (
    async_index_case_photos,
    async_find_cross_case_matches,
)
from backend.analysis.reverse_image_search import search_all_providers
from backend.models.face import FaceEncoding
from backend.core.config import settings


async def run_investigation(
    case_objectid: int,
    db: Session,
    investigation_id: int | None = None,
    run_usernames: bool = True,
    run_web: bool = True,
    run_faces: bool = True,
    max_usernames: int = 15,
    max_web_queries: int = 8,
) -> Investigation:
    """Run a full OSINT investigation against a missing person case.

    This is an async function that runs the username search, web mention
    scanner, and face recognition concurrently, scores all results, and
    saves them to the database.

    Args:
        case_objectid: The MissingCase.objectid to investigate
        db: SQLAlchemy session
        investigation_id: If provided, use this existing Investigation record
            instead of creating a new one. The API endpoint creates the record
            upfront so it can return the ID immediately.
        run_usernames: Whether to run username enumeration
        run_web: Whether to run web mention scanning
        run_faces: Whether to run face recognition (index + cross-case match)
        max_usernames: Max username variations to check
        max_web_queries: Max search queries for web mentions

    Returns:
        The completed Investigation record with all leads attached
    """
    # Fetch the case
    case = db.query(MissingCase).filter(MissingCase.objectid == case_objectid).first()
    if not case:
        raise ValueError(f"Case {case_objectid} not found")

    if not case.name:
        raise ValueError(f"Case {case_objectid} has no name — cannot investigate")

    logger.info(f"Starting investigation for case {case_objectid}: {case.name}")

    # Use existing investigation record or create a new one
    if investigation_id is not None:
        investigation = db.query(Investigation).filter(Investigation.id == investigation_id).first()
        if not investigation:
            raise ValueError(f"Investigation {investigation_id} not found")
        # Ensure it's in the right state
        investigation.status = "running"
        db.commit()
        db.refresh(investigation)
    else:
        investigation = Investigation(
            case_objectid=case_objectid,
            status="running",
            ran_username_search=run_usernames,
            ran_web_mentions=run_web,
            ran_face_search=run_faces,
        )
        db.add(investigation)
        db.commit()
        db.refresh(investigation)

    try:
        all_leads = []

        # Run modules concurrently
        tasks = []
        if run_usernames:
            tasks.append(
                _run_username_search(
                    case.name, case.age, max_usernames, case_objectid, investigation.id
                )
            )
        if run_web:
            tasks.append(
                _run_web_mentions(
                    case.name, case.city, case.province, case.missing_since,
                    max_web_queries, case_objectid, investigation.id
                )
            )
        if run_faces:
            tasks.append(
                _run_face_search(
                    case_objectid, db, investigation.id
                )
            )

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Investigation module failed: {result}")
                else:
                    all_leads.extend(result)

        # Deduplicate leads by source_url (keep highest confidence)
        deduplicated = _deduplicate_leads(all_leads)

        # Save leads to DB
        high_count = 0
        for lead_data in deduplicated:
            lead = Lead(**lead_data)
            db.add(lead)
            if lead.confidence >= 0.7:
                high_count += 1

        # Update investigation summary
        investigation.status = "completed"
        investigation.completed_at = datetime.now(timezone.utc)
        investigation.total_leads = len(deduplicated)
        investigation.high_confidence_leads = high_count

        db.commit()
        db.refresh(investigation)

        logger.info(
            f"Investigation {investigation.id} complete: "
            f"{len(deduplicated)} leads ({high_count} high confidence)"
        )

        return investigation

    except Exception as e:
        logger.error(f"Investigation {investigation.id} failed: {e}")
        investigation.status = "failed"
        investigation.completed_at = datetime.now(timezone.utc)
        investigation.error_message = str(e)
        db.commit()
        raise


async def _run_username_search(
    name: str,
    age: int | None,
    max_usernames: int,
    case_objectid: int,
    investigation_id: int,
) -> list[dict]:
    """Run username enumeration and return scored lead dicts."""
    logger.info(f"Running username search for '{name}'...")

    hits = await search_all_usernames(name, age=age, max_usernames=max_usernames)

    leads = []
    for hit in hits:
        confidence = score_username_hit(
            username=hit["username"],
            platform=hit["platform"],
            person_name=name,
            person_age=age,
        )

        leads.append({
            "investigation_id": investigation_id,
            "case_objectid": case_objectid,
            "lead_type": "username_hit",
            "source_platform": hit["platform"].lower().replace("/", "_"),
            "source_url": hit["url"],
            "source_name": hit["platform"],
            "title": f"@{hit['username']} on {hit['platform']}",
            "content": f"Username '{hit['username']}' exists on {hit['platform']}. "
                       f"Profile URL: {hit['url']}",
            "matched_query": hit.get("generated_from", name),
            "username_found": hit["username"],
            "platform_url": hit["url"],
            "account_exists": True,
            "confidence": confidence,
        })

    logger.info(f"Username search found {len(leads)} hits for '{name}'")
    return leads


async def _run_web_mentions(
    name: str,
    city: str | None,
    province: str | None,
    missing_since: datetime | None,
    max_queries: int,
    case_objectid: int,
    investigation_id: int,
) -> list[dict]:
    """Run web mention scanning and return scored lead dicts."""
    logger.info(f"Running web mention scan for '{name}'...")

    mentions = await scan_web_mentions(
        name, city=city, province=province, max_queries=max_queries
    )

    leads = []
    for mention in mentions:
        confidence = score_web_mention(
            title=mention.get("title", ""),
            content=mention.get("content", ""),
            source=mention.get("source", ""),
            content_date=mention.get("content_date"),
            missing_since=missing_since,
            person_name=name,
            city=city,
            province=province,
        )

        # Determine lead type from source
        source = mention.get("source", "")
        if source == "google_news":
            lead_type = "news_article"
        elif source == "reddit":
            lead_type = "forum_post"
        else:
            lead_type = "web_mention"

        leads.append({
            "investigation_id": investigation_id,
            "case_objectid": case_objectid,
            "lead_type": lead_type,
            "source_platform": source,
            "source_url": mention.get("url"),
            "source_name": mention.get("source_name", ""),
            "title": mention.get("title", ""),
            "content": mention.get("content", ""),
            "matched_query": mention.get("query", ""),
            "content_date": mention.get("content_date"),
            "confidence": confidence,
        })

    logger.info(f"Web mention scan found {len(leads)} mentions for '{name}'")
    return leads


async def _run_face_search(
    case_objectid: int,
    db: Session,
    investigation_id: int,
) -> list[dict]:
    """Run face recognition: index photos, cross-case matching, reverse image search.

    Steps:
    1. Index this case's photos (extract faces, compute encodings)
    2. Compare against all other indexed faces (cross-case matching)
    3. Run reverse image search on face crops (if API keys configured)
    4. Convert all results to lead dicts
    """
    logger.info(f"Running face search for case {case_objectid}...")

    leads = []

    # Step 1: Index this case's photos
    try:
        index_result = await async_index_case_photos(case_objectid, db)
        logger.info(
            f"Face indexing for case {case_objectid}: "
            f"{index_result['total_faces_found']} face(s) from "
            f"{index_result['photos_with_faces']} photo(s)"
        )
    except Exception as e:
        logger.error(f"Face indexing failed for case {case_objectid}: {e}")
        return leads

    # Step 2: Cross-case face matching
    try:
        matches = await async_find_cross_case_matches(case_objectid, db)
        for match in matches:
            # Build face crop URLs for display
            face_a_url = f"/data/faces/{match['face_a_crop']}" if match.get("face_a_crop") else ""
            face_b_url = f"/data/faces/{match['face_b_crop']}" if match.get("face_b_crop") else ""

            # Get the other case's name for the title
            other_case_id = match["case_b_objectid"]
            other_case = db.query(MissingCase).filter(
                MissingCase.objectid == other_case_id
            ).first()
            other_name = other_case.name if other_case else f"Case #{other_case_id}"

            leads.append({
                "investigation_id": investigation_id,
                "case_objectid": case_objectid,
                "lead_type": "face_match",
                "source_platform": "face_recognition",
                "source_url": face_b_url,
                "source_name": "Cross-Case Face Match",
                "title": f"Face similarity with {other_name} (Case #{other_case_id})",
                "content": (
                    f"A face from this case matches a face from {other_name} "
                    f"(Case #{other_case_id}) with {match['confidence']:.0%} confidence "
                    f"(distance: {match['distance']:.3f}). "
                    f"This could indicate the same person appears in multiple cases."
                ),
                "confidence": match["confidence"],
            })

        logger.info(f"Cross-case matching found {len(matches)} match(es) for case {case_objectid}")
    except Exception as e:
        logger.error(f"Cross-case face matching failed: {e}")

    # Step 3: Reverse image search (only if providers are configured)
    try:
        case_faces = (
            db.query(FaceEncoding)
            .filter(FaceEncoding.case_objectid == case_objectid)
            .all()
        )

        for face_enc in case_faces:
            if not face_enc.crop_path:
                continue

            crop_full_path = settings.FACES_DIR / face_enc.crop_path
            if not crop_full_path.exists():
                continue

            ris_results = await search_all_providers(str(crop_full_path))
            for result in ris_results:
                leads.append({
                    "investigation_id": investigation_id,
                    "case_objectid": case_objectid,
                    "lead_type": "face_match",
                    "source_platform": result.get("source_name", "reverse_image_search").lower().replace(" ", "_"),
                    "source_url": result.get("page_url", ""),
                    "source_name": result.get("source_name", "Reverse Image Search"),
                    "title": result.get("title", "Face found online"),
                    "content": (
                        f"A face from this case was found online via {result.get('source_name', 'reverse image search')}. "
                        f"Similarity: {result.get('similarity', 0):.0%}. "
                        f"Source: {result.get('page_url', 'unknown')}"
                    ),
                    "confidence": result.get("similarity", 0.5),
                })

        if case_faces:
            logger.info(f"Reverse image search produced {len(leads) - len(matches)} result(s)")
    except Exception as e:
        logger.error(f"Reverse image search failed: {e}")

    logger.info(f"Face search total: {len(leads)} lead(s) for case {case_objectid}")
    return leads


def _deduplicate_leads(leads: list[dict]) -> list[dict]:
    """Deduplicate leads by source_url, keeping the highest confidence version."""
    import hashlib

    seen = {}  # key -> lead_data

    for lead in leads:
        url = lead.get("source_url") or ""

        if not url:
            # No URL — build a composite key from type, source, title, and content hash
            content_hash = hashlib.md5(
                (lead.get("content", "") or "").encode()
            ).hexdigest()[:8]
            key = (
                f"{lead.get('lead_type', '')}|"
                f"{lead.get('source_name', '')}|"
                f"{lead.get('title', '')}|"
                f"{lead.get('username_found', '')}|"
                f"{content_hash}"
            )
        else:
            key = url

        if key not in seen or lead.get("confidence", 0) > seen[key].get("confidence", 0):
            seen[key] = lead

    return list(seen.values())
