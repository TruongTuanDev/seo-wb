from app.schemas.card import ProductInput
from app.services.card_generator import CardGenerator
from app.services.product_intent_parser import ColorIntent, ProductIntent


def test_color_variants_use_russian_color_in_vendor_code():
    raw = [
        {
            "subjectID": 11,
            "variants": [
                {
                    "vendorCode": "234",
                    "title": "Брюки прямые с высокой посадкой",
                    "description": "Практичные брюки с удобной посадкой для повседневных образов и комфортной носки каждый день.",
                    "brand": "FORMELA",
                    "dimensions": {"length": 30, "width": 20, "height": 3, "weightBrutto": 0.5},
                    "characteristics": [{"id": 14177449, "value": ["черный"]}],
                    "sizes": [{"techSize": "25", "wbSize": "40", "skus": []}],
                }
            ],
        }
    ]
    intent = ProductIntent(colors=[ColorIntent(value="черный", code="CHERNYI")], vendor_code="234")

    CardGenerator._apply_intent_to_raw(
        raw,
        ProductInput(vendor_code="234"),
        intent,
        [{"charcID": 14177449, "name": "Цвет"}],
    )

    assert raw[0]["variants"][0]["vendorCode"] == "234/черный"
