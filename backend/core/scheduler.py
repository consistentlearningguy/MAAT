"""APScheduler setup for periodic data synchronization."""

import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from loguru import logger

from backend.core.config import settings
from backend.ingestion.mcsc_client import mcsc_client

scheduler = BackgroundScheduler()


def _run_sync():
    """Wrapper to run async sync in a background thread."""
    logger.info("Scheduled sync triggered...")
    loop = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(mcsc_client.sync_all_cases())
        logger.info(f"Scheduled sync completed: {result}")
    except Exception as e:
        logger.error(f"Scheduled sync failed: {e}")
    finally:
        if loop:
            loop.close()


def start_scheduler():
    """Start the background scheduler with sync job."""
    scheduler.add_job(
        _run_sync,
        "interval",
        minutes=settings.SYNC_INTERVAL_MINUTES,
        id="mcsc_sync",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        f"Scheduler started. Sync interval: {settings.SYNC_INTERVAL_MINUTES} minutes"
    )


def stop_scheduler():
    """Shut down the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
