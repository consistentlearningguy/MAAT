from backend.ingestion.mcsc import normalize_case_feature


def test_normalize_case_feature_prefers_official_summary_location_when_fields_conflict():
    feature = {
        "attributes": {
            "objectid": 8118,
            "globalid": "{sample-guid}",
            "status": "vulnerable",
            "casestatus": "open",
            "name": "Zavier Dikken",
            "age": 14,
            "gender": "boy",
            "ethnicity": "caucasian",
            "city": "Sault Ste. Marie",
            "province": "BritishColumbia",
            "missing": 1774995900000,
            "description": (
                "<b>Missing Since: </b> March 31, 2026, approx. 7:25PM\n"
                "<b>Location: </b> Second Line W, Sault Ste. Marie, ON\n"
                "<b>Last Seen Wearing: </b> Blue plaid jacket"
            ),
            "authname": "Sault Ste. Marie Police Service",
            "authemail": "",
            "authlink": "https://www.facebook.com/SaultPolice/posts/example",
            "authphone": "705-949-6300",
            "authphonetwo": "",
            "thumb_url": "https://example.org/thumb.jpg",
            "pic_url": "https://example.org/photo.jpg",
            "mcscemail": "tips@mcsc.ca",
            "mcscphone": "",
            "CreationDate": 1774995900000,
            "EditDate": 1774999500000,
        },
        "geometry": {"x": -84.37319181827382, "y": 46.537204347591846},
    }

    normalized = normalize_case_feature(feature)

    assert normalized["city"] == "Sault Ste. Marie"
    assert normalized["province"] == "Ontario"
    assert "official-field-conflict" in normalized["risk_flags"]
    assert normalized["source_records"][0]["metadata_json"]["official_location_text"] == "Second Line W, Sault Ste. Marie, ON"
