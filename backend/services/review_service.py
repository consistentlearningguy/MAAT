"""Lead review workflow."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.models.investigation import Lead, ReviewDecision


class ReviewService:
    """Persist human review decisions."""

    def __init__(self, db: Session):
        self.db = db

    def review_lead(self, lead_id: int, decision: str, notes: str | None, reviewer: str = "local-investigator") -> Lead:
        """Apply a review decision to a lead."""
        lead = self.db.get(Lead, lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} not found.")
        lead.reviewed = True
        lead.review_status = decision
        lead.human_reason = notes
        lead.review_decisions.append(
            ReviewDecision(reviewer=reviewer, decision=decision, notes=notes)
        )
        self.db.commit()
        self.db.refresh(lead)
        return lead
