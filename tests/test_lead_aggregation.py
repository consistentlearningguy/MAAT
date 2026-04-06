from datetime import datetime, timezone

from backend.osint.aggregation import merge_normalized_leads
from backend.osint.normalization.models import NormalizedLead


def test_merge_normalized_leads_combines_duplicates_and_rationale():
    found_at = datetime.now(timezone.utc)
    leads = [
        NormalizedLead(
            connector_name="connector-a",
            source_kind="clear-web",
            lead_type="web-mention",
            category="clear-web-search",
            source_name="Source A",
            source_url="https://example.org/post?utm_source=test",
            query_used='"Sample" Toronto',
            found_at=found_at,
            title="Public post",
            summary="First summary",
            source_trust=0.4,
            rationale=["Matched on name query."],
        ),
        NormalizedLead(
            connector_name="connector-b",
            source_kind="clear-web",
            lead_type="web-mention",
            category="clear-web-search",
            source_name="Source B",
            source_url="https://example.org/post",
            query_used='"Sample" Ontario',
            found_at=found_at,
            title="Public post",
            summary="Second, longer summary for analysts.",
            source_trust=0.7,
            rationale=["Matched on province query."],
        ),
    ]

    merged = merge_normalized_leads(leads)

    assert len(merged) == 1
    assert merged[0].corroboration_count >= 2
    assert merged[0].source_trust == 0.7
    assert merged[0].summary == "Second, longer summary for analysts."
    assert any("multiple public query variants" in reason.lower() for reason in merged[0].rationale)
