from datetime import datetime, timezone

from backend.models.case import Case, CasePhoto
from backend.osint.resource_pack import build_case_resource_pack


def test_build_case_resource_pack_returns_grouped_trace_labs_style_resources():
    case = Case(
        id=1,
        slug="sample-case",
        name="Sample Case Toronto",
        aliases=["SCT"],
        city="Toronto",
        province="Ontario",
        age=14,
        status="missing",
        case_status="open",
        source_feed="MCSC",
        source_url="https://mcsc.ca/case/sample-case",
        authority_case_url="https://police.example.org/case/sample-case",
        is_active=True,
        missing_since=datetime(2026, 3, 14, tzinfo=timezone.utc),
        official_summary_html=(
            "<b>Missing Since: </b> March 14, 2026, approx. 9:00PM\n"
            "<b>Location: </b> Main St, Toronto, ON\n"
            "<b>Height: </b> 5'4\"\n"
            "<b>Last Seen Wearing: </b> blue jacket"
        ),
    )
    case.photos.append(
        CasePhoto(
            url="https://example.org/case-photo.jpg",
            thumb_url="https://example.org/case-photo.jpg",
            is_primary=True,
        )
    )

    pack = build_case_resource_pack(case)

    assert pack["case_id"] == case.id
    assert pack["groups"]
    assert pack["official_context"]["location_text"] == "Main St, Toronto, ON"
    assert pack["coverage"]["categories"]
    assert pack["coverage"]["next_steps"]
    assert any(group["slug"] == "official-cross-check" for group in pack["groups"])
    assert any(group["slug"] == "social-profile-sweep" for group in pack["groups"])
    assert any(group["slug"] == "news-archive-monitoring" for group in pack["groups"])
    assert any(group["slug"] == "geo-open-data" for group in pack["groups"])
    assert any(group["slug"] == "photo-archive-geo" for group in pack["groups"])

    photo_group = next(group for group in pack["groups"] if group["slug"] == "photo-archive-geo")
    reverse_image_item = next(item for item in photo_group["items"] if item["label"] == "Reverse-Image Pivot")
    assert reverse_image_item["target_value"] == "https://example.org/case-photo.jpg"

    social_group = next(group for group in pack["groups"] if group["slug"] == "social-profile-sweep")
    assert social_group["items"][0]["launchers"]

    official_group = next(group for group in pack["groups"] if group["slug"] == "official-cross-check")
    assert any(item.get("target_value") == "https://police.example.org/case/sample-case" for item in official_group["items"])
    assert any(item["label"] == "Official Last-Seen Anchor" for item in official_group["items"])
