from datetime import datetime, timedelta, timezone

from backend.models.case import Case
from backend.osint.normalization.models import NormalizedLead
from backend.osint.scoring.lead_scoring import score_lead


def test_score_lead_returns_rationale_and_score():
    case = Case(
        id=1,
        slug="sample-case",
        name="Sample Case Toronto",
        aliases=["SCT"],
        city="Toronto",
        province="Ontario",
        age=14,
        status="vulnerable",
        case_status="open",
        latitude=43.65,
        longitude=-79.38,
        risk_flags=[],
        source_feed="MCSC",
        is_active=True,
        missing_since=datetime.now(timezone.utc) - timedelta(days=3),
    )
    lead = NormalizedLead(
        connector_name="mock-public-search",
        source_kind="clear-web",
        lead_type="web-mention",
        category="clear-web-search",
        source_name="Mock Search",
        source_url="https://example.org/result",
        query_used='"Sample Case Toronto" Toronto',
        found_at=datetime.now(timezone.utc),
        title="Sample Case Toronto seen near Toronto station",
        summary="Public post references Toronto station.",
        published_at=datetime.now(timezone.utc) - timedelta(days=1),
        location_text="Toronto",
        latitude=43.66,
        longitude=-79.37,
        source_trust=0.5,
        corroboration_count=2,
    )

    scored = score_lead(case, lead)

    assert scored.score > 0.4
    assert scored.rationale
