"""Face recognition engine — extraction, encoding, comparison, and indexing.

This module is the heart of Phase 3. It provides:
1. Face detection + encoding from case photos
2. Face cropping and storage
3. Cross-case face comparison (find similar faces across different cases)
4. Upload-based comparison (match an uploaded image against all indexed faces)
5. Bulk indexing of all case photos

All face operations use the `face_recognition` library (dlib backend).
Encodings are 128-dimensional float64 vectors.
"""

import asyncio
from pathlib import Path
from typing import Optional

import numpy as np
import face_recognition
from PIL import Image
from loguru import logger
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.models.case import MissingCase, CasePhoto
from backend.models.face import FaceEncoding, FaceMatch


# ---------------------------------------------------------------------------
# Face detection + encoding
# ---------------------------------------------------------------------------


def detect_and_encode_photo(
    image_path: str | Path,
    detection_model: str | None = None,
    upsample_count: int | None = None,
) -> list[dict]:
    """Detect all faces in an image, return their encodings and bounding boxes.

    Args:
        image_path: Path to the image file
        detection_model: "hog" (fast, CPU) or "cnn" (accurate, GPU)
        upsample_count: Number of times to upsample (higher = find smaller faces)

    Returns:
        List of dicts, each with:
        - encoding: numpy array (128,) float64
        - location: (top, right, bottom, left) pixel coordinates
        - face_index: 0-based index
    """
    model = detection_model or settings.FACE_DETECTION_MODEL
    upsample = upsample_count if upsample_count is not None else settings.FACE_UPSAMPLE_COUNT

    image_path = Path(image_path)
    if not image_path.exists():
        logger.warning(f"Image not found: {image_path}")
        return []

    try:
        # Load image (face_recognition uses PIL internally, expects RGB)
        image = face_recognition.load_image_file(str(image_path))
    except Exception as e:
        logger.error(f"Failed to load image {image_path}: {e}")
        return []

    # Detect face locations
    try:
        locations = face_recognition.face_locations(
            image, number_of_times_to_upsample=upsample, model=model
        )
    except Exception as e:
        logger.error(f"Face detection failed for {image_path}: {e}")
        return []

    if not locations:
        logger.debug(f"No faces detected in {image_path}")
        return []

    # Compute encodings for all detected faces
    try:
        encodings = face_recognition.face_encodings(image, known_face_locations=locations)
    except Exception as e:
        logger.error(f"Face encoding failed for {image_path}: {e}")
        return []

    results = []
    for idx, (encoding, location) in enumerate(zip(encodings, locations)):
        top, right, bottom, left = location
        results.append({
            "encoding": encoding,
            "location": location,  # (top, right, bottom, left)
            "face_index": idx,
        })

    logger.debug(f"Detected {len(results)} face(s) in {image_path.name}")
    return results


# ---------------------------------------------------------------------------
# Face cropping
# ---------------------------------------------------------------------------


def crop_and_save_face(
    image_path: str | Path,
    location: tuple[int, int, int, int],
    output_path: str | Path,
    padding: float | None = None,
) -> Path | None:
    """Crop a face from an image with padding and save it.

    Args:
        image_path: Source image path
        location: (top, right, bottom, left) face bounding box
        output_path: Where to save the cropped face
        padding: Extra padding around face as fraction (0.25 = 25%)

    Returns:
        Path to saved crop, or None on failure
    """
    pad = padding if padding is not None else settings.FACE_CROP_PADDING

    try:
        img = Image.open(image_path)
        width, height = img.size

        top, right, bottom, left = location

        # Add padding
        face_height = bottom - top
        face_width = right - left
        pad_h = int(face_height * pad)
        pad_w = int(face_width * pad)

        crop_top = max(0, top - pad_h)
        crop_bottom = min(height, bottom + pad_h)
        crop_left = max(0, left - pad_w)
        crop_right = min(width, right + pad_w)

        face_crop = img.crop((crop_left, crop_top, crop_right, crop_bottom))

        # Convert RGBA/P/LA to RGB for JPEG compatibility
        if face_crop.mode in ("RGBA", "P", "LA"):
            face_crop = face_crop.convert("RGB")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        face_crop.save(str(output_path), quality=95)

        logger.debug(f"Saved face crop to {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Failed to crop face from {image_path}: {e}")
        return None


# ---------------------------------------------------------------------------
# Database operations — index a single photo
# ---------------------------------------------------------------------------


def index_photo(
    photo: CasePhoto,
    db: Session,
    force: bool = False,
) -> list[FaceEncoding]:
    """Extract faces from a case photo and store encodings in DB.

    Args:
        photo: CasePhoto record (must have local_path set)
        db: SQLAlchemy session
        force: If True, re-index even if encodings already exist

    Returns:
        List of FaceEncoding records created
    """
    if not photo.local_path:
        logger.debug(f"Photo {photo.id} has no local_path, skipping")
        return []

    image_path = settings.IMAGES_DIR / Path(photo.local_path).name
    if not image_path.exists():
        # Try the local_path as-is (might be absolute)
        image_path = Path(photo.local_path)
        if not image_path.exists():
            logger.warning(f"Photo file not found: {photo.local_path}")
            return []

    # Check if already indexed (unless force)
    if not force:
        existing = (
            db.query(FaceEncoding)
            .filter(FaceEncoding.photo_id == photo.id)
            .count()
        )
        if existing > 0:
            logger.debug(f"Photo {photo.id} already indexed ({existing} faces), skipping")
            return []

    # Detect and encode
    faces = detect_and_encode_photo(image_path)

    if not faces:
        return []

    created = []
    for face_data in faces:
        encoding_array = face_data["encoding"]
        top, right, bottom, left = face_data["location"]
        face_idx = face_data["face_index"]

        # Save face crop
        crop_filename = f"case_{photo.case_objectid}_photo_{photo.id}_face_{face_idx}.jpg"
        crop_path = settings.FACES_DIR / crop_filename
        saved_crop = crop_and_save_face(image_path, face_data["location"], crop_path)

        # Store encoding as bytes
        encoding_bytes = encoding_array.astype(np.float64).tobytes()

        face_enc = FaceEncoding(
            case_objectid=photo.case_objectid,
            photo_id=photo.id,
            encoding=encoding_bytes,
            face_top=top,
            face_right=right,
            face_bottom=bottom,
            face_left=left,
            crop_path=crop_filename if saved_crop else None,
            face_index=face_idx,
            encoding_model=settings.FACE_DETECTION_MODEL,
        )
        db.add(face_enc)
        created.append(face_enc)

    db.commit()
    for fe in created:
        db.refresh(fe)

    logger.info(
        f"Indexed photo {photo.id} (case {photo.case_objectid}): "
        f"{len(created)} face(s) found"
    )
    return created


# ---------------------------------------------------------------------------
# Bulk indexing — process all case photos
# ---------------------------------------------------------------------------


def index_all_photos(
    db: Session,
    force: bool = False,
    case_objectid: int | None = None,
) -> dict:
    """Index faces in all case photos (or a specific case).

    Args:
        db: SQLAlchemy session
        force: Re-index photos that already have face encodings
        case_objectid: If provided, only index photos for this case

    Returns:
        Summary dict with counts
    """
    query = db.query(CasePhoto).filter(CasePhoto.local_path.isnot(None))
    if case_objectid is not None:
        query = query.filter(CasePhoto.case_objectid == case_objectid)

    photos = query.all()
    logger.info(f"Indexing faces in {len(photos)} photo(s)...")

    total_faces = 0
    photos_with_faces = 0
    photos_processed = 0
    photos_skipped = 0

    for photo in photos:
        faces = index_photo(photo, db, force=force)
        if faces:
            total_faces += len(faces)
            photos_with_faces += 1
            photos_processed += 1
        elif not force:
            # Check if it was skipped because already indexed
            existing = (
                db.query(FaceEncoding)
                .filter(FaceEncoding.photo_id == photo.id)
                .count()
            )
            if existing > 0:
                photos_skipped += 1
            else:
                photos_processed += 1
        else:
            photos_processed += 1

    summary = {
        "photos_total": len(photos),
        "photos_processed": photos_processed,
        "photos_skipped": photos_skipped,
        "photos_with_faces": photos_with_faces,
        "total_faces_found": total_faces,
    }

    logger.info(
        f"Face indexing complete: {total_faces} faces from "
        f"{photos_with_faces}/{photos_processed} photos "
        f"({photos_skipped} skipped)"
    )
    return summary


# ---------------------------------------------------------------------------
# Face comparison — cross-case matching
# ---------------------------------------------------------------------------


def encoding_from_bytes(encoding_bytes: bytes) -> np.ndarray:
    """Convert stored bytes back to numpy encoding array."""
    return np.frombuffer(encoding_bytes, dtype=np.float64)


def compare_faces(
    known_encoding: np.ndarray,
    candidate_encodings: list[np.ndarray],
    threshold: float | None = None,
) -> list[tuple[int, float]]:
    """Compare one face encoding against a list of candidates.

    Args:
        known_encoding: The reference encoding (128,)
        candidate_encodings: List of candidate encodings
        threshold: Max distance to consider a match (default from config)

    Returns:
        List of (index, distance) tuples for matches below threshold,
        sorted by distance ascending
    """
    if not candidate_encodings:
        return []

    thresh = threshold if threshold is not None else settings.FACE_MATCH_THRESHOLD

    distances = face_recognition.face_distance(candidate_encodings, known_encoding)

    matches = []
    for idx, dist in enumerate(distances):
        if dist <= thresh:
            matches.append((idx, float(dist)))

    matches.sort(key=lambda x: x[1])
    return matches


def find_cross_case_matches(
    db: Session,
    case_objectid: int | None = None,
    threshold: float | None = None,
) -> list[dict]:
    """Find face matches across different cases.

    If case_objectid is provided, compare that case's faces against all others.
    Otherwise, compare all faces against all others (N^2 but deduplicated).

    Args:
        db: SQLAlchemy session
        case_objectid: Optional — limit comparison to this case vs others
        threshold: Face distance threshold

    Returns:
        List of match dicts with case_a, case_b, distance, confidence
    """
    thresh = threshold if threshold is not None else settings.FACE_MATCH_THRESHOLD

    if case_objectid is not None:
        # Compare this case's faces against all others
        case_faces = (
            db.query(FaceEncoding)
            .filter(FaceEncoding.case_objectid == case_objectid)
            .all()
        )
        other_faces = (
            db.query(FaceEncoding)
            .filter(FaceEncoding.case_objectid != case_objectid)
            .all()
        )
    else:
        # Compare all faces (will deduplicate pairs)
        all_faces = db.query(FaceEncoding).all()
        case_faces = all_faces
        other_faces = all_faces

    if not case_faces or not other_faces:
        return []

    # Build encoding arrays
    other_encodings = [encoding_from_bytes(f.encoding) for f in other_faces]

    matches = []
    seen_pairs = set()  # (min_id, max_id) to avoid duplicate pairs

    for face_a in case_faces:
        enc_a = encoding_from_bytes(face_a.encoding)

        for idx, dist in compare_faces(enc_a, other_encodings, threshold=thresh):
            face_b = other_faces[idx]

            # Skip self-matches
            if face_a.id == face_b.id:
                continue
            # Skip same-case matches
            if face_a.case_objectid == face_b.case_objectid:
                continue

            # Deduplicate pairs
            pair_key = (min(face_a.id, face_b.id), max(face_a.id, face_b.id))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            confidence = max(0.0, min(1.0, 1.0 - dist))

            matches.append({
                "face_a_id": face_a.id,
                "face_b_id": face_b.id,
                "case_a_objectid": face_a.case_objectid,
                "case_b_objectid": face_b.case_objectid,
                "distance": dist,
                "confidence": confidence,
                "face_a_crop": face_a.crop_path,
                "face_b_crop": face_b.crop_path,
            })

    matches.sort(key=lambda m: m["distance"])
    logger.info(f"Found {len(matches)} cross-case face match(es)")
    return matches


def save_cross_case_matches(
    db: Session,
    matches: list[dict],
) -> list[FaceMatch]:
    """Save cross-case face match results to the database.

    Avoids duplicates by checking if a match between the same face pair
    already exists.
    """
    created = []
    for match_data in matches:
        # Check for existing match between these faces
        pair_min = min(match_data["face_a_id"], match_data["face_b_id"])
        pair_max = max(match_data["face_a_id"], match_data["face_b_id"])

        existing = (
            db.query(FaceMatch)
            .filter(
                FaceMatch.face_a_id == pair_min,
                FaceMatch.face_b_id == pair_max,
            )
            .first()
        )
        if existing:
            continue

        fm = FaceMatch(
            face_a_id=pair_min,
            face_b_id=pair_max,
            case_a_objectid=match_data["case_a_objectid"],
            case_b_objectid=match_data["case_b_objectid"],
            distance=match_data["distance"],
            confidence=match_data["confidence"],
        )
        db.add(fm)
        created.append(fm)

    if created:
        db.commit()
        for fm in created:
            db.refresh(fm)

    return created


# ---------------------------------------------------------------------------
# Match against uploaded image
# ---------------------------------------------------------------------------


def match_uploaded_image(
    image_path: str | Path,
    db: Session,
    threshold: float | None = None,
    limit: int = 20,
) -> list[dict]:
    """Compare an uploaded image against all indexed face encodings.

    Args:
        image_path: Path to the uploaded image
        db: SQLAlchemy session
        threshold: Face distance threshold
        limit: Maximum number of results

    Returns:
        List of match dicts sorted by distance (best match first)
    """
    # Detect faces in uploaded image
    upload_faces = detect_and_encode_photo(image_path)
    if not upload_faces:
        logger.info("No faces detected in uploaded image")
        return []

    # Get all indexed face encodings
    all_face_records = db.query(FaceEncoding).all()
    if not all_face_records:
        logger.info("No face encodings in database to compare against")
        return []

    all_encodings = [encoding_from_bytes(f.encoding) for f in all_face_records]

    thresh = threshold if threshold is not None else settings.FACE_MATCH_THRESHOLD
    results = []

    for upload_face in upload_faces:
        enc = upload_face["encoding"]

        for idx, dist in compare_faces(enc, all_encodings, threshold=thresh):
            face_record = all_face_records[idx]
            confidence = max(0.0, min(1.0, 1.0 - dist))

            # Get the case info
            case = (
                db.query(MissingCase)
                .filter(MissingCase.objectid == face_record.case_objectid)
                .first()
            )

            results.append({
                "face_encoding_id": face_record.id,
                "case_objectid": face_record.case_objectid,
                "case_name": case.name if case else None,
                "distance": dist,
                "confidence": confidence,
                "crop_path": face_record.crop_path,
                "upload_face_index": upload_face["face_index"],
            })

    # Deduplicate by case (keep best match per case)
    best_per_case = {}
    for r in results:
        cid = r["case_objectid"]
        if cid not in best_per_case or r["distance"] < best_per_case[cid]["distance"]:
            best_per_case[cid] = r

    results = sorted(best_per_case.values(), key=lambda r: r["distance"])
    return results[:limit]


# ---------------------------------------------------------------------------
# Async wrappers for use in the investigation orchestrator
# ---------------------------------------------------------------------------


async def async_index_case_photos(
    case_objectid: int,
    db: Session,
    force: bool = False,
) -> dict:
    """Async wrapper for indexing a case's photos."""
    return await asyncio.to_thread(
        index_all_photos, db=db, force=force, case_objectid=case_objectid
    )


async def async_find_cross_case_matches(
    case_objectid: int,
    db: Session,
    threshold: float | None = None,
) -> list[dict]:
    """Async wrapper for finding cross-case face matches."""
    return await asyncio.to_thread(
        find_cross_case_matches, db=db, case_objectid=case_objectid, threshold=threshold
    )
