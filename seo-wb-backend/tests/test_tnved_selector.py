from app.schemas.card import ImageAnalysis, ProductInput
from app.services.tnved_selector import FashionTnvedSelector


def test_selector_prefers_womens_woven_trousers_for_female_pants():
    items = [
        {"tnved": "6203421100", "name": "Брюки мужские из хлопчатобумажной ткани, не трикотажные"},
        {"tnved": "6204623100", "name": "Брюки женские из хлопчатобумажной ткани, не трикотажные"},
    ]
    hint = FashionTnvedSelector.build_hint(
        subject_id=11,
        subject_name="Брюки",
        user_input=ProductInput(category="брюки", gender="женский"),
        analysis=ImageAnalysis(category="брюки", gender="женский", material="хлопок"),
    )

    selected, scored = FashionTnvedSelector.select_best(items, hint)

    assert selected is not None
    assert selected["tnved"] == "6204623100"
    assert scored[0]["score"] > scored[1]["score"]


def test_selector_prefers_knit_prefix_when_material_looks_knit():
    items = [
        {"tnved": "6204623900", "name": "Брюки женские из хлопчатобумажной ткани, не трикотажные"},
        {"tnved": "6104620000", "name": "Брюки женские трикотажные из хлопчатобумажной пряжи"},
    ]
    hint = FashionTnvedSelector.build_hint(
        subject_id=11,
        subject_name="Брюки",
        analysis=ImageAnalysis(category="брюки", gender="женский", material="трикотажный хлопок"),
    )

    selected, _ = FashionTnvedSelector.select_best(items, hint)

    assert selected is not None
    assert selected["tnved"] == "6104620000"


def test_selector_prefers_womens_synthetic_blouse_code():
    items = [
        {"tnved": "6206300000", "name": "Блузки женские из хлопчатобумажных тканей, не трикотажные"},
        {"tnved": "6206400000", "name": "Блузки женские из химических нитей, не трикотажные"},
    ]
    hint = FashionTnvedSelector.build_hint(
        subject_id=1429,
        subject_name="Блузки",
        analysis=ImageAnalysis(category="блузки", gender="женский", material="полиэстер"),
    )

    selected, _ = FashionTnvedSelector.select_best(items, hint)

    assert selected is not None
    assert selected["tnved"] == "6206400000"


def test_selector_rejects_womens_trouser_code_for_male_pants():
    items = [
        {"tnved": "6204623100", "name": "Брюки женские из хлопчатобумажной ткани, не трикотажные"},
        {"tnved": "6203421100", "name": "Брюки мужские из хлопчатобумажной ткани, не трикотажные"},
    ]
    hint = FashionTnvedSelector.build_hint(
        subject_id=11,
        subject_name="Брюки",
        analysis=ImageAnalysis(category="брюки", gender="мужской", material="хлопок"),
    )

    selected, scored = FashionTnvedSelector.select_best(items, hint)

    assert selected is not None
    assert selected["tnved"] == "6203421100"
    assert "tnved_prefix_match=6203421100" in scored[0]["scoreReasons"]
    assert "audience_conflict" in scored[1]["scoreReasons"]


def test_selector_prefers_skirt_specific_prefix_over_general_womens_group():
    items = [
        {"tnved": "6204623100", "name": "Брюки женские из хлопчатобумажной ткани, не трикотажные"},
        {"tnved": "6204520000", "name": "Юбки женские из хлопчатобумажной ткани, не трикотажные"},
    ]
    hint = FashionTnvedSelector.build_hint(
        subject_id=12,
        subject_name="Юбки",
        analysis=ImageAnalysis(category="юбка", gender="женский", material="хлопок"),
    )

    selected, scored = FashionTnvedSelector.select_best(items, hint)

    assert selected is not None
    assert selected["tnved"] == "6204520000"
    assert scored[0]["score"] > scored[1]["score"]
