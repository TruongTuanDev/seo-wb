from app.schemas.card import ImageAnalysis, ProductInput
from app.services.card_generator import CardGenerator
from app.services.product_copy_policy import cleanup_description, cleanup_title
from app.services.product_intent_parser import ColorIntent, ProductIntent


def test_apply_intent_uses_russian_vendor_color_suffix():
    raw = [
        {
            "subjectID": 12,
            "variants": [
                {
                    "vendorCode": "CHANGE-ME",
                    "title": "Women's jeans straight fit",
                    "description": (
                        "Straight-fit jeans with durable denim fabric, clean construction, and a comfortable silhouette "
                        "for daily wear across school, office, and casual routines."
                    ),
                    "brand": "Test Brand",
                    "dimensions": {"length": 30, "width": 20, "height": 4, "weightBrutto": 0.4},
                    "characteristics": [],
                    "sizes": [{"techSize": "S", "wbSize": "42", "skus": []}],
                }
            ],
        }
    ]
    user_input = ProductInput(vendor_code="234")
    intent = ProductIntent(colors=[ColorIntent(value="black", code="CHERNYI")])

    CardGenerator._apply_intent_to_raw(raw, user_input, intent, charcs=[])

    assert raw[0]["variants"][0]["vendorCode"] == "234/Черный"


def test_cleanup_title_removes_duplicate_trailing_token():
    cleaned = cleanup_title(
        "Набор трусов-боксеров для мальчиков Человек-паук, 5 шт. Бокс",
        "Трусы",
        ImageAnalysis(product_name="Набор трусов-боксеров"),
        ProductInput(),
    )

    assert cleaned == "Набор трусов-боксеров для мальчиков Человек-паук, 5 шт"


def test_cleanup_title_replaces_underwear_fit_with_higher_value_hint():
    cleaned = cleanup_title(
        "Набор трусов-боксеров для мальчиков, 5 шт. Облегающий",
        "Трусы-боксеры",
        ImageAnalysis(material="хлопок", features=["принт Человек-паук"]),
        ProductInput(),
    )

    assert "Облегающий" not in cleaned
    assert "Человек-паук" in cleaned or "хлопок" in cleaned


def test_underwear_description_rejects_generic_office_copy():
    analysis = ImageAnalysis(
        product_name="Набор трусов-боксеров для мальчиков",
        material="хлопок",
        gender="мальчики",
        features=["принт Человек-паук", "мягкая резинка"],
    )
    cleaned = cleanup_description(
        (
            "Стильные трусы для офиса и строгих учебных образов, которые легко сочетаются с базовым гардеробом "
            "и подходят для деловых образов каждый день."
        ),
        title="Набор трусов-боксеров для мальчиков",
        subject={"subjectName": "Трусы-боксеры"},
        analysis=analysis,
        user_input=ProductInput(),
    )

    assert "деловых образов" not in cleaned
    assert "офиса" not in cleaned
    assert "спорта" in cleaned
    assert "карточке" not in cleaned


def test_bag_description_stays_in_accessory_context():
    text = CardGenerator._description(
        ImageAnalysis(product_name="Женская сумка", material="экокожа", features=["вместительное отделение"]),
        ProductInput(),
        {"subjectName": "Сумки"},
        "Женская сумка",
    )

    assert "эластичный пояс" not in text
    assert "посадк" not in text.casefold()
    assert "хран" in text.casefold() or "аксессуар" in text.casefold()
