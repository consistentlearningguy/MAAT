"""SQLAlchemy models for OSINT investigations, leads, and digital footprint results."""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Text,
    Boolean,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship

from backend.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Investigation(Base):
    """An OSINT investigation run against a missing person case.
    
    Each time we run the digital footprint engine for a case, we create
    one Investigation record. It tracks the overall status and results.
    """

    __tablename__ = "investigations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_objectid = Column(Integer, ForeignKey("missing_cases.objectid"), nullable=False, index=True)
    started_at = Column(DateTime, default=utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="running")  # running, completed, failed, cancelled
    
    # What modules were run
    ran_username_search = Column(Boolean, default=False)
    ran_web_mentions = Column(Boolean, default=False)
    ran_name_lookup = Column(Boolean, default=False)
    ran_face_search = Column(Boolean, default=False)

    # Summary counts
    total_leads = Column(Integer, default=0)
    high_confidence_leads = Column(Integer, default=0)

    error_message = Column(Text, nullable=True)

    # Relationships
    case = relationship("MissingCase", backref="investigations")
    leads = relationship("Lead", back_populates="investigation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Investigation(id={self.id}, case={self.case_objectid}, status='{self.status}')>"

    def to_dict(self):
        return {
            "id": self.id,
            "case_objectid": self.case_objectid,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "ran_username_search": self.ran_username_search,
            "ran_web_mentions": self.ran_web_mentions,
            "ran_name_lookup": self.ran_name_lookup,
            "ran_face_search": self.ran_face_search,
            "total_leads": self.total_leads,
            "high_confidence_leads": self.high_confidence_leads,
            "error_message": self.error_message,
        }


class Lead(Base):
    """A single intelligence lead from any OSINT module.
    
    This is the core output of the investigation system. Each lead represents
    a potential piece of information that could help locate the missing person.
    
    Lead types:
    - username_hit: A matching username found on a platform
    - web_mention: A mention of the person's name on the web
    - social_post: A specific social media post mentioning the person
    - news_article: A news article about the case
    - forum_post: A forum discussion about the case or sighting
    - sighting_report: Someone reporting they saw the person
    - face_match: A face similarity match from image comparison
    """

    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    investigation_id = Column(Integer, ForeignKey("investigations.id"), nullable=False, index=True)
    case_objectid = Column(Integer, ForeignKey("missing_cases.objectid"), nullable=False, index=True)

    # What kind of lead
    lead_type = Column(String(30), nullable=False, index=True)
    # username_hit, web_mention, social_post, news_article, forum_post, sighting_report

    # Source information
    source_platform = Column(String(100), nullable=True)  # e.g. "instagram", "reddit", "google_news"
    source_url = Column(String(1000), nullable=True)  # Direct URL to the evidence
    source_name = Column(String(200), nullable=True)  # Human-readable source name

    # The actual finding
    title = Column(String(500), nullable=True)  # Short description of the lead
    content = Column(Text, nullable=True)  # Full text content / details
    matched_query = Column(String(200), nullable=True)  # What search query produced this

    # For username hits specifically
    username_found = Column(String(200), nullable=True)
    platform_url = Column(String(1000), nullable=True)
    account_exists = Column(Boolean, nullable=True)

    # Location information (if the lead contains location data)
    location_text = Column(String(300), nullable=True)  # e.g. "Vancouver, BC"
    location_lat = Column(Float, nullable=True)
    location_lng = Column(Float, nullable=True)

    # Timing
    found_at = Column(DateTime, default=utcnow, nullable=False)
    content_date = Column(DateTime, nullable=True)  # When the content was posted/published

    # Confidence scoring (0.0 to 1.0)
    confidence = Column(Float, default=0.0, nullable=False)
    
    # Has an analyst reviewed this lead?
    reviewed = Column(Boolean, default=False)
    review_notes = Column(Text, nullable=True)
    is_actionable = Column(Boolean, nullable=True)  # null=unreviewed, True=useful, False=noise

    # Relationships
    investigation = relationship("Investigation", back_populates="leads")

    __table_args__ = (
        Index("ix_lead_case_type", "case_objectid", "lead_type"),
        Index("ix_lead_confidence", "confidence"),
    )

    def __repr__(self):
        return f"<Lead(id={self.id}, type='{self.lead_type}', confidence={self.confidence:.2f})>"

    def to_dict(self):
        return {
            "id": self.id,
            "investigation_id": self.investigation_id,
            "case_objectid": self.case_objectid,
            "lead_type": self.lead_type,
            "source_platform": self.source_platform,
            "source_url": self.source_url,
            "source_name": self.source_name,
            "title": self.title,
            "content": self.content,
            "matched_query": self.matched_query,
            "username_found": self.username_found,
            "platform_url": self.platform_url,
            "account_exists": self.account_exists,
            "location_text": self.location_text,
            "location_lat": self.location_lat,
            "location_lng": self.location_lng,
            "found_at": self.found_at.isoformat() if self.found_at else None,
            "content_date": self.content_date.isoformat() if self.content_date else None,
            "confidence": self.confidence,
            "reviewed": self.reviewed,
            "review_notes": self.review_notes,
            "is_actionable": self.is_actionable,
        }
