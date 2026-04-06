"""Investigation, query logging, review, and lead models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base
from shared.utils.dates import utcnow


class InvestigationRun(Base):
    """Investigator-only enrichment run."""

    __tablename__ = "investigation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    mode: Mapped[str] = mapped_column(String(32), default="developer")
    connector_names: Mapped[list[str]] = mapped_column(JSON, default=list)
    feature_flags: Mapped[dict] = mapped_column(JSON, default=dict)
    facts_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    inference_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    leads: Mapped[list["Lead"]] = relationship(back_populates="investigation_run", cascade="all, delete-orphan")
    query_logs: Mapped[list["SearchQueryLog"]] = relationship(back_populates="investigation_run", cascade="all, delete-orphan")


class Lead(Base):
    """Normalized, scored lead."""

    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_run_id: Mapped[int] = mapped_column(ForeignKey("investigation_runs.id"), index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    lead_type: Mapped[str] = mapped_column(String(64), index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    source_kind: Mapped[str] = mapped_column(String(32), default="clear-web")
    source_name: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str] = mapped_column(String(1024))
    query_used: Mapped[str] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    found_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    location_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    source_trust: Mapped[float] = mapped_column(Float, default=0.5)
    corroboration_count: Mapped[int] = mapped_column(Integer, default=1)
    rationale: Mapped[list[str]] = mapped_column(JSON, default=list)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    review_status: Mapped[str] = mapped_column(String(32), default="unreviewed")
    human_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    investigation_run: Mapped["InvestigationRun"] = relationship(back_populates="leads")
    review_decisions: Mapped[list["ReviewDecision"]] = relationship(back_populates="lead", cascade="all, delete-orphan")


class SearchQueryLog(Base):
    """Transparent log of each connector query."""

    __tablename__ = "search_query_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_run_id: Mapped[int] = mapped_column(ForeignKey("investigation_runs.id"), index=True)
    connector_name: Mapped[str] = mapped_column(String(255))
    source_kind: Mapped[str] = mapped_column(String(32), default="clear-web")
    query_used: Mapped[str] = mapped_column(String(255))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    investigation_run: Mapped["InvestigationRun"] = relationship(back_populates="query_logs")


class ReviewDecision(Base):
    """Human review outcome for a lead."""

    __tablename__ = "review_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    reviewer: Mapped[str] = mapped_column(String(255), default="local-investigator")
    decision: Mapped[str] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lead: Mapped["Lead"] = relationship(back_populates="review_decisions")
