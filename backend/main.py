"""Backend entrypoint."""

from __future__ import annotations

import uvicorn

from backend.api.app import app
from backend.core.config import settings


if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port, reload=settings.debug)
