"""MCSC ArcGIS FeatureServer API client.

Fetches missing children case data from the Missing Children Society of Canada's
public ArcGIS FeatureServer endpoint, including case details and photo attachments.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.database import SessionLocal
from backend.models.case import MissingCase, CasePhoto, SyncLog, utcnow


# Province code mapping (ArcGIS codes → display names)
PROVINCE_CODES = {
    "Alberta": "Alberta",
    "BritishColumbia": "British Columbia",
    "Manitoba": "Manitoba",
    "NewBrunswick": "New Brunswick",
    "NewfoundlandandLabrador": "Newfoundland and Labrador",
    "NT": "Northwest Territories",
    "NovaScotia": "Nova Scotia",
    "NU": "Nunavut",
    "Ontario": "Ontario",
    "PrinceEdwardIsland": "Prince Edward Island",
    "Quebec": "Quebec",
    "Saskatchewan": "Saskatchewan",
    "YT": "Yukon",
}

# Status display mapping
STATUS_DISPLAY = {
    "vulnerable": "Vulnerable",
    "abudction": "Abduction",  # Note: typo in MCSC data
    "amberalert": "Amber Alert",
    "childsearchalert": "Child Search Alert",
    "missing": "Missing",
    "policeoption1": "Police Option 1",
}

BASE_URL = settings.MCSC_FEATURE_SERVER_URL
REQUEST_TIMEOUT = 30.0
MAX_PAGE_SIZE = 1000


class MCSCClient:
    """Client for the MCSC ArcGIS FeatureServer API."""

    def __init__(self):
        self.base_url = BASE_URL

    async def _query(
        self,
        where: str = "1=1",
        out_fields: str = "*",
        return_geometry: bool = True,
        result_offset: int = 0,
        result_record_count: int = MAX_PAGE_SIZE,
        order_by: str = "missing DESC",
        response_format: str = "json",
    ) -> dict:
        """Execute a query against the ArcGIS FeatureServer."""
        params = {
            "where": where,
            "outFields": out_fields,
            "returnGeometry": str(return_geometry).lower(),
            "resultOffset": result_offset,
            "resultRecordCount": result_record_count,
            "orderByFields": order_by,
            "f": response_format,
        }

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(f"{self.base_url}/query", params=params)
            response.raise_for_status()
            return response.json()

    async def fetch_cases(
        self,
        where: str = "casestatus='open'",
        offset: int = 0,
        limit: int = MAX_PAGE_SIZE,
    ) -> list[dict]:
        """Fetch a page of cases from the API."""
        data = await self._query(
            where=where,
            result_offset=offset,
            result_record_count=limit,
        )
        features = data.get("features", [])
        logger.debug(f"Fetched {len(features)} features (offset={offset})")
        return features

    async def fetch_all_open_cases(self, province: Optional[str] = None) -> list[dict]:
        """Fetch all open cases, handling pagination."""
        where = "casestatus='open'"
        if province:
            where += f" AND province='{province}'"

        all_features = []
        offset = 0

        while True:
            features = await self.fetch_cases(where=where, offset=offset)
            if not features:
                break
            all_features.extend(features)
            if len(features) < MAX_PAGE_SIZE:
                break
            offset += MAX_PAGE_SIZE

        logger.info(f"Fetched {len(all_features)} total open cases" +
                     (f" for {province}" if province else ""))
        return all_features

    async def fetch_recent_cases(self, days: int = 90) -> list[dict]:
        """Fetch cases from the last N days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_ms = int(cutoff.timestamp() * 1000)
        where = f"casestatus='open' AND missing >= {cutoff_ms}"
        return await self.fetch_all_open_cases_with_where(where)

    async def fetch_all_open_cases_with_where(self, where: str) -> list[dict]:
        """Fetch all cases matching a where clause, handling pagination."""
        all_features = []
        offset = 0

        while True:
            features = await self.fetch_cases(where=where, offset=offset)
            if not features:
                break
            all_features.extend(features)
            if len(features) < MAX_PAGE_SIZE:
                break
            offset += MAX_PAGE_SIZE

        return all_features

    async def fetch_case_attachments(self, objectid: int) -> list[dict]:
        """Fetch attachment metadata for a specific case."""
        url = f"{self.base_url}/{objectid}/attachments"
        params = {"f": "json"}

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        attachments = data.get("attachmentInfos", [])
        logger.debug(f"Case {objectid} has {len(attachments)} attachments")
        return attachments

    async def download_attachment(
        self, objectid: int, attachment_id: int, save_dir: Optional[Path] = None
    ) -> Optional[Path]:
        """Download a photo attachment and save it locally."""
        if save_dir is None:
            save_dir = settings.IMAGES_DIR

        save_dir.mkdir(parents=True, exist_ok=True)
        url = f"{self.base_url}/{objectid}/attachments/{attachment_id}"

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()

            # Determine file extension from content type
            content_type = response.headers.get("content-type", "image/jpeg")
            ext = ".jpg"
            if "png" in content_type:
                ext = ".png"
            elif "gif" in content_type:
                ext = ".gif"
            elif "webp" in content_type:
                ext = ".webp"

            filename = f"case_{objectid}_att_{attachment_id}{ext}"
            save_path = save_dir / filename
            save_path.write_bytes(response.content)

            logger.debug(f"Downloaded attachment: {save_path}")
            return save_path

    def _parse_feature(self, feature: dict) -> dict:
        """Parse an ArcGIS feature into a flat dictionary for our model."""
        attrs = feature.get("attributes", {})
        geometry = feature.get("geometry", {})

        # Parse millisecond timestamps from ArcGIS
        missing_since = None
        if attrs.get("missing"):
            try:
                missing_since = datetime.fromtimestamp(
                    attrs["missing"] / 1000, tz=timezone.utc
                )
            except (ValueError, TypeError, OSError):
                pass

        created_at = None
        if attrs.get("CreationDate"):
            try:
                created_at = datetime.fromtimestamp(
                    attrs["CreationDate"] / 1000, tz=timezone.utc
                )
            except (ValueError, TypeError, OSError):
                pass

        updated_at = None
        if attrs.get("EditDate"):
            try:
                updated_at = datetime.fromtimestamp(
                    attrs["EditDate"] / 1000, tz=timezone.utc
                )
            except (ValueError, TypeError, OSError):
                pass

        return {
            "objectid": attrs.get("objectid"),
            "globalid": attrs.get("globalid"),
            "name": attrs.get("name"),
            "age": attrs.get("age"),
            "gender": attrs.get("gender"),
            "ethnicity": attrs.get("ethnicity"),
            "city": attrs.get("city"),
            "province": attrs.get("province"),
            "latitude": geometry.get("y"),
            "longitude": geometry.get("x"),
            "missing_since": missing_since,
            "description": attrs.get("description"),
            "status": attrs.get("status"),
            "case_status": attrs.get("casestatus"),
            "authority_name": attrs.get("authname"),
            "authority_email": attrs.get("authemail"),
            "authority_phone": attrs.get("authphone"),
            "authority_phone_alt": attrs.get("authphonetwo"),
            "authority_link": attrs.get("authlink"),
            "photo_url": attrs.get("pic_url"),
            "thumb_url": attrs.get("thumb_url"),
            "arcgis_created_at": created_at,
            "arcgis_updated_at": updated_at,
        }

    async def sync_all_cases(self, db: Optional[Session] = None) -> dict:
        """Full synchronization: fetch all open cases and update the database.

        Returns a summary dict with counts of added, updated, removed cases.
        """
        own_session = db is None
        if own_session:
            db = SessionLocal()

        sync_log = SyncLog(started_at=utcnow(), status="running")
        db.add(sync_log)
        db.commit()

        try:
            # Fetch all open cases from all provinces
            logger.info("Starting full sync from MCSC ArcGIS API...")
            features = await self.fetch_all_open_cases()
            logger.info(f"Fetched {len(features)} features from API")

            # Parse features
            api_cases = {}
            for feature in features:
                parsed = self._parse_feature(feature)
                if parsed["objectid"] is not None:
                    api_cases[parsed["objectid"]] = parsed

            # Get existing cases from DB
            existing_cases = {
                c.objectid: c for c in db.query(MissingCase).all()
            }

            added = 0
            updated = 0
            removed = 0
            photos_downloaded = 0

            # Add or update cases
            for oid, case_data in api_cases.items():
                if oid in existing_cases:
                    # Update existing case
                    existing = existing_cases[oid]
                    changed = False
                    for key, value in case_data.items():
                        if key in ("objectid",):
                            continue
                        current = getattr(existing, key, None)
                        if current != value:
                            setattr(existing, key, value)
                            changed = True
                    if changed:
                        existing.last_synced_at = utcnow()
                        updated += 1
                else:
                    # Insert new case
                    new_case = MissingCase(**case_data)
                    new_case.first_synced_at = utcnow()
                    new_case.last_synced_at = utcnow()
                    db.add(new_case)
                    added += 1

            # Mark cases that are no longer in the API
            api_oids = set(api_cases.keys())
            for oid, existing in existing_cases.items():
                if oid not in api_oids and existing.case_status == "open":
                    existing.case_status = "resolved_or_removed"
                    existing.last_synced_at = utcnow()
                    removed += 1

            db.commit()

            # Download photos for new cases
            for oid in api_cases:
                if oid not in existing_cases:
                    try:
                        attachments = await self.fetch_case_attachments(oid)
                        for att in attachments:
                            att_id = att.get("id")
                            if att_id is None:
                                continue

                            # Build the attachment URL
                            att_url = f"{self.base_url}/{oid}/attachments/{att_id}"

                            # Download the file
                            save_path = await self.download_attachment(oid, att_id)

                            if save_path:
                                photo = CasePhoto(
                                    case_objectid=oid,
                                    attachment_id=att_id,
                                    url=att_url,
                                    local_path=str(save_path),
                                    content_type=att.get("contentType"),
                                    file_size=att.get("size"),
                                    downloaded_at=utcnow(),
                                )
                                db.add(photo)
                                photos_downloaded += 1

                            # Small delay to be respectful to the API
                            await asyncio.sleep(0.2)
                    except Exception as e:
                        logger.warning(f"Failed to download photos for case {oid}: {e}")

            db.commit()

            # Update sync log
            sync_log.completed_at = utcnow()
            sync_log.cases_added = added
            sync_log.cases_updated = updated
            sync_log.cases_removed = removed
            sync_log.photos_downloaded = photos_downloaded
            sync_log.total_cases = len(api_cases)
            sync_log.status = "completed"
            db.commit()

            summary = {
                "status": "completed",
                "total_from_api": len(api_cases),
                "added": added,
                "updated": updated,
                "removed": removed,
                "photos_downloaded": photos_downloaded,
            }
            logger.info(f"Sync completed: {summary}")
            return summary

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            sync_log.completed_at = utcnow()
            sync_log.status = "failed"
            sync_log.error_message = str(e)
            db.commit()
            raise
        finally:
            if own_session:
                db.close()


# Module-level client instance
mcsc_client = MCSCClient()
