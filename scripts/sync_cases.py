"""Sync normalized cases from the public MCSC ArcGIS feed."""

from __future__ import annotations

import asyncio

from backend.core.database import SessionLocal, init_db
from backend.services.case_service import CaseService


async def main() -> None:
    init_db()
    with SessionLocal() as session:
        result = await CaseService(session).sync_from_mcsc()
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
