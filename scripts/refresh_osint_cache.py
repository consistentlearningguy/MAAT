"""Run optional investigator-mode enrichment for one case."""

from __future__ import annotations

import argparse
import asyncio

from backend.core.config import settings
from backend.core.database import SessionLocal, init_db
from backend.services.investigation_service import InvestigationService


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id", type=int)
    args = parser.parse_args()

    if not settings.enable_investigator_mode:
        raise SystemExit("ENABLE_INVESTIGATOR_MODE must be true to refresh OSINT cache.")

    init_db()
    with SessionLocal() as session:
        run = await InvestigationService(session).run_for_case(args.case_id)
        print({"run_id": run.id, "status": run.status, "connectors": run.connector_names})


if __name__ == "__main__":
    asyncio.run(main())
