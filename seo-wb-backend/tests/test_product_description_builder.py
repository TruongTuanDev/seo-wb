import pytest

from app.schemas.card import ImageAnalysis, ProductInput
from app.services.product_description_builder import (
    build_description_prompt_context,
    build_product_description,
    description_is_safe,
    finalize_product_description,
)


@pytest.mark.parametrize(
    ("subject", "expected_root", "forbidden_root"),
    [
        ("Брюки", "брюк", "джинс"),
        ("Джинсы", "джинс", "плать"),
        ("Шорты", "шорт", "юбк"),
        ("Юбки", "юбк", "плать"),
        ("Платья", "плать", "юбк"),
        ("Рубашки", "рубаш", "куртк"),
        ("Куртки", "куртк", "рубаш"),
    ],
)
def test_subject_fallback_descriptions_are_specific(subject, expected_root, forbidden_root):
    text = build_product_description(
        subject,
        ImageAnalysis(
            category=subject,
            material="хлопок",
            fit_type="свободный крой",
            features=["длинный рукав", "карманы"],
        ),
        ProductInput(category=subject),
    ).casefold()

    assert expected_root in text
    assert forbidden_root not in text
    assert len(text) >= 220


def test_safe_ai_description_is_preserved_to_keep_copy_flexible():
    candidate = (
        "Брюки широкого кроя создают спокойный современный силуэт и не ограничивают движения. "
        "Высокая посадка аккуратно подчеркивает линию талии, а карманы делают модель практичной на каждый день. "
        "Материал на основе льна подходит для регулярной носки. "
        "Модель легко сочетается с рубашками, футболками и жакетами. "
        "Деликатная стирка помогает сохранить форму изделия."
    )

    result = finalize_product_description(
        "Брюки",
        candidate,
        ImageAnalysis(category="Брюки", material="лен", fit_type="широкий крой"),
        ProductInput(category="Брюки"),
    )

    assert result == candidate


@pytest.mark.parametrize(
    "candidate",
    [
        (
            "Брюки бежевого цвета подходят для повседневной носки и прогулок. "
            "Свободный крой сохраняет комфорт, а высокая посадка подчеркивает талию. "
            "Материал приятен в носке и хорошо держит форму. "
            "Модель сочетается с рубашками и футболками. Бережная стирка помогает сохранить внешний вид."
        ),
        (
            "Широкие джинсы из льна подходят для повседневной носки и прогулок. "
            "Высокая посадка подчеркивает талию, а свободные штанины сохраняют комфорт. "
            "Такие джинсы легко сочетаются с футболками и рубашками. "
            "Деликатная стирка помогает сохранить форму изделия и свойства материала."
        ),
        (
            "Брюки подходят для повседневной носки и прогулок. "
            "В описании естественно раскрыты детали модели: брюки широкие, брюки высокая посадка. "
            "Материал приятен в носке, а свободный крой сохраняет комфорт. "
            "Бережная стирка помогает сохранить форму изделия."
        ),
    ],
)
def test_unsafe_ai_description_is_replaced(candidate):
    result = finalize_product_description(
        "Брюки",
        candidate,
        ImageAnalysis(category="Брюки", material="лен", color="бежевый", fit_type="широкий крой"),
        ProductInput(category="Брюки"),
    ).casefold()

    assert result != candidate.casefold()
    assert "бежев" not in result
    assert "джинс" not in result
    assert "в описании естественно" not in result


def test_styling_companion_is_not_treated_as_subject_conflict():
    candidate = (
        "Рубашка свободного кроя формирует аккуратный силуэт и подходит для повседневной носки. "
        "Длинный рукав и классический воротник делают модель универсальной. "
        "Материал на основе хлопка приятен в течение дня. "
        "Рубашка легко сочетается с брюками, джинсами, юбками или шортами. "
        "Щадящая стирка помогает сохранить внешний вид изделия."
    )

    assert description_is_safe(
        "Рубашки",
        candidate,
        ImageAnalysis(category="Рубашки", material="хлопок"),
        ProductInput(category="Рубашки"),
    )


def test_description_prompt_context_is_subject_driven():
    trousers = build_description_prompt_context("Брюки")
    jacket = build_description_prompt_context("Куртки")

    assert trousers["subject_code"] == "trousers"
    assert jacket["subject_code"] == "jacket"
    assert trousers["focus"] != jacket["focus"]


def test_description_rejects_detected_color_not_in_basic_palette():
    candidate = (
        "Куртка графитового оттенка подходит для города и прогулок. "
        "Прямой крой сохраняет свободу движений, а капюшон помогает собрать практичный образ. "
        "Материал рассчитан на регулярную носку. "
        "Модель сочетается с базовыми вещами гардероба. "
        "При уходе следует учитывать рекомендации на ярлыке."
    )

    assert not description_is_safe(
        "Куртки",
        candidate,
        ImageAnalysis(category="Куртки", color="графитовый"),
        ProductInput(category="Куртки"),
    )


def test_fallback_drops_cross_subject_feature_from_analysis():
    text = build_product_description(
        "Брюки",
        ImageAnalysis(
            category="Брюки",
            material="лен",
            features=["джинсовая фактура", "боковые карманы"],
        ),
        ProductInput(category="Брюки"),
    ).casefold()

    assert "джинс" not in text
    assert "карман" in text


def test_color_filter_does_not_confuse_underwear_or_synthetic_material_with_colors():
    candidate = (
        "Трусы подходят как комфортное белье для регулярной носки. "
        "Мягкая посадка не ограничивает движения, а аккуратные швы помогают сохранить удобство в течение дня. "
        "Синтетические волокна в составе не заявляются без данных ярлыка. "
        "Модель рассчитана на повседневное использование. "
        "Деликатная стирка помогает сохранить форму изделия."
    )

    assert description_is_safe(
        "Трусы",
        candidate,
        ImageAnalysis(category="Трусы"),
        ProductInput(category="Трусы"),
    )
