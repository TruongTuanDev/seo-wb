from app.schemas.card import ImageAnalysis
from app.services.card_payload_enricher import CardPayloadEnricher


def test_enricher_maps_all_season_to_wb_directory_value():
    payload = {
        "variants": [
            {
                "characteristics": [{"id": 18769, "value": ["всесезонный"]}],
            }
        ]
    }
    enricher = CardPayloadEnricher(
        [{"charcID": 18769, "name": "Сезон", "maxCount": 1}],
        directories={"season": ["круглогодичный", "лето", "демисезон", "зима"]},
    )

    enricher.enrich_payload(payload, subject_id=180, analysis=ImageAnalysis(season="всесезонный"))

    assert payload["variants"][0]["characteristics"] == [{"id": 18769, "value": ["круглогодичный"]}]


def test_enricher_drops_unknown_optional_dictionary_value():
    payload = {"variants": [{"characteristics": [{"id": 18769, "value": ["unknown-season"]}]}]}
    enricher = CardPayloadEnricher(
        [{"charcID": 18769, "name": "Сезон", "maxCount": 1}],
        directories={"season": ["круглогодичный", "лето", "демисезон", "зима"]},
    )

    enricher.enrich_payload(payload, subject_id=180, analysis=ImageAnalysis(season="unknown-season"))

    assert payload["variants"][0]["characteristics"] == []


def test_enricher_synchronizes_vendor_code_with_final_color():
    payload = {
        "variants": [
            {
                "vendorCode": "345/Синий",
                "characteristics": [{"id": 14177449, "value": ["Черный"]}],
            }
        ]
    }
    enricher = CardPayloadEnricher(
        [{"charcID": 14177449, "name": "Цвет", "maxCount": 5}],
    )

    enricher.enrich_payload(payload, subject_id=11)

    assert payload["variants"][0]["vendorCode"] == "345/Черный"
