import json
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from app.core.config import Settings
from app.schemas.card import CardUploadGroup, ImageAnalysis, ProductInput
from app.services.card_flow import CardFlowService
from app.services.gemini_analyzer import GeminiAnalyzer


def _image_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (48, 72), color=(55, 95, 145)).save(buffer, format="JPEG")
    return buffer.getvalue()


def test_primary_analysis_returns_card_and_image_generation_data_in_one_call(monkeypatch):
    analyzer = GeminiAnalyzer(Settings(gemini_api_key="test-key"))
    calls = 0
    raw = {
        "category": "pants",
        "product_name": "wide trousers",
        "material": "linen",
        "color": "blue",
        "gender": "female",
        "fit_type": "wide",
        "features": ["front pockets", "drawstring waist"],
        "confidence": 0.9,
        "garment_analysis": {
            "product_type": "wide trousers",
            "garment_area": "lower_body",
            "category": "pants",
            "gender": "female",
            "main_color": "blue",
            "secondary_colors": [],
            "material": "linen",
            "fabric_texture": "woven",
            "silhouette": "wide",
            "fit": "relaxed",
            "length": "full length",
            "waist": "drawstring waist",
            "neckline": "none",
            "sleeves": "none",
            "closure": "drawstring",
            "pockets": "front pockets",
            "hem": "straight",
            "logo_or_text": "none",
            "front_view": {"description": "Wide trousers", "key_details": ["front pockets"]},
            "back_view": {"description": "Plain back", "key_details": []},
            "special_details": ["drawstring waist"],
            "must_preserve": ["front pockets", "drawstring waist"],
            "must_not_change": ["wide silhouette"],
            "prompt_summary": "Wide linen trousers",
        },
    }

    def generate_content(*args, **kwargs):
        nonlocal calls
        calls += 1
        return SimpleNamespace(text=json.dumps(raw))

    monkeypatch.setattr(analyzer._client.models, "generate_content", generate_content)

    result = analyzer.analyze([_image_bytes()], ProductInput(category="pants"))

    assert calls == 1
    assert result.category == "pants"
    assert result.material == "linen"
    assert result.garment_json["garment_area"] == "lower_body"
    assert result.garment_json["pockets"] == "front pockets"
    assert result.garment_json["color_palette"]
    assert "front pockets" in result.garment_json["must_preserve"]
    assert result.garment_json["analysis_source"] == "primary_product_vision"
    assert result.garment_json["provider_garment_fallback_used"] is False


def test_primary_analysis_builds_safe_garment_fallback_when_provider_omits_it(monkeypatch):
    analyzer = GeminiAnalyzer(Settings(gemini_api_key="test-key"))
    raw = {
        "category": "skirt",
        "product_name": "midi skirt",
        "material": "cotton",
        "color": "black",
        "gender": "female",
        "fit_type": "a-line",
        "features": ["side zipper"],
        "confidence": 0.7,
    }
    monkeypatch.setattr(
        analyzer._client.models,
        "generate_content",
        lambda *args, **kwargs: SimpleNamespace(text=json.dumps(raw)),
    )

    result = analyzer.analyze([_image_bytes()], ProductInput(category="skirt"))

    assert result.garment_json["garment_area"] == "lower_body"
    assert result.garment_json["product_type"] == "midi skirt"
    assert result.garment_json["source_category"] == "skirt"
    assert "side zipper" in result.garment_json["must_preserve"]
    assert result.garment_json["provider_garment_fallback_used"] is True


def test_primary_analysis_switches_model_after_transient_failures(monkeypatch):
    analyzer = GeminiAnalyzer(
        Settings(
            gemini_api_key="test-key",
            gemini_model="gemini-2.5-flash",
            gemini_fallback_model="gemini-2.5-flash-lite",
            gemini_analysis_retry_attempts=2,
            gemini_retry_backoff_seconds=0.1,
        )
    )
    calls = []

    def generate_content(*args, **kwargs):
        model = kwargs["model"]
        calls.append(model)
        if model == "gemini-2.5-flash":
            raise Exception("503 UNAVAILABLE high demand")
        return SimpleNamespace(
            text=json.dumps(
                {
                    "category": "Брюки",
                    "product_name": "Брюки",
                    "color": "черный",
                    "features": [],
                    "confidence": 0.8,
                }
            )
        )

    monkeypatch.setattr(analyzer._client.models, "generate_content", generate_content)
    monkeypatch.setattr("app.services.gemini_analyzer.time.sleep", lambda _delay: None)
    monkeypatch.setattr("app.services.gemini_analyzer.random.uniform", lambda *_args: 0)

    result = analyzer.analyze([_image_bytes()], ProductInput(category="Брюки"))

    assert calls == ["gemini-2.5-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
    assert result.garment_json["analysis_model"] == "gemini-2.5-flash-lite"
    assert result.garment_json["analysis_fallback_used"] is True


@pytest.mark.anyio
async def test_generate_draft_persists_canonical_garment_analysis_for_image_jobs(monkeypatch):
    image_bytes = _image_bytes()
    analysis = ImageAnalysis(
        category="pants",
        product_name="wide trousers",
        material="linen",
        fit_type="wide",
        garment_json={
            "product_type": "wide trousers",
            "category": "pants",
            "garment_area": "lower_body",
            "material": "linen",
            "fit": "wide",
            "front_view": {"description": "wide trousers", "key_details": ["front pockets"]},
            "back_view": {"description": "plain back", "key_details": []},
            "must_preserve": ["front pockets"],
        },
    )
    card_payload = [
        CardUploadGroup.model_validate(
            {
                "subjectID": 12,
                "variants": [
                    {
                        "vendorCode": "TEST-1",
                        "title": "Wide trousers",
                        "description": "Comfortable wide trousers with a clean silhouette for everyday wear. " * 2,
                        "brand": "No brand",
                        "dimensions": {"length": 30, "width": 20, "height": 4, "weightBrutto": 0.4},
                        "characteristics": [{"id": 1, "value": ["wide"]}],
                        "sizes": [{"techSize": "S", "wbSize": "S", "skus": []}],
                    }
                ],
            }
        )
    ]

    class FakeGeminiAnalyzer:
        def __init__(self, settings):
            pass

        def analyze(self, images, user_input):
            return analysis

    class FakeCardGenerator:
        def __init__(self, settings):
            pass

        def generate(self, user_input, image_analysis, subject, charcs):
            return card_payload

    class FakeDb:
        def add(self, item):
            self.item = item

        def commit(self):
            pass

        def refresh(self, item):
            pass

    monkeypatch.setattr("app.services.card_flow.GeminiAnalyzer", FakeGeminiAnalyzer)
    monkeypatch.setattr("app.services.card_flow.CardGenerator", FakeCardGenerator)

    service = CardFlowService.__new__(CardFlowService)
    service._settings = Settings(gemini_api_key="test-key")
    service._db = FakeDb()
    service._user = SimpleNamespace(id=1)
    service._store = SimpleNamespace(id=2)
    service._resolve_subject = AsyncMock(return_value={"subjectID": 12, "subjectName": "pants"})
    service._wb = SimpleNamespace(get_subject_charcs=AsyncMock(return_value=[]))
    service._enrich_payload = AsyncMock(return_value=None)

    draft = await service.generate_draft([image_bytes], ProductInput(category="pants"))

    assert draft.garment_json["garment_area"] == "lower_body"
    assert draft.garment_json["source_title"] == "Wide trousers"
    assert draft.analysis["garment_json"] == draft.garment_json


@pytest.mark.anyio
async def test_suggest_tnved_reranks_candidates_with_fashion_hint():
    service = CardFlowService.__new__(CardFlowService)
    service._wb = SimpleNamespace(
        get_tnved=AsyncMock(
            return_value=[
                {"tnved": "6203421100", "name": "Брюки мужские из хлопчатобумажной ткани, не трикотажные"},
                {"tnved": "6204623100", "name": "Брюки женские из хлопчатобумажной ткани, не трикотажные"},
            ]
        )
    )

    result = await service.suggest_tnved(
        11,
        subject_name="Брюки",
        category="брюки",
        gender="женский",
        material="хлопок",
    )

    assert result["selected"]["tnved"] == "6204623100"
    assert result["data"][0]["tnved"] == "6204623100"
