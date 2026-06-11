import pytest

from app.core.config import Settings
from app.schemas.card import ImageAnalysis, ProductInput
from app.services.subject_resolver import SubjectResolver


class FakeWbClient:
    def __init__(self, subjects):
        self._subjects = subjects
        self.calls = []

    async def get_subjects(self, parent_id=None, locale="ru"):
        self.calls.append((parent_id, locale))
        return self._subjects


@pytest.mark.anyio
async def test_resolve_subject_uses_ai_candidate_for_multilingual_misspelled_note(monkeypatch):
    subjects = [
        {"subjectID": 11, "subjectName": "Брюки"},
        {"subjectID": 12, "subjectName": "Джинсы"},
    ]
    resolver = SubjectResolver(Settings(app_env="test", app_secret_key="test-secret-key"), FakeWbClient(subjects))

    def fake_ai(subjects_arg, source_text):
        assert "1130" in source_text
        assert subjects_arg == subjects
        return subjects[1]

    monkeypatch.setattr(resolver, "_resolve_with_ai", fake_ai)

    subject = await resolver.resolve(
        ProductInput(
            category="quâng bò nữ cạp cao màu xanh dương đậm, mã 1130, size 25-38, 26-40",
        ),
        ImageAnalysis(category=None),
    )

    assert subject["subjectID"] == 12


def test_subject_resolver_strips_sku_size_dimensions_noise():
    normalized = SubjectResolver._strip_noise(
        "quần bò nữ cạp cao màu xanh dương đậm, mã 1130, size 25-38, 26-40, kích thước 28 22 2"
    )

    assert "quần bò" in normalized
    assert "1130" not in normalized
    assert "25-38" not in normalized


def test_ai_match_must_be_verified_against_real_wb_subjects():
    subjects = [{"subjectID": 12, "subjectName": "Джинсы"}]
    hallucinated = {"candidates": [{"subjectName": "Magic Pants", "confidence": 0.99}]}

    assert SubjectResolver._verified_ai_match(subjects, hallucinated) is None


@pytest.mark.anyio
async def test_resolve_subject_searches_all_subjects_and_keeps_product_terms_after_size(monkeypatch):
    subjects = [
        {"subjectID": 1429, "subjectName": "\u0411\u043b\u0443\u0437\u043a\u0438-\u0431\u043e\u0434\u0438"},
        {"subjectID": 256, "subjectName": "\u0422\u0440\u0443\u0441\u044b"},
    ]
    wb_client = FakeWbClient(subjects)
    resolver = SubjectResolver(Settings(app_env="test", app_secret_key="test-secret-key"), wb_client)
    monkeypatch.setattr(resolver, "_resolve_with_ai", lambda subjects_arg, source_text: None)
    description = (
        "combo bo 5 quan lot tre em, size S(86-92), M(122-128), 20x20x2, can nang 0.3, "
        "\u0422\u0440\u0443\u0441\u044b \u041d\u0430\u0431\u043e\u0440 \u0442\u0440\u0443\u0441\u043e\u0432 "
        "\u0434\u043b\u044f \u043c\u0430\u043b\u044c\u0447\u0438\u043a\u043e\u0432"
    )

    subject = await resolver.resolve(ProductInput(category=description), ImageAnalysis(category=None))

    assert subject["subjectID"] == 256
    assert wb_client.calls == [(None, "ru")]
    assert "\u0442\u0440\u0443\u0441\u044b" in SubjectResolver._strip_noise(description)
