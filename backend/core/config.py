"""Application configuration loaded from environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    """Application settings."""

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'data' / 'db.sqlite'}"
    )

    # MCSC ArcGIS FeatureServer
    MCSC_FEATURE_SERVER_URL: str = os.getenv(
        "MCSC_FEATURE_SERVER_URL",
        "https://services.arcgis.com/Sv9ZXFjH5h1fYAaI/arcgis/rest/services/"
        "Missing_Children_Cases_View_Master/FeatureServer/0",
    )

    # Sync
    SYNC_INTERVAL_MINUTES: int = int(os.getenv("SYNC_INTERVAL_MINUTES", "60"))

    # Server
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")

    # Paths
    DATA_DIR: Path = PROJECT_ROOT / "data"
    IMAGES_DIR: Path = DATA_DIR / "images"
    FACES_DIR: Path = DATA_DIR / "faces"

    # Face recognition (Phase 3)
    # Detection model: "hog" (faster, CPU) or "cnn" (more accurate, GPU recommended)
    FACE_DETECTION_MODEL: str = os.getenv("FACE_DETECTION_MODEL", "hog")
    # Distance threshold for considering two faces the same person
    # Lower = stricter. face_recognition default is 0.6.
    FACE_MATCH_THRESHOLD: float = float(os.getenv("FACE_MATCH_THRESHOLD", "0.55"))
    # Number of times to upsample image when detecting faces (higher = find smaller faces)
    FACE_UPSAMPLE_COUNT: int = int(os.getenv("FACE_UPSAMPLE_COUNT", "1"))
    # Padding (%) around face crop for context
    FACE_CROP_PADDING: float = float(os.getenv("FACE_CROP_PADDING", "0.25"))

    # Reverse image search API keys (Phase 3 — optional)
    PIMEYES_API_KEY: str | None = os.getenv("PIMEYES_API_KEY")
    GOOGLE_VISION_API_KEY: str | None = os.getenv("GOOGLE_VISION_API_KEY")
    TINEYE_API_KEY: str | None = os.getenv("TINEYE_API_KEY")

    def __init__(self):
        # Ensure data directories exist
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        self.FACES_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
