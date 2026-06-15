from app.services.critical_attribute_validator import CriticalAttributeValidator
from app.services.keyword_stuffing_validator import KeywordStuffingValidator
from app.services.marketplace_policy_validator import MarketplacePolicyValidator
from app.services.product_copy_policy import build_seo_title
from app.services.russian_grammar_validator import RussianGrammarValidator
from app.services.seo_content_validator import SeoContentValidator
from app.services.seo_keyword_planner import SeoKeywordPlanner
from app.services.semantic_consistency_validator import SemanticConsistencyValidator


def test_jeans_title_uses_marketplace_friendly_russian_structure():
    payload = build_seo_title(
        "Джинсы",
        "женские",
        {"pants_model": "широкие", "fit": "высокая", "decor": "рваные", "color": "голубой"},
        {"primary_keyword": "джинсы женские широкие", "secondary_keywords": ["джинсы с высокой посадкой"]},
    )

    title = payload["title"].casefold()
    assert "джинсы" in title
    assert "женские" not in title
    assert "широкие" in title
    assert "посадк" in title
    assert "голуб" not in title


def test_keyword_plan_keeps_forbidden_title_attributes_out_of_primary_keyword():
    plan = SeoKeywordPlanner.build_plan(
        category="Брюки",
        subject_name="Брюки",
        brand="Бренд",
        gender="женский",
        analysis=None,
        user_input=None,
        confirmed_attributes={"color": "бежевый", "composition": "лен", "fit": "широкие", "season": "лето"},
        wb_characteristics=[],
        product_family_policy={"family": "bottoms"},
    )

    primary = plan["primary_keyword"].casefold()
    assert "брюки" in primary
    assert "широк" in primary
    assert all(term not in primary for term in ("жен", "беж", "лен", "лето", "бренд"))


def test_marketplace_policy_blocks_forbidden_title_attributes_and_description_color():
    result = MarketplacePolicyValidator.validate(
        subject_name="Брюки",
        title="Брюки женские бежевые из льна на лето",
        description="Бежевые брюки подходят на каждый день.",
        confirmed_attributes={"color": "бежевый", "composition": "лен", "season": "лето"},
        inferred_attributes={},
    )

    assert result["valid"] is False
    assert result["blocking_issues"]
    assert result["subject_rule_score"] < 100


def test_scorecard_cannot_be_excellent_when_blocking_issue_exists():
    description = "Бежевые брюки с аккуратным кроем подходят для повседневной носки. " * 12
    validator_result = SeoContentValidator.validate(
        title="Брюки широкие",
        description=description,
        seo_keyword_plan={"primary_keyword": "брюки широкие", "secondary_keywords": [], "long_tail_keywords": [], "forbidden_claims": []},
        confirmed_attributes={"color": "бежевый", "fit": "широкие"},
        inferred_attributes={},
        auto_fix=False,
    )
    scorecard = SeoContentValidator.build_scorecard(
        title="Брюки широкие",
        description=description,
        seo_keyword_plan={"primary_keyword": "брюки широкие", "secondary_keywords": []},
        validator_result=validator_result,
        confirmed_attributes={"color": "бежевый", "fit": "широкие"},
        inferred_attributes={},
        subject_name="Брюки",
    )

    assert scorecard["blocking_issues"]
    assert scorecard["status"] == "needs_review"


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
        wb_characteristics=[
            {"name": "Модель джинсов"},
            {"name": "Тип посадки"},
            {"name": "Вид застежки"},
            {"name": "Декоративные элементы"},
            {"name": "Состав"},
        ],
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


def test_semantic_conflict_lowers_score():
    validator_result = SeoContentValidator.validate(
        title="Брюки широкие лен",
        description=("Эти брюки удобны на каждый день. " * 40) + "Модель выглядит как джинсы и имеет голубой оттенок.",
        seo_keyword_plan={"primary_keyword": "брюки широкие", "secondary_keywords": [], "long_tail_keywords": [], "forbidden_claims": []},
        confirmed_attributes={"composition": "лен", "color": "бежевый", "fit": "широкие"},
        inferred_attributes={},
        auto_fix=False,
    )
    scorecard = SeoContentValidator.build_scorecard(
        title="Брюки широкие лен",
        description=("Эти брюки удобны на каждый день. " * 40) + "Модель выглядит как джинсы и имеет голубой оттенок.",
        seo_keyword_plan={"primary_keyword": "брюки широкие", "secondary_keywords": []},
        validator_result=validator_result,
        confirmed_attributes={"composition": "лен", "color": "бежевый", "fit": "широкие"},
        inferred_attributes={},
        subject_name="Брюки",
    )

    assert scorecard["semantic_consistency_score"] < 100
    assert scorecard["seo_score"] < 85
    assert scorecard["semantic_conflicts"]


def test_semantic_consistency_validator_detects_cross_subject_text():
    result = SemanticConsistencyValidator.validate(
        subject_name="Юбка",
        title="Юбка миди",
        description="Это платье на каждый день.",
        confirmed_attributes={"color": "черный"},
        inferred_attributes={},
    )

    assert result["conflicts"]
    assert result["semantic_score"] < 100


def test_semantic_consistency_allows_styling_companion_subject():
    result = SemanticConsistencyValidator.validate(
        subject_name="Юбка",
        title="Юбка миди",
        description="Юбка миди легко сочетается с платьем-накидкой и базовым верхом.",
        confirmed_attributes={},
        inferred_attributes={},
    )

    assert result["conflicts"] == []
