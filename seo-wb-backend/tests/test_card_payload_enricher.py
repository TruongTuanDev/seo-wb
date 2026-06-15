from app.schemas.card import ImageAnalysis, ProductInput
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


def test_enricher_adds_underwear_specific_filters_when_schema_supports_them():
    payload = {"variants": [{"characteristics": []}]}
    enricher = CardPayloadEnricher(
        [
            {"charcID": 1, "name": "Назначение", "maxCount": 3},
            {"charcID": 2, "name": "Особенности белья", "maxCount": 3},
            {"charcID": 3, "name": "Возрастные ограничения", "maxCount": 1},
        ]
    )

    enricher.enrich_payload(
        payload,
        subject_id=180,
        user_input=ProductInput(note="для мальчиков 3-7 лет"),
        analysis=ImageAnalysis(product_name="Набор трусов-боксеров", gender="мальчики"),
    )

    assert payload["variants"][0]["characteristics"] == [
        {"id": 1, "value": ["повседневная", "в школу", "для спорта"]},
        {"id": 2, "value": ["мягкая резинка", "дышащий материал", "анатомический крой"]},
        {"id": 3, "value": ["3-7 лет"]},
    ]


def test_age_limits_do_not_fall_back_to_height():
    payload = {"variants": [{"characteristics": []}]}
    enricher = CardPayloadEnricher([{"charcID": 3, "name": "Возрастные ограничения", "maxCount": 1}])

    enricher.enrich_payload(
        payload,
        subject_id=180,
        user_input=ProductInput(),
        analysis=ImageAnalysis(
            product_name="Набор трусов-боксеров",
            gender="мальчики",
            sizes=[{"techSize": "S", "wbSize": "86-92"}],
        ),
    )

    assert payload["variants"][0]["characteristics"] == []
