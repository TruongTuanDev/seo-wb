from app.services.critical_attribute_validator import CriticalAttributeValidator
from app.services.keyword_stuffing_validator import KeywordStuffingValidator
from app.services.product_copy_policy import build_seo_title
from app.services.russian_grammar_validator import RussianGrammarValidator
from app.services.seo_content_validator import SeoContentValidator


def test_jeans_title_uses_marketplace_friendly_russian_structure():
    payload = build_seo_title(
        "Джинсы",
        "женские",
        {"pants_model": "широкие", "fit": "высокая", "decor": "рваные"},
        {"primary_keyword": "джинсы женские широкие", "secondary_keywords": ["джинсы с высокой посадкой"]},
    )

    title = payload["title"].casefold()
    assert "джинсы" in title
    assert "женские" in title
    assert "широкие" in title
    assert "посадк" in title


def test_russian_grammar_validator_flags_spammy_title():
    result = RussianGrammarValidator.validate("Джинсы Женский Высокая Хлопок Голубой Лето")

    assert result["grammar_score"] < 70
    assert result["issues"]


def test_keyword_stuffing_validator_penalizes_repetition():
    result = KeywordStuffingValidator.validate("Платье платье платье женское летнее")

    assert result["keyword_stuffing_score"] < 70
    assert result["density_issues"]


def test_critical_attribute_validator_returns_missing_subject_fields():
    result = CriticalAttributeValidator.validate(
        subject_name="Джинсы",
        confirmed_attributes={"composition": "хлопок"},
        inferred_attributes={"fit": "высокая"},
    )

    assert "Вид застежки" in result["missing_critical_attributes"]
    assert result["critical_score"] < 100


def test_auto_fix_does_not_emit_ai_keyword_block_phrase():
    result = SeoContentValidator.validate(
        title="Джинсы женские широкие с высокой посадкой рваные",
        description="Короткое описание джинсов.",
        seo_keyword_plan={
            "primary_keyword": "джинсы женские широкие",
            "secondary_keywords": ["джинсы с высокой посадкой", "рваные джинсы"],
            "long_tail_keywords": [],
            "forbidden_claims": [],
        },
        confirmed_attributes={"composition": "хлопок", "fit": "высокая", "purpose": "на каждый день"},
        inferred_attributes={"pants_model": "широкие"},
        min_chars=400,
        max_chars=900,
        auto_fix=True,
    )

    fixed = result["fixed_description"].casefold()
    assert "актуальные поисковые фразы" not in fixed
    assert "в описании естественно раскрыты детали модели" not in fixed
