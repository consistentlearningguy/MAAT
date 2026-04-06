from backend.enrichment.official_context import extract_official_context


def test_extract_official_context_parses_location_descriptors_and_conflicts():
    context = extract_official_context(
        (
            "<b>Missing Since: </b> March 31, 2026, approx. 7:25PM\n"
            "<b>Location: </b> Second Line W, Sault Ste. Marie, ON\n"
            "<b>Height: </b> 5'4\"\n"
            "<b>Hair Color: </b> Straight brown hair\n"
            "<b>Eye Color: </b> Blue\n"
            "<b>Last Seen Wearing: </b> Blue plaid jacket"
        ),
        city="Sault Ste. Marie",
        province="British Columbia",
    )

    assert context["location_text"] == "Second Line W, Sault Ste. Marie, ON"
    assert context["inferred_city"] == "Sault Ste. Marie"
    assert context["inferred_province"] == "Ontario"
    assert any("Hair Straight brown hair" in chip for chip in context["descriptor_chips"])
    assert context["quality_warnings"]
