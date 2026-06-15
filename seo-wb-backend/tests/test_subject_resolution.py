import pytest

from app.core.config import Settings
from app.schemas.card import ImageAnalysis, ProductInput
from app.services.subject_resolver import SubjectResolver


class FakeWbClient:
    def __init__(self, subjects):
        self._subjects = subjects
        self.parent_ids = []

    async def get_subjects(self, parent_id=None, locale="ru"):
        self.parent_ids.append(parent_id)
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
async def test_resolver_uses_full_wb_subject_catalog_and_keeps_product_terms_after_size():
    subjects = [
        {"subjectID": 71, "subjectName": "Брюки"},
        {"subjectID": 1429, "subjectName": "Блузки-боди"},
        {"subjectID": 219, "subjectName": "Футболки-поло"},
    ]
    wb_client = FakeWbClient(subjects)
    resolver = SubjectResolver(Settings(app_env="test", app_secret_key="test-secret-key"), wb_client)
    source = (
        "Quần vải học sinh, size 25-30(40-50), 20x30x2, cân nặng 0.3, "
        "mã 234, màu xanh đỏ tím vàng Брюки Брюки женские Текстиль "
        "Женский С карманами На резинке Укороченные"
    )

    subject = await resolver.resolve(ProductInput(note=source), ImageAnalysis())
    normalized = SubjectResolver._normalize_text(SubjectResolver._strip_noise(source))

    assert wb_client.parent_ids == [None]
    assert subject["subjectName"] == "Брюки"
    assert "брюки" in normalized
    assert "25-30" not in normalized
    assert "20x30x2" not in normalized


def test_top_candidates_use_same_exact_token_scoring_as_resolution():
    subjects = [
        {"subjectID": 71, "subjectName": "Брюки"},
        {"subjectID": 1429, "subjectName": "Блузки-боди"},
    ]

    candidates = SubjectResolver._top_candidate_details(
        subjects,
        "Quần vải size 25-30 Брюки женские с карманами",
    )

    assert candidates[0]["subjectName"] == "Брюки"
    assert candidates[0]["score"] == 1.0
