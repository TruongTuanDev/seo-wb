from app.schemas.card import ImageAnalysis, ProductInput
from app.services.product_copy_policy import resolve_product_family, render_description


def test_bottoms_description_for_trousers_does_not_leak_jeans_or_blue():
    policy = resolve_product_family(
        {"subjectName": "Брюки"},
        ImageAnalysis(category="Брюки", product_name="Брюки льняные", material="лен", color="бежевый"),
        ProductInput(category="Брюки"),
    )

    text = render_description(
        policy,
        title="Брюки женские широкие с высокой посадкой бежевые",
        analysis=ImageAnalysis(category="Брюки", product_name="Брюки льняные", material="лен", color="бежевый"),
        user_input=ProductInput(category="Брюки"),
    ).casefold()

    assert "джинсы" not in text
    assert "голубой оттенок" not in text
    assert "бежев" not in text
    assert "цвет" not in text


def test_skirt_description_does_not_mention_dress():
    policy = resolve_product_family(
        {"subjectName": "Юбка"},
        ImageAnalysis(category="Юбка", product_name="Юбка миди", material="хлопок", color="черный"),
        ProductInput(category="Юбка"),
    )

    text = render_description(
        policy,
        title="Юбка миди черная",
        analysis=ImageAnalysis(category="Юбка", product_name="Юбка миди", material="хлопок", color="черный"),
        user_input=ProductInput(category="Юбка"),
    ).casefold()

    assert "платье" not in text
    assert "юбка" in text
    assert "черн" not in text


def test_unknown_category_falls_back_to_family_rule_and_generation_still_works():
    policy = resolve_product_family(
        {"subjectName": "Неизвестный товар"},
        ImageAnalysis(category="Неизвестный товар", product_name="Неизвестный товар", material="хлопок"),
        ProductInput(category="Неизвестный товар"),
    )

    text = render_description(
        policy,
        title="Неизвестный товар базовая модель",
        analysis=ImageAnalysis(category="Неизвестный товар", product_name="Неизвестный товар", material="хлопок"),
        user_input=ProductInput(category="Неизвестный товар"),
    )

    assert isinstance(text, str)
    assert len(text) > 100
