from app.schemas.card import ProductInput
from app.services.card_generator import CardGenerator
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
