import asyncio
from datetime import datetime, timezone

from backend.core.config import settings
from backend.osint.connectors.official_artifacts import OfficialArtifactsConnector
from backend.osint.normalization.models import QueryContext


def test_official_artifacts_connector_emits_bulletin_location_and_photo_leads():
    old_investigator = settings.enable_investigator_mode
    settings.enable_investigator_mode = True

    try:
        connector = OfficialArtifactsConnector()
        context = QueryContext(
            case_id=8118,
            name="Zavier Dikken",
            aliases=[],
            city="Sault Ste. Marie",
            province="Ontario",
            age=14,
            missing_since=datetime(2026, 3, 31, 22, 25, tzinfo=timezone.utc),
            location_text="Second Line W, Sault Ste. Marie, ON",
            authority_name="Sault Ste. Marie Police Service",
            authority_case_url="https://www.facebook.com/SaultPolice/posts/example",
            case_reference_url="https://services.arcgis.com/example/query?where=objectid%3D8118&outFields=*",
            source_urls=["https://www.facebook.com/SaultPolice/posts/example"],
            image_urls=["https://services.arcgis.com/example/attachments/14636"],
        )
        result = asyncio.run(connector.run(context))
    finally:
        settings.enable_investigator_mode = old_investigator

    assert len(result.leads) == 3
    assert any(lead.lead_type == "official-bulletin" for lead in result.leads)
    assert any(lead.lead_type == "official-last-seen" for lead in result.leads)
    assert any(lead.lead_type == "official-photo" for lead in result.leads)
    assert result.query_logs[0]["result_count"] == 3


def test_official_artifacts_connector_falls_back_to_case_reference_url_when_authority_link_missing():
    old_investigator = settings.enable_investigator_mode
    settings.enable_investigator_mode = True

    try:
        connector = OfficialArtifactsConnector()
        context = QueryContext(
            case_id=8115,
            name="Sanayah",
            aliases=[],
            city="Toronto",
            province="Ontario",
            age=16,
            missing_since=datetime(2026, 3, 28, 6, 0, tzinfo=timezone.utc),
            location_text="Wynford Dr & Concorde Pl, Toronto, ON",
            authority_name="Toronto Police Service",
            authority_case_url=None,
            case_reference_url="https://services.arcgis.com/example/query?where=objectid%3D8115&outFields=*",
            source_urls=["https://services.arcgis.com/example/query?where=objectid%3D8115&outFields=*"],
            image_urls=["https://services.arcgis.com/example/attachments/14633"],
        )
        result = asyncio.run(connector.run(context))
    finally:
        settings.enable_investigator_mode = old_investigator

    assert any(
        lead.lead_type == "official-bulletin"
        and lead.source_url == "https://services.arcgis.com/example/query?where=objectid%3D8115&outFields=*"
        for lead in result.leads
    )
