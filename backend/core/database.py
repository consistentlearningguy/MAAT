"""SQLAlchemy database engine, session factory, and initialization."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.core.config import settings

# Handle SQLite file path: strip sqlite:/// prefix for path check
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db():
    """Create all database tables."""
    from backend.models.case import MissingCase, CasePhoto, SyncLog  # noqa: F401
    from backend.models.investigation import Investigation, Lead  # noqa: F401
    from backend.models.face import FaceEncoding, FaceMatch  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
