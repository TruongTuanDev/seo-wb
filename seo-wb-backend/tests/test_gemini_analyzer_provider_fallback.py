import json
from io import BytesIO

import pytest
from PIL import Image

from app.core.config import Settings
from app.core.errors import AppError
from app.schemas.card import ProductInput
from app.services.gemini_analyzer import GeminiAnalyzer


def _image_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (24, 24), color=(20, 40, 80)).save(buffer, format="JPEG")
    return buffer.getvalue()


def test_gemini_quota_error_falls_back_to_openai_without_retry(monkeypatch):
    analyzer = GeminiAnalyzer(
        Settings(
            app_env="test",
            app_secret_key="test-secret-key",
            gemini_api_key="test-gemini",
            openai_api_key="test-openai",
            openai_card_model="gpt-4.1-mini",
        )
    )
    calls = {"gemini": 0, "openai": 0}

    def fail_gemini(*args, **kwargs):
        calls["gemini"] += 1
        raise Exception("429 RESOURCE_EXHAUSTED: prepayment credits are depleted")

    def openai_fallback(*args, **kwargs):
        calls["openai"] += 1
        return json.dumps({"category": "Брюки", "product_name": "Брюки", "confidence": 0.8})

    monkeypatch.setattr(analyzer._client.models, "generate_content", fail_gemini)
    monkeypatch.setattr(analyzer, "_analyze_with_openai", openai_fallback)

    result = analyzer.analyze([_image_bytes()], ProductInput())

    assert result.category == "Брюки"
    assert calls == {"gemini": 1, "openai": 1}
    assert any("OpenAI fallback" in warning for warning in result.warnings)


def test_image_analysis_returns_clear_error_when_all_providers_fail(monkeypatch):
    analyzer = GeminiAnalyzer(
        Settings(
            app_env="test",
            app_secret_key="test-secret-key",
            gemini_api_key="test-gemini",
            openai_api_key="test-openai",
            openai_card_model="gpt-4.1-mini",
        )
    )

    monkeypatch.setattr(
        analyzer._client.models,
        "generate_content",
        lambda *args, **kwargs: (_ for _ in ()).throw(Exception("429 RESOURCE_EXHAUSTED")),
    )
    monkeypatch.setattr(
        analyzer,
        "_analyze_with_openai",
        lambda *args, **kwargs: (_ for _ in ()).throw(Exception("OpenAI unavailable")),
    )

    with pytest.raises(AppError) as exc_info:
        analyzer.analyze([_image_bytes()], ProductInput())

    assert exc_info.value.code == "image_analysis_failed"
    assert exc_info.value.status_code == 503


def test_non_retryable_quota_error_detection():
    assert GeminiAnalyzer._is_non_retryable_quota_error(Exception("RESOURCE_EXHAUSTED"))
    assert GeminiAnalyzer._is_non_retryable_quota_error(Exception("Prepayment credits are depleted"))
    assert not GeminiAnalyzer._is_non_retryable_quota_error(Exception("Temporary connection reset"))
