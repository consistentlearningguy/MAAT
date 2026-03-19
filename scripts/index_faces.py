"""Face indexing script — extract, encode, and crop faces from all case photos.

Run this once after initial_sync.py to build the face index.
Can also be re-run with --force to re-index all photos.

Usage:
    python -m scripts.index_faces
    python -m scripts.index_faces --force
    python -m scripts.index_faces --case 8037
    python -m scripts.index_faces --match
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger

from backend.core.database import init_db, SessionLocal


def main():
    parser = argparse.ArgumentParser(description="Index faces in case photos")
    parser.add_argument(
        "--force", action="store_true",
        help="Re-index photos that already have encodings"
    )
    parser.add_argument(
        "--case", type=int, default=None,
        help="Only index photos for this case objectid"
    )
    parser.add_argument(
        "--match", action="store_true",
        help="After indexing, run cross-case face matching"
    )
    parser.add_argument(
        "--match-only", action="store_true",
        help="Skip indexing, only run cross-case matching"
    )
    parser.add_argument(
        "--threshold", type=float, default=None,
        help="Face distance threshold for matching (default: from config)"
    )
    args = parser.parse_args()

    logger.info("=== OSINT Missing Persons CA - Face Indexing ===")
    logger.info("")

    # Initialize database tables (creates face_encodings / face_matches if missing)
    logger.info("Initializing database...")
    init_db()

    from backend.analysis import face_engine

    try:
        face_engine.ensure_face_recognition_available()
    except RuntimeError as e:
        logger.error(str(e))
        raise SystemExit(1)

    db = SessionLocal()
    try:
        # --- Index phase ---
        if not args.match_only:
            logger.info("")
            if args.case:
                logger.info(f"Indexing faces for case {args.case}...")
            else:
                logger.info("Indexing faces in ALL case photos...")
            if args.force:
                logger.info("(Force mode: re-indexing existing photos)")
            logger.info("")

            result = face_engine.index_all_photos(db, force=args.force, case_objectid=args.case)

            logger.info("")
            logger.info("=== Indexing Results ===")
            logger.info(f"  Photos total:       {result['photos_total']}")
            logger.info(f"  Photos processed:   {result['photos_processed']}")
            logger.info(f"  Photos skipped:     {result['photos_skipped']}")
            logger.info(f"  Photos with faces:  {result['photos_with_faces']}")
            logger.info(f"  Total faces found:  {result['total_faces_found']}")
            logger.info("")

        # --- Matching phase ---
        if args.match or args.match_only:
            logger.info("Running cross-case face matching...")
            matches = face_engine.find_cross_case_matches(
                db,
                case_objectid=args.case,
                threshold=args.threshold,
            )

            if matches:
                logger.info(f"Found {len(matches)} cross-case match(es):")
                for m in matches[:20]:  # Show top 20
                    logger.info(
                        f"  Case {m['case_a_objectid']} <-> Case {m['case_b_objectid']}  "
                        f"distance={m['distance']:.4f}  confidence={m['confidence']:.1%}"
                    )
                if len(matches) > 20:
                    logger.info(f"  ... and {len(matches) - 20} more")

                saved = face_engine.save_cross_case_matches(db, matches)
                logger.info(f"Saved {len(saved)} new match(es) to database")
            else:
                logger.info("No cross-case face matches found.")
            logger.info("")

        logger.info("Done.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
