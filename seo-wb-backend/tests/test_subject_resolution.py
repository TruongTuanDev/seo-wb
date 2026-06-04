import pytest

from app.core.config import Settings
from app.schemas.card import ImageAnalysis, ProductInput
from app.services.subject_resolver import SubjectResolver


class FakeWbClient:
    def __init__(self, subjects):
        self._subjects = subjects

    async def get_subjects(self, parent_id=None, locale="ru"):
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
