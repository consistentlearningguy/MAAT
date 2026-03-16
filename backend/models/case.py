"""SQLAlchemy models for missing persons cases, photos, and sync logs."""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Text,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship

from backend.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class MissingCase(Base):
    """A missing person case from MCSC."""

    __tablename__ = "missing_cases"

    # Primary key from ArcGIS objectid
    objectid = Column(Integer, primary_key=True, index=True)
    globalid = Column(String(38), unique=True, nullable=True)

    # Person details
    name = Column(String(100), nullable=True, index=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    ethnicity = Column(String(100), nullable=True)

    # Location
    city = Column(String(100), nullable=True, index=True)
    province = Column(String(100), nullable=True, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # Case details
    missing_since = Column(DateTime, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=True, index=True)  # vulnerable, abudction, amberalert, etc.
    case_status = Column(String(20), nullable=True, index=True)  # open, located, archived, expired

    # Authority contact
    authority_name = Column(String(200), nullable=True)
    authority_email = Column(String(100), nullable=True)
    authority_phone = Column(String(50), nullable=True)
    authority_phone_alt = Column(String(50), nullable=True)
    authority_link = Column(String(255), nullable=True)

    # Photos
    photo_url = Column(String(500), nullable=True)
    thumb_url = Column(String(500), nullable=True)

    # Sync tracking
    first_synced_at = Column(DateTime, default=utcnow)
    last_synced_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Timestamps from ArcGIS
    arcgis_created_at = Column(DateTime, nullable=True)
    arcgis_updated_at = Column(DateTime, nullable=True)

    # Relationships
    photos = relationship("CasePhoto", back_populates="case", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_province_status", "province", "case_status"),
        Index("ix_missing_since", "missing_since"),
    )

    def __repr__(self):
        return f"<MissingCase(objectid={self.objectid}, name='{self.name}', province='{self.province}')>"

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "objectid": self.objectid,
            "globalid": self.globalid,
            "name": self.name,
            "age": self.age,
            "gender": self.gender,
            "ethnicity": self.ethnicity,
            "city": self.city,
            "province": self.province,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "missing_since": self.missing_since.isoformat() if self.missing_since else None,
            "description": self.description,
            "status": self.status,
            "case_status": self.case_status,
            "authority_name": self.authority_name,
            "authority_email": self.authority_email,
            "authority_phone": self.authority_phone,
            "authority_phone_alt": self.authority_phone_alt,
            "authority_link": self.authority_link,
            "photo_url": self.photo_url,
            "thumb_url": self.thumb_url,
            "first_synced_at": self.first_synced_at.isoformat() if self.first_synced_at else None,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "photos": [p.to_dict() for p in self.photos] if self.photos else [],
        }

    def to_geojson_feature(self):
        """Convert to GeoJSON Feature for map rendering."""
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [self.longitude, self.latitude],
            }
            if self.latitude and self.longitude
            else None,
            "properties": {
                "objectid": self.objectid,
                "name": self.name,
                "age": self.age,
                "city": self.city,
                "province": self.province,
                "missing_since": self.missing_since.isoformat() if self.missing_since else None,
                "status": self.status,
                "case_status": self.case_status,
                "photo_url": self.photo_url,
                "thumb_url": self.thumb_url,
            },
        }


class CasePhoto(Base):
    """Photo attachment for a missing person case."""

    __tablename__ = "case_photos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_objectid = Column(Integer, ForeignKey("missing_cases.objectid"), nullable=False, index=True)
    attachment_id = Column(Integer, nullable=False)
    url = Column(String(500), nullable=True)
    local_path = Column(String(500), nullable=True)
    content_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=True)
    downloaded_at = Column(DateTime, nullable=True)

    # Relationship
    case = relationship("MissingCase", back_populates="photos")

    def __repr__(self):
        return f"<CasePhoto(id={self.id}, case={self.case_objectid}, attachment={self.attachment_id})>"

    def to_dict(self):
        return {
            "id": self.id,
            "case_objectid": self.case_objectid,
            "attachment_id": self.attachment_id,
            "url": self.url,
            "local_path": self.local_path,
            "content_type": self.content_type,
            "file_size": self.file_size,
            "downloaded_at": self.downloaded_at.isoformat() if self.downloaded_at else None,
        }


class SyncLog(Base):
    """Log of each data synchronization run."""

    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime, default=utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    cases_added = Column(Integer, default=0)
    cases_updated = Column(Integer, default=0)
    cases_removed = Column(Integer, default=0)
    photos_downloaded = Column(Integer, default=0)
    total_cases = Column(Integer, default=0)
    status = Column(String(20), default="running")  # running, completed, failed
    error_message = Column(Text, nullable=True)

    def __repr__(self):
        return f"<SyncLog(id={self.id}, status='{self.status}', added={self.cases_added})>"

    def to_dict(self):
        return {
            "id": self.id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "cases_added": self.cases_added,
            "cases_updated": self.cases_updated,
            "cases_removed": self.cases_removed,
            "photos_downloaded": self.photos_downloaded,
            "total_cases": self.total_cases,
            "status": self.status,
            "error_message": self.error_message,
        }
