from backend.ingestion.mcsc import normalize_case_feature


def test_normalize_case_feature_maps_arcgis_fields():
    feature = {
        "attributes": {
            "objectid": 10,
            "globalid": "abc",
            "status": "vulnerable",
            "casestatus": "open",
            "name": "Sample Child",
            "age": 14,
            "gender": "female",
            "ethnicity": "notlisted",
            "city": "Toronto",
            "province": "Ontario",
            "missing": 1710000000000,
            "description": "<p>Official text</p>",
            "authname": "Toronto Police",
            "authemail": "tips@example.org",
            "authlink": "https://example.org/case",
            "authphone": "416-000-0000",
            "thumb_url": "https://example.org/photo.jpg",
            "mcscemail": "tips@mcsc.ca",
            "mcscphone": "1-800-661-6160",
        },
        "geometry": {"x": -79.38, "y": 43.65},
    }

    record = normalize_case_feature(feature)

    assert record["id"] == 10
    assert record["province"] == "Ontario"
    assert record["status"] == "vulnerable"
    assert record["photos"][0]["url"] == "https://example.org/photo.jpg"
    assert record["source_records"][0]["official"] is True
