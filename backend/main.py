"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger

from backend.core.config import settings
from backend.core.database import init_db, get_db
from backend.core.scheduler import start_scheduler, stop_scheduler
from backend.api.cases import router as cases_router
from backend.api.sync import router as sync_router
from backend.api.investigations import router as investigations_router, cleanup_stale_investigations
from backend.api.faces import router as faces_router

BACKEND_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("Starting OSINT Missing Persons CA...")
    init_db()
    logger.info("Database initialized.")

    # C3: Clean up any investigations stuck as "running" from a previous crash
    db = next(get_db())
    try:
        cleaned = cleanup_stale_investigations(db)
        if cleaned:
            logger.info(f"Cleaned up {cleaned} stale investigation(s) from previous session.")
    finally:
        db.close()

    start_scheduler()
    yield
    stop_scheduler()
    logger.info("Application shut down.")


app = FastAPI(
    title="OSINT Missing Persons Canada",
    description="Intelligence platform for locating missing children in Canada",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(BACKEND_DIR / "static")), name="static")

# Also serve downloaded images
app.mount("/data/images", StaticFiles(directory=str(settings.IMAGES_DIR)), name="images")

# Serve face crops
app.mount("/data/faces", StaticFiles(directory=str(settings.FACES_DIR)), name="faces")

# Templates
templates = Jinja2Templates(directory=str(BACKEND_DIR / "templates"))

# Include API routers
app.include_router(cases_router)
app.include_router(sync_router)
app.include_router(investigations_router)
app.include_router(faces_router)


# --- Page routes ---

@app.get("/")
async def index(request: Request):
    """Dashboard page with map and case list."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/case/{objectid}")
async def case_detail(request: Request, objectid: int):
    """Case detail page."""
    return templates.TemplateResponse(
        "case_detail.html",
        {"request": request, "objectid": objectid},
    )


# --- Run directly ---

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
