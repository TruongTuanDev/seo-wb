from app.schemas.card import ImageAnalysis, ProductInput
from app.services.card_generator import CardGenerator
from app.services.product_intent_parser import ProductIntent
from app.services.product_title_builder import build_product_title, select_best_ai_title


def test_title_converts_raw_rise_to_natural_russian_phrase():
    title = build_product_title(
        "Брюки",
        ImageAnalysis(product_name="Брюки Высокая", fit_type="Высокая"),
        ProductInput(),
        "Брюки Высокая с высокой посадкой",
    )

    assert title in {"Брюки с высокой посадкой", "Брюки с завышенной талией"}


def test_bottoms_title_uses_silhouette_rise_and_detail_without_color_or_gender():
    title = build_product_title(
        "Джинсы",
        ImageAnalysis(
            product_name="Джинсы женские голубые",
            color="голубые",
            gender="женские",
            fit_type="широкие",
            features=["высокая посадка", "рваные детали"],
        ),
        ProductInput(),
    )

    assert "жен" not in title.casefold()
    assert "голуб" not in title.casefold()
    assert "джинсы" in title.casefold()
    assert "широк" in title.casefold()
    assert "высок" in title.casefold()
    assert "рван" in title.casefold()


def test_title_does_not_repeat_equivalent_rise_phrases():
    title = build_product_title(
        "Брюки",
        ImageAnalysis(fit_type="Высокая", features=["с высокой посадкой"]),
        ProductInput(),
    )

    assert title.count("высокой посадкой") == 1


def test_titles_vary_between_products_but_stay_stable_for_same_product():
    analysis = ImageAnalysis(
        product_name="Брюки",
        fit_type="широкие",
        features=["высокая посадка", "рваные детали"],
    )
    first_product = ProductInput(vendor_code="SKU-100")
    second_product = ProductInput(vendor_code="SKU-101")

    first_title = build_product_title("Брюки", analysis, first_product)
    repeated_title = build_product_title("Брюки", analysis, first_product)
    second_title = build_product_title("Брюки", analysis, second_product)

    assert first_title == repeated_title
    assert first_title != second_title


def test_flexible_title_variants_remain_natural_and_rule_safe():
    analysis = ImageAnalysis(
        product_name="Брюки женские красные",
        color="красные",
        gender="женские",
        fit_type="широкие",
        features=["высокая посадка"],
    )
    titles = {
        build_product_title("Брюки", analysis, ProductInput(vendor_code=f"SKU-{index}"))
        for index in range(20)
    }

    assert len(titles) >= 3
    assert all(title.startswith("Брюки") for title in titles)
    assert all("жен" not in title.casefold() and "красн" not in title.casefold() for title in titles)


def test_ai_title_selector_supports_multiple_fashion_subjects():
    cases = [
        (
            "Рубашки",
            ImageAnalysis(product_name="Рубашки", features=["длинный рукав", "свободный крой"]),
            ["Рубашки женские белые", "Рубашки свободного кроя с длинным рукавом"],
            "Рубашки свободного кроя с длинным рукавом",
        ),
        (
            "Платья",
            ImageAnalysis(product_name="Платья", features=["длина миди", "приталенный силуэт"]),
            ["Платья красные летние", "Платья миди приталенного силуэта"],
            "Платья миди приталенного силуэта",
        ),
        (
            "Куртки",
            ImageAnalysis(product_name="Куртки", features=["капюшон", "утепленная"]),
            ["Куртки зимние черные", "Куртки утепленные с капюшоном"],
            "Куртки утепленные с капюшоном",
        ),
    ]

    for subject, analysis, candidates, expected in cases:
        assert select_best_ai_title(subject, candidates, analysis, ProductInput()) == expected


def test_ai_title_selector_rejects_forbidden_fields_and_raw_keyword_chains():
    analysis = ImageAnalysis(
        product_name="Брюки",
        color="бежевый",
        gender="женские",
        material="лен",
        season="лето",
        features=["широкий крой", "высокая посадка"],
    )
    selected = select_best_ai_title(
        "Брюки",
        [
            "Брюки женские бежевые лен лето",
            "Брюки Высокая широкие",
            "Брюки широкого кроя с высокой посадкой",
        ],
        analysis,
        ProductInput(brand="Test Brand"),
        brand="Test Brand",
    )

    assert selected == "Брюки широкого кроя с высокой посадкой"


def test_short_material_name_does_not_reject_unrelated_word():
    selected = select_best_ai_title(
        "Куртки",
        ["Куртки утепленные с капюшоном"],
        ImageAnalysis(product_name="Куртки", material="лен", features=["утепленная", "капюшон"]),
        ProductInput(),
    )

    assert selected == "Куртки утепленные с капюшоном"


def test_ai_title_selector_rejects_inflected_material_and_color():
    selected = select_best_ai_title(
        "Рубашки",
        [
            "Рубашки хлопковые свободного кроя",
            "Рубашки белые свободного кроя",
            "Рубашки свободного кроя с длинным рукавом",
        ],
        ImageAnalysis(
            product_name="Рубашки",
            material="хлопок",
            color="белый",
            features=["свободный крой", "длинный рукав"],
        ),
        ProductInput(),
    )

    assert selected == "Рубашки свободного кроя с длинным рукавом"


def test_card_generator_consumes_candidates_without_leaking_them_to_wb_payload():
    raw = [
        {
            "subjectID": 123,
            "variants": [
                {
                    "vendorCode": "SKU-1",
                    "title": "Платья женские красные",
                    "titleCandidates": [
                        "Платья женские красные",
                        "Платья миди приталенного силуэта",
                    ],
                    "description": "Описание товара " * 10,
                    "brand": "Нет бренда",
                    "dimensions": {"length": 30, "width": 20, "height": 5, "weightBrutto": 0.5},
                    "characteristics": [{"id": 1, "value": ["миди"]}],
                    "sizes": [{"techSize": "M", "wbSize": "44", "skus": []}],
                }
            ],
        }
    ]
    generator = object.__new__(CardGenerator)
    result = generator._enrich_openai_output(
        raw,
        ProductInput(vendor_code="SKU-1"),
        ImageAnalysis(
            product_name="Платья",
            color="красный",
            gender="женские",
            features=["длина миди", "приталенный силуэт"],
        ),
        {"subjectID": 123, "subjectName": "Платья"},
        ProductIntent(vendor_code="SKU-1"),
        [],
    )
    variant = result[0]["variants"][0]

    assert variant["title"] == "Платья миди приталенного силуэта"
    assert "titleCandidates" not in variant


def test_specialized_fallbacks_cover_all_priority_subjects():
    cases = [
        (
            "Брюки",
            ImageAnalysis(fit_type="широкие", features=["высокая посадка"]),
            (("широк",), ("высок", "завыш")),
        ),
        (
            "Джинсы",
            ImageAnalysis(fit_type="прямые", features=["средняя посадка", "рваные детали"]),
            (("прям",), ("средн", "стандартн"), ("рван",)),
        ),
        (
            "Шорты",
            ImageAnalysis(fit_type="свободные", features=["высокая посадка", "бермуды"]),
            (("свобод",), ("высок", "завыш"), ("бермуд",)),
        ),
        (
            "Юбки",
            ImageAnalysis(features=["длина миди", "А-силуэт", "разрез"]),
            (("миди",), ("а-силуэт",), ("разрез",)),
        ),
        (
            "Платья",
            ImageAnalysis(features=["длина макси", "приталенный силуэт", "длинный рукав"]),
            (("макси",), ("притал",), ("рукав",)),
        ),
        (
            "Рубашки",
            ImageAnalysis(fit_type="свободный", features=["длинный рукав", "воротник"]),
            (("свобод",), ("рукав",), ("воротник",)),
        ),
        (
            "Куртки",
            ImageAnalysis(features=["утепленная", "капюшон", "молния"]),
            (("утепл",), ("капюш",)),
        ),
    ]

    for subject, analysis, expected_groups in cases:
        title = build_product_title(subject, analysis, ProductInput(vendor_code=f"SKU-{subject}"))
        normalized = title.casefold()
        assert title.startswith(subject)
        assert len(title) <= 60
        assert all(any(root in normalized for root in group) for group in expected_groups)


def test_specialized_fallbacks_do_not_use_generic_copy():
    for subject in ("Шорты", "Юбки", "Платья", "Рубашки", "Куртки"):
        title = build_product_title(subject, ImageAnalysis(), ProductInput())
        assert title == f"{subject} базового кроя"
        assert "повседневного использования" not in title


def test_ai_title_rejects_unsupported_subject_specific_claim():
    selected = select_best_ai_title(
        "Куртки",
        [
            "Куртки утепленные с капюшоном",
            "Куртки прямого кроя",
        ],
        ImageAnalysis(product_name="Куртки", features=["прямой крой"]),
        ProductInput(),
    )

    assert selected == "Куртки прямого кроя"
