"""SQLAlchemy database setup."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.core.config import settings


class Base(DeclarativeBase):
    """Declarative base for SQLAlchemy models."""


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
    future=True,
    echo=settings.debug,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_db():
    """FastAPI dependency for DB sessions."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Create tables."""
    from backend.models.case import AlertSnapshot, Case, CasePhoto, GeoContext, ResourceLink, SourceRecord
    from backend.models.investigation import InvestigationRun, Lead, ReviewDecision, SearchQueryLog

    Base.metadata.create_all(bind=engine)
