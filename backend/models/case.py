"""Core case, source, photo, resource, and geospatial models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base
from shared.utils.dates import utcnow


class Case(Base):
    """Normalized missing child case."""

    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_record_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    slug: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str | None] = mapped_column(String(255), index=True)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ethnicity: Mapped[str | None] = mapped_column(String(128), nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), index=True)
    province: Mapped[str | None] = mapped_column(String(128), index=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str | None] = mapped_column(String(64), index=True)
    case_status: Mapped[str | None] = mapped_column(String(64), index=True)
    missing_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    official_summary_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    authority_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    authority_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    authority_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    authority_phone_alt: Mapped[str | None] = mapped_column(String(64), nullable=True)
    authority_case_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    mcsc_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mcsc_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risk_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_feed: Mapped[str] = mapped_column(String(255), default="Missing Children Society of Canada ArcGIS")
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    arcgis_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    arcgis_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    photos: Mapped[list["CasePhoto"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    source_records: Mapped[list["SourceRecord"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    resource_links: Mapped[list["ResourceLink"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    geo_contexts: Mapped[list["GeoContext"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    alert_snapshots: Mapped[list["AlertSnapshot"]] = relationship(back_populates="case", cascade="all, delete-orphan")


class CasePhoto(Base):
    """Photo for a case."""

    __tablename__ = "case_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    url: Mapped[str] = mapped_column(String(1024))
    thumb_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    caption: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    case: Mapped["Case"] = relationship(back_populates="photos")


class SourceRecord(Base):
    """Normalized source attribution record."""

    __tablename__ = "source_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    source_name: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(64))
    source_url: Mapped[str] = mapped_column(String(1024))
    query_used: Mapped[str | None] = mapped_column(String(255), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    official: Mapped[bool] = mapped_column(Boolean, default=True)
    trust_weight: Mapped[float] = mapped_column(Float, default=1.0)
    attribution_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    case: Mapped["Case"] = relationship(back_populates="source_records")


class ResourceLink(Base):
    """Public resources and reporting routes linked to a case or province."""

    __tablename__ = "resource_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    province: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(1024))
    authority_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    official: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    case: Mapped["Case"] = relationship(back_populates="resource_links")


class GeoContext(Base):
    """Nearby public geospatial reference points."""

    __tablename__ = "geo_contexts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    context_type: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(255))
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    case: Mapped["Case"] = relationship(back_populates="geo_contexts")


class AlertSnapshot(Base):
    """Historical snapshot of an alert state."""

    __tablename__ = "alert_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    case: Mapped["Case"] = relationship(back_populates="alert_snapshots")

