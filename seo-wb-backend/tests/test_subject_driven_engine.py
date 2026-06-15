from app.services.critical_attribute_validator import CriticalAttributeValidator
from app.services.product_copy_policy import build_seo_title
from app.services.subject_rule_registry import SubjectRuleRegistry


def test_subject_registry_supports_at_least_fifteen_fashion_subjects():
    assert len(SubjectRuleRegistry.all_rules()) >= 15


def test_jeans_title_does_not_include_gender_by_default():
    payload = build_seo_title(
        "Джинсы",
        "женские",
        {"pants_model": "широкие", "fit": "высокая", "decor": "рваные"},
        {"primary_keyword": "джинсы широкие"},
    )

    assert "женские" not in payload["title"].casefold()
    assert payload["title"].casefold().startswith("джинсы")


def test_title_does_not_include_material_color_or_season():
    payload = build_seo_title(
        "Брюки",
        "женские",
        {
            "fit": "широкие",
            "material": "лен",
            "color": "бежевый",
            "season": "лето",
        },
        {"primary_keyword": "брюки широкие"},
    )

    title = payload["title"].casefold()
    assert title.startswith("брюки")
    assert all(term not in title for term in ("жен", "лен", "беж", "лето"))


def test_critical_attributes_are_subject_specific():
    jeans = CriticalAttributeValidator.validate(
        subject_name="Джинсы",
        confirmed_attributes={"composition": "хлопок"},
        inferred_attributes={},
        wb_characteristics=[{"name": "Модель джинсов"}, {"name": "Тип посадки"}, {"name": "Вид застежки"}, {"name": "Декоративные элементы"}, {"name": "Состав"}],
    )
    tshirt = CriticalAttributeValidator.validate(
        subject_name="Футболка",
        confirmed_attributes={"composition": "хлопок"},
        inferred_attributes={},
        wb_characteristics=[{"name": "Состав"}, {"name": "Вырез горловины"}, {"name": "Тип рукава"}, {"name": "Покрой"}],
    )

    assert "Модель джинсов" in jeans["missing_critical_attributes"]
    assert "Вырез горловины" in tshirt["missing_critical_attributes"]


def test_live_wb_required_characteristic_is_always_checked():
    result = CriticalAttributeValidator.validate(
        subject_name="Футболка",
        confirmed_attributes={"composition": "хлопок"},
        inferred_attributes={},
        wb_characteristics=[{"charcID": 999, "name": "Новая обязательная характеристика", "required": True}],
    )

    assert "Новая обязательная характеристика" in result["missing_critical_attributes"]
