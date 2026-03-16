"""SQLAlchemy models for face encodings and cross-case face matches.

Each case photo can contain zero or more faces. We extract each face,
crop it, compute a 128-dimensional encoding (via face_recognition / dlib),
and store it here. This allows:

1. Cross-case comparison: find cases whose photos share similar faces
2. Upload comparison: match an uploaded image against all known faces
3. Reverse image search input: use the cropped face for PimEyes / Yandex / etc.
"""

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
    LargeBinary,
)
from sqlalchemy.orm import relationship

from backend.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class FaceEncoding(Base):
    """A single face detected in a case photo.

    One CasePhoto can have multiple FaceEncoding rows (group photos).
    The encoding is a 128-dim float vector serialized as bytes (numpy .tobytes()).
    """

    __tablename__ = "face_encodings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_objectid = Column(Integer, ForeignKey("missing_cases.objectid"), nullable=False, index=True)
    photo_id = Column(Integer, ForeignKey("case_photos.id"), nullable=False, index=True)

    # The 128-dimensional face encoding (numpy float64 array, 1024 bytes)
    encoding = Column(LargeBinary(1024), nullable=False)

    # Face location in the source image (top, right, bottom, left in pixels)
    face_top = Column(Integer, nullable=True)
    face_right = Column(Integer, nullable=True)
    face_bottom = Column(Integer, nullable=True)
    face_left = Column(Integer, nullable=True)

    # Path to the cropped face image (relative to data/faces/)
    crop_path = Column(String(500), nullable=True)

    # Quality / metadata
    face_index = Column(Integer, default=0)  # 0-based index if multiple faces in photo
    encoding_model = Column(String(50), default="dlib_cnn")  # which model produced this

    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    photo = relationship("CasePhoto", backref="face_encodings")
    case = relationship("MissingCase", backref="face_encodings")

    __table_args__ = (
        Index("ix_face_case_photo", "case_objectid", "photo_id"),
    )

    def __repr__(self):
        return (
            f"<FaceEncoding(id={self.id}, case={self.case_objectid}, "
            f"photo={self.photo_id}, face_idx={self.face_index})>"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "case_objectid": self.case_objectid,
            "photo_id": self.photo_id,
            "face_top": self.face_top,
            "face_right": self.face_right,
            "face_bottom": self.face_bottom,
            "face_left": self.face_left,
            "crop_path": self.crop_path,
            "face_index": self.face_index,
            "encoding_model": self.encoding_model,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class FaceMatch(Base):
    """A match between two face encodings from different cases.

    This records cross-case face similarity discoveries. A match means
    the face from case A looks similar to the face from case B above
    a configurable threshold.
    """

    __tablename__ = "face_matches"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # The two faces being compared
    face_a_id = Column(Integer, ForeignKey("face_encodings.id"), nullable=False, index=True)
    face_b_id = Column(Integer, ForeignKey("face_encodings.id"), nullable=False, index=True)

    # The cases they belong to
    case_a_objectid = Column(Integer, ForeignKey("missing_cases.objectid"), nullable=False)
    case_b_objectid = Column(Integer, ForeignKey("missing_cases.objectid"), nullable=False)

    # Euclidean distance (lower = more similar, <0.6 is typically same person)
    distance = Column(Float, nullable=False)
    # Confidence (1.0 - distance, clamped to [0, 1])
    confidence = Column(Float, nullable=False)

    # Has an analyst reviewed this match?
    reviewed = Column(Boolean, default=False)
    review_notes = Column(Text, nullable=True)
    is_same_person = Column(Boolean, nullable=True)  # None=unreviewed

    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    face_a = relationship("FaceEncoding", foreign_keys=[face_a_id], backref="matches_as_a")
    face_b = relationship("FaceEncoding", foreign_keys=[face_b_id], backref="matches_as_b")

    __table_args__ = (
        Index("ix_match_cases", "case_a_objectid", "case_b_objectid"),
        Index("ix_match_confidence", "confidence"),
    )

    def __repr__(self):
        return (
            f"<FaceMatch(id={self.id}, case_a={self.case_a_objectid}, "
            f"case_b={self.case_b_objectid}, dist={self.distance:.3f})>"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "face_a_id": self.face_a_id,
            "face_b_id": self.face_b_id,
            "case_a_objectid": self.case_a_objectid,
            "case_b_objectid": self.case_b_objectid,
            "distance": self.distance,
            "confidence": self.confidence,
            "reviewed": self.reviewed,
            "review_notes": self.review_notes,
            "is_same_person": self.is_same_person,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
