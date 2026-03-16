"""Initial data sync script.

Run this once to populate the database with all current cases from MCSC.
Usage: python -m scripts.initial_sync
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger

from backend.core.database import init_db
from backend.ingestion.mcsc_client import mcsc_client


async def main():
    logger.info("=== OSINT Missing Persons CA - Initial Sync ===")
    logger.info("")

    # Initialize database tables
    logger.info("Initializing database...")
    init_db()
    logger.info("Database tables created.")

    # Run full sync
    logger.info("")
    logger.info("Starting data sync from MCSC ArcGIS API...")
    logger.info("This will fetch all open cases across all Canadian provinces.")
    logger.info("")

    try:
        result = await mcsc_client.sync_all_cases()

        logger.info("")
        logger.info("=== Sync Complete ===")
        logger.info(f"  Total cases from API:  {result['total_from_api']}")
        logger.info(f"  New cases added:       {result['added']}")
        logger.info(f"  Cases updated:         {result['updated']}")
        logger.info(f"  Cases removed/resolved:{result['removed']}")
        logger.info(f"  Photos downloaded:     {result['photos_downloaded']}")
        logger.info("")
        logger.info("Database is ready. Start the server with:")
        logger.info("  python -m backend.main")
        logger.info("")

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
