import re
from dataclasses import dataclass, field
from typing import Any

from app.schemas.card import ImageAnalysis, ProductInput
from app.services.subject_rule_registry import SubjectRuleRegistry
from app.services.title_template_registry import TitleTemplateRegistry


@dataclass(frozen=True)
class ProductFamilyPolicy:
    family: str
    focus_points: list[str]
    use_cases: list[str]
    forbidden_phrases: list[str] = field(default_factory=list)
    replacement_description: str = ""
    seo_characteristics: dict[str, list[str]] = field(default_factory=dict)


FAMILY_POLICIES: dict[str, ProductFamilyPolicy] = {
    "underwear": ProductFamilyPolicy(
        family="underwear",
        focus_points=["мягкий материал", "дышащая ткань", "комфортная посадка", "эластичный пояс"],
        use_cases=["на каждый день", "в школу", "для спорта и активных игр"],
        forbidden_phrases=["деловые образы", "офис", "работы", "строгие учебные", "повседневные аутфиты"],
        replacement_description="комфортное белье для ежедневной носки и активного дня",
        seo_characteristics={
            "purpose": ["повседневная", "в школу", "для спорта"],
            "underwear_features": ["мягкая резинка", "дышащий материал", "анатомический крой"],
        },
    ),
    "tops": ProductFamilyPolicy(
        family="tops",
        focus_points=["удобный крой", "приятная ткань", "аккуратная посадка", "простое сочетание с базовым гардеробом"],
        use_cases=["на каждый день", "в школу", "для прогулок"],
        forbidden_phrases=["защищает от дождя", "согревает в сильный мороз"],
        replacement_description="удобная повседневная модель для комфортного образа каждый день",
        seo_characteristics={"purpose": ["повседневная", "в школу", "для прогулок"]},
    ),
    "bottoms": ProductFamilyPolicy(
        family="bottoms",
        focus_points=["комфорт в движении", "аккуратный силуэт", "удобная посадка", "практичность"],
        use_cases=["на каждый день", "в школу", "для прогулок"],
        forbidden_phrases=["деловые образы", "белье на каждый день"],
        replacement_description="практичная модель для ежедневной носки и активного дня",
        seo_characteristics={"purpose": ["повседневная", "в школу", "для прогулок"]},
    ),
    "dresses_skirts": ProductFamilyPolicy(
        family="dresses_skirts",
        focus_points=["аккуратный силуэт", "комфортная посадка", "приятный материал", "женственный образ"],
        use_cases=["на каждый день", "для прогулок", "на учебу"],
        forbidden_phrases=["для офиса и работы", "анатомический крой белья"],
        replacement_description="комфортная модель для аккуратного образа и повседневной носки",
        seo_characteristics={"purpose": ["повседневная", "для прогулок", "на учебу"]},
    ),
    "outerwear": ProductFamilyPolicy(
        family="outerwear",
        focus_points=["защита от прохлады", "удобный верхний слой", "комфортная посадка", "практичность"],
        use_cases=["на каждый день", "для прогулок", "в поездки"],
        forbidden_phrases=["легкое белье", "мягкая резинка"],
        replacement_description="практичная верхняя одежда для прохладной погоды и ежедневного использования",
        seo_characteristics={"purpose": ["повседневная", "для прогулок", "в поездки"]},
    ),
    "sleepwear": ProductFamilyPolicy(
        family="sleepwear",
        focus_points=["мягкость", "комфорт во время сна", "приятная к телу ткань", "свобода движений"],
        use_cases=["для сна", "для дома", "для отдыха"],
        forbidden_phrases=["офис", "деловые образы", "для спорта"],
        replacement_description="уютная домашняя модель для сна и отдыха",
        seo_characteristics={"purpose": ["для сна", "домашняя", "для отдыха"]},
    ),
    "bags_accessories": ProductFamilyPolicy(
        family="bags_accessories",
        focus_points=["практичность", "удобство хранения", "аккуратный внешний вид", "повседневное использование"],
        use_cases=["на каждый день", "в школу", "в поездки"],
        forbidden_phrases=["свобода движений в течение всего дня", "посадка по фигуре", "эластичный пояс"],
        replacement_description="практичный аксессуар для ежедневных задач и удобного хранения вещей",
        seo_characteristics={"purpose": ["повседневная", "в школу", "в поездки"]},
    ),
    "generic_apparel": ProductFamilyPolicy(
        family="generic_apparel",
        focus_points=["комфорт", "практичность", "аккуратный внешний вид", "удобство каждый день"],
        use_cases=["на каждый день", "для прогулок", "на учебу"],
        forbidden_phrases=[],
        replacement_description="универсальная модель для повседневной носки",
        seo_characteristics={"purpose": ["повседневная", "для прогулок", "на учебу"]},
    ),
}


def resolve_product_family(
    subject: dict[str, Any] | None,
    analysis: ImageAnalysis | None,
    user_input: ProductInput | None,
) -> ProductFamilyPolicy:
    source = " ".join(
        str(part or "")
        for part in [
            subject.get("subjectName") if subject else "",
            analysis.category if analysis else "",
            analysis.product_name if analysis else "",
            user_input.category if user_input else "",
            user_input.note if user_input else "",
        ]
    ).casefold()

    if any(token in source for token in ["трус", "боксер", "бель", "brief", "boxer", "panties"]):
        return FAMILY_POLICIES["underwear"]
    if any(token in source for token in ["пижам", "сорочка", "халат", "sleep", "homewear"]):
        return FAMILY_POLICIES["sleepwear"]
    if any(token in source for token in ["куртк", "пальто", "пухов", "ветров", "жилет", "coat", "jacket"]):
        return FAMILY_POLICIES["outerwear"]
    if any(token in source for token in ["сумк", "рюкзак", "кошелек", "ремень", "bag", "backpack", "belt"]):
        return FAMILY_POLICIES["bags_accessories"]
    if any(token in source for token in ["плать", "юбк", "dress", "skirt", "сарафан"]):
        return FAMILY_POLICIES["dresses_skirts"]
    if any(token in source for token in ["брюк", "джинс", "шорт", "леггинс", "pants", "jeans", "shorts"]):
        return FAMILY_POLICIES["bottoms"]
    if any(token in source for token in ["футбол", "рубаш", "блуз", "майк", "свитш", "худи", "shirt", "top"]):
        return FAMILY_POLICIES["tops"]
    return FAMILY_POLICIES["generic_apparel"]


def build_copy_policy_context(
    subject: dict[str, Any] | None,
    analysis: ImageAnalysis | None,
    user_input: ProductInput | None,
) -> dict[str, Any]:
    policy = resolve_product_family(subject, analysis, user_input)
    subject_rule = SubjectRuleRegistry.resolve_from_context(
        subject.get("subjectName") if subject else "",
        analysis.category if analysis else "",
        analysis.product_name if analysis else "",
        user_input.category if user_input else "",
    )
    return {
        "family": policy.family,
        "subject_code": subject_rule.subject_code if subject_rule else None,
        "focus_points": policy.focus_points,
        "use_cases": policy.use_cases,
        "forbidden_phrases": policy.forbidden_phrases,
        "replacement_description": policy.replacement_description,
    }


def build_seo_title(
    category: str | None,
    gender: str | None,
    attributes: dict[str, Any] | None,
    seo_keyword_plan: dict[str, Any] | None,
    brand: str | None = None,
    include_gender_in_title: bool = False,
) -> dict[str, Any]:
    attributes = attributes or {}
    seo_keyword_plan = seo_keyword_plan or {}
    subject = _normalize_spaces(category or "")
    primary_keyword = _normalize_spaces(str(seo_keyword_plan.get("primary_keyword") or ""))
    material = _pick_attribute(attributes, "material", "composition", "Состав")
    color = _pick_attribute(attributes, "color", "Цвет")
    fit = _pick_attribute(attributes, "fit", "Тип посадки", "Покрой")
    season = _pick_attribute(attributes, "season", "Сезон")
    quantity = _pick_attribute(attributes, "quantity_in_set", "quantity")
    key_feature = _pick_attribute(attributes, "key_feature", "feature")

    registry_attributes = {
        "main_attribute": _pick_attribute(attributes, "pants_model", "model") or fit or key_feature,
        "fit": fit,
        "secondary_attribute": key_feature,
        "material": None,
        "color": None,
        "rise": fit,
        "decor": _pick_attribute(attributes, "decor", "pattern"),
        "length": _pick_attribute(attributes, "length", "Длина изделия"),
        "occasion": _pick_attribute(attributes, "purpose", "occasion"),
        "construction": _pick_attribute(attributes, "construction", "feature"),
        "support": _pick_attribute(attributes, "support", "model"),
        "model": _pick_attribute(attributes, "pants_model", "model"),
        "quantity_in_set": quantity,
        "hood_feature": key_feature or fit,
        "detail": _pick_attribute(attributes, "detail", "decor", "pattern", "feature"),
        "style": _pick_attribute(attributes, "style", "fit", "model"),
        "silhouette": _pick_attribute(attributes, "silhouette", "fit", "model"),
        "purpose": _pick_attribute(attributes, "purpose", "occasion"),
        "bra_type": _pick_attribute(attributes, "bra_type", "type"),
        "wire_state": _pick_attribute(attributes, "wire_state", "support"),
        "effect": _pick_attribute(attributes, "effect", "feature"),
        "panties_type": _pick_attribute(attributes, "panties_type", "type", "model"),
    }
    title = TitleTemplateRegistry.build_title(
        subject_name=subject or "Товар",
        attributes=registry_attributes,
        include_gender_in_title=include_gender_in_title,
        gender=gender,
    )
    if not title and primary_keyword:
        title = primary_keyword
    used_primary_keyword = bool(primary_keyword and _normalize_spaces(primary_keyword).casefold() in title.casefold())
    used_secondary_keywords = []
    for keyword in seo_keyword_plan.get("secondary_keywords", []) or []:
        keyword_text = _normalize_spaces(str(keyword))
        if keyword_text and keyword_text.casefold() in title.casefold():
            used_secondary_keywords.append(keyword_text)
    return {
        "title": title,
        "title_tokens": title.split(),
        "used_primary_keyword": used_primary_keyword,
        "used_secondary_keywords": used_secondary_keywords,
        "brand_used": brand.strip() if brand and brand.strip() else None,
    }


def cleanup_title(title: str, default_category: str, analysis: ImageAnalysis | None, user_input: ProductInput | None) -> str:
    family = resolve_product_family({"subjectName": default_category}, analysis, user_input).family
    source = _normalize_spaces(title)
    if not source:
        source = analysis.product_name if analysis else ""
    if not source:
        source = user_input.category if user_input else ""
    if not source:
        source = default_category

    words = source.split()
    cleaned: list[str] = []
    seen: set[str] = set()
    for word in words:
        raw = word.strip()
        if not raw:
            continue
        norm = _token_key(raw)
        if not norm:
            continue
        if cleaned and norm in seen and not any(char.isdigit() for char in norm):
            continue
        cleaned.append(raw)
        seen.add(norm)

    if len(cleaned) > 1:
        tail_key = _token_key(cleaned[-1])
        body_keys = {_token_key(item) for item in cleaned[:-1]}
        if tail_key in body_keys or any(tail_key and tail_key in key for key in body_keys):
            cleaned.pop()

    result = _normalize_spaces(" ".join(cleaned)).strip(",.-/ ")
    result = _family_title_cleanup(result, family=family, analysis=analysis, user_input=user_input)
    if len(result) < 10:
        result = f"{default_category} базовая модель"
    return result[:60].strip()


def cleanup_description(
    description: str,
    *,
    title: str,
    subject: dict[str, Any] | None,
    analysis: ImageAnalysis | None,
    user_input: ProductInput | None,
) -> str:
    policy = resolve_product_family(subject, analysis, user_input)
    normalized = _normalize_spaces(description)
    if not normalized:
        return _sanitize_description(render_description(policy, title=title, analysis=analysis, user_input=user_input), analysis, user_input)
    if any(phrase in normalized.casefold() for phrase in policy.forbidden_phrases):
        return _sanitize_description(render_description(policy, title=title, analysis=analysis, user_input=user_input), analysis, user_input)
    if _contains_forbidden_description_content(normalized, analysis=analysis, user_input=user_input):
        return _sanitize_description(render_description(policy, title=title, analysis=analysis, user_input=user_input), analysis, user_input)
    if len(normalized) < 220:
        return _sanitize_description(render_description(policy, title=title, analysis=analysis, user_input=user_input), analysis, user_input)
    return _sanitize_description(normalized[:1000], analysis, user_input)


def render_description(
    policy: ProductFamilyPolicy,
    *,
    title: str,
    analysis: ImageAnalysis | None,
    user_input: ProductInput | None,
) -> str:
    subject_rule = SubjectRuleRegistry.resolve_from_context(
        analysis.category if analysis else "",
        analysis.product_name if analysis else "",
        user_input.category if user_input else "",
        title,
    )
    if subject_rule is not None:
        return _render_subject_description(subject_rule, policy=policy, title=title, analysis=analysis, user_input=user_input)

    product_name = (analysis.product_name if analysis and analysis.product_name else title).strip().lower()
    material = (analysis.material if analysis and analysis.material else "качественного материала").strip().lower()
    color = str(analysis.color if analysis and analysis.color else user_input.color if user_input and user_input.color else "").strip().lower()
    features = [str(item).strip().lower() for item in ((analysis.features if analysis else []) or []) if str(item).strip()]
    audience = _audience_phrase(analysis, user_input)
    use_cases = ", ".join(policy.use_cases)
    focus_text = ", ".join(policy.focus_points[:3]).lower()
    feature_text = ", ".join(features[:3])

    if policy.family == "underwear":
        opening = f"Яркий {product_name} обязательно понравится {audience}."
        benefits = (
            f"Модель из {material} создана для ежедневного комфорта: {focus_text} помогают ребенку чувствовать себя удобно "
            "в школе, на прогулке и во время активных игр."
        )
        if feature_text:
            benefits += f" Детали и принты, включая {feature_text}, делают комплект более заметным и приятным для ребенка."
        use_case_sentence = (
            f"Комплект подходит для сценариев {use_cases}, а мягкая посадка и дышащий материал помогают сохранить комфорт "
            "после частой носки и стирки."
        )
        closing = "Практичный вариант на каждый день, когда важны мягкость, удобство и натуральная ткань для детского белья."
        text = _normalize_spaces(" ".join([opening, benefits, use_case_sentence, closing]))
        while len(text) < 320:
            text += " " + "Набор удобно брать на каждый день, чтобы у ребенка всегда было комфортное белье для школы, дома и прогулок."
            text = _normalize_spaces(text)
        return text[:1000]

    if policy.family == "bottoms":
        source = " ".join(
            str(part or "")
            for part in [
                title,
                analysis.product_name if analysis else "",
                analysis.category if analysis else "",
                user_input.category if user_input else "",
            ]
        ).casefold()
        is_jeans = any(token in source for token in ["джинс", "jeans", "деним"])
        product_label = "джинсы" if is_jeans else "брюки"
        fit_value = (analysis.fit_type if analysis and analysis.fit_type else "").strip().lower()
        fit_phrase = "широкие " if "шир" in fit_value else "свободные " if fit_value else ""
        opening = f"{fit_phrase}{product_label} из {material} сочетают комфорт, актуальный силуэт и удобство на каждый день."
        benefits = (
            "Модель помогает создать современный расслабленный образ, а высокая посадка подчеркивает талию "
            "и делает посадку более удобной в движении."
        )
        if feature_text:
            benefits += f" Детали модели, включая {feature_text}, добавляют образу выразительность без перегруженного декора."
        use_case_sentence = (
            f"Такие {product_label} подходят для сценариев {use_cases} и хорошо работают как базовая модель на сезонную и повседневную носку."
        )
        closing = "Уход: бережная стирка при 30 градусах, не отбеливать, гладить при низкой температуре."
        text = _normalize_spaces(" ".join([opening, benefits, use_case_sentence, closing]))
        while len(text) < 420:
            text += " " + "Свободный крой сохраняет комфорт в течение дня, а плотный материал помогает модели держать аккуратную форму после носки."
            text = _normalize_spaces(text)
        return text[:1000]

    opening = f"{product_name[:1].upper() + product_name[1:]} из {material} подходит {audience}."
    benefits = f"Модель делает акцент на таких качествах, как {focus_text}, поэтому остается удобной в течение дня."
    if feature_text:
        benefits += f" В конструкции особенно заметны {feature_text}, что помогает точнее передать преимущества товара в карточке."

    use_case_sentence = f"Изделие рассчитано на сценарии {use_cases} и хорошо отвечает ожиданиям покупателей в своей категории."
    closing = f"{policy.replacement_description[:1].upper() + policy.replacement_description[1:]}, без лишних обещаний и нерелевантных модных формулировок."
    text = _normalize_spaces(" ".join([opening, benefits, use_case_sentence, closing]))
    while len(text) < 320:
        text += " " + _support_sentence(policy, analysis)
        text = _normalize_spaces(text)
    return text[:1000]


def suggest_characteristics(
    subject: dict[str, Any] | None,
    analysis: ImageAnalysis | None,
    user_input: ProductInput | None,
) -> dict[str, list[str] | str]:
    policy = resolve_product_family(subject, analysis, user_input)
    source = " ".join(
        str(part or "")
        for part in [
            subject.get("subjectName") if subject else "",
            analysis.category if analysis else "",
            analysis.product_name if analysis else "",
            user_input.category if user_input else "",
            user_input.note if user_input else "",
            " ".join(analysis.features if analysis and analysis.features else []),
        ]
    ).casefold()
    suggestions: dict[str, list[str] | str] = {}
    for alias, values in policy.seo_characteristics.items():
        suggestions[alias] = values

    if any(token in source for token in ["джинс", "jeans"]):
        if "wide" in source or "шир" in source:
            suggestions.setdefault("pants_model", "широкие")
        elif "прям" in source:
            suggestions.setdefault("pants_model", "прямые")
        suggestions.setdefault("closure", "молния")
        suggestions.setdefault("pattern", "без рисунка")
        if any(token in source for token in ["рван", "дыр", "distress"]):
            suggestions.setdefault("decor", "рваные элементы")

    age_hint = _extract_age_hint(analysis, user_input)
    if age_hint:
        suggestions["age_limits"] = age_hint
    subject_rule = SubjectRuleRegistry.resolve_from_context(
        subject.get("subjectName") if subject else "",
        analysis.category if analysis else "",
        analysis.product_name if analysis else "",
        user_input.category if user_input else "",
    )
    if subject_rule:
        defaults = subject_rule.attribute_inference_rules
        if defaults.get("closure_default"):
            suggestions.setdefault("closure", str(defaults["closure_default"]))
        if defaults.get("pattern_default"):
            suggestions.setdefault("pattern", str(defaults["pattern_default"]))
    return suggestions


def _render_subject_description(
    rule: Any,
    *,
    policy: ProductFamilyPolicy,
    title: str,
    analysis: ImageAnalysis | None,
    user_input: ProductInput | None,
) -> str:
    material = (analysis.material if analysis and analysis.material else "качественный материал").strip().lower()
    fit = str(analysis.fit_type if analysis and analysis.fit_type else "").strip().lower()
    product_name = str(analysis.product_name if analysis and analysis.product_name else title).strip().lower()
    features = [str(item).strip().lower() for item in ((analysis.features if analysis else []) or []) if str(item).strip()]
    use_cases = ", ".join(policy.use_cases)
    context = {
        "subject_label": rule.ru_names[0],
        "subject_label_cap": rule.ru_names[0][:1].upper() + rule.ru_names[0][1:],
        "material": material,
        "use_cases": use_cases,
        "fit_sentence": _fit_sentence(rule.subject_code, fit),
        "rise_sentence": _rise_sentence(fit),
        "length_sentence": _length_sentence(product_name, features),
        "color_sentence": "",
    }
    blueprint = rule.description_blueprint
    parts = [
        blueprint.get("opening", "").format(**context),
        blueprint.get("fit", "").format(**context),
        blueprint.get("material", "").format(**context),
        blueprint.get("use_case", "").format(**context),
        blueprint.get("care", "").format(**context),
    ]
    text = _normalize_spaces(" ".join(part for part in parts if part))
    if any(term in text.casefold() for term in rule.forbidden_terms):
        text = text.replace("  ", " ")
    while len(text) < 420:
        text = _normalize_spaces(f"{text} {_support_sentence(policy, analysis)}")
    return text[:1000]


def _fit_sentence(subject_code: str, fit: str) -> str:
    if not fit:
        return "Крой остается удобным и уместным для своей категории."
    if "шир" in fit:
        return "Свободный крой помогает сохранить комфорт и современный силуэт."
    if "прям" in fit:
        return "Прямой крой выглядит аккуратно и остается удобным на каждый день."
    if "облег" in fit or "скинни" in fit:
        return "Более прилегающий крой подчеркивает силуэт и сохраняет комфортную посадку."
    if subject_code in {"bra", "panties"}:
        return "Посадка рассчитана на комфортное прилегание без лишнего давления."
    return f"Крой {fit} помогает сохранить уместный силуэт и комфорт в носке."


def _rise_sentence(fit: str) -> str:
    if "высок" in fit:
        return "Высокая посадка подчеркивает линию талии и делает модель удобной в движении."
    if "низк" in fit:
        return "Низкая посадка поддерживает расслабленный характер модели."
    if "сред" in fit:
        return "Средняя посадка остается универсальной для повседневной носки."
    return ""


def _length_sentence(product_name: str, features: list[str]) -> str:
    source = " ".join([product_name, *features]).casefold()
    if "мини" in source:
        return "Длина мини делает силуэт более легким и акцентным."
    if "миди" in source:
        return "Длина миди остается универсальной и удобной для повседневных образов."
    if "макси" in source:
        return "Длина макси помогает создать более выразительный и цельный образ."
    return ""


def _support_sentence(policy: ProductFamilyPolicy, analysis: ImageAnalysis | None) -> str:
    fit = (analysis.fit_type if analysis and analysis.fit_type else "").strip().lower()
    parts = []
    if fit:
        parts.append(f"Посадка {fit} поддерживает комфорт в движении и аккуратный силуэт.")
    if not parts:
        parts.append("Практичная конструкция помогает сохранить комфорт и аккуратный внешний вид в течение дня.")
    return " ".join(parts)


def _contains_forbidden_description_content(
    text: str,
    *,
    analysis: ImageAnalysis | None,
    user_input: ProductInput | None,
) -> bool:
    source = text.casefold()
    forbidden_markers = (
        "актуальные поисковые фразы",
        "в описании естественно раскрыты детали модели",
        "описание раскрывает материал",
        "релевантные поисковые запросы",
    )
    if any(marker in source for marker in forbidden_markers):
        return True
    color_values = [
        analysis.color if analysis else None,
        user_input.color if user_input else None,
        *[
            item.get("value")
            for item in ((analysis.variant_colors if analysis else []) or [])
            if isinstance(item, dict)
        ],
    ]
    return any(str(value).strip().casefold() in source for value in color_values if str(value or "").strip())


def _sanitize_description(
    text: str,
    analysis: ImageAnalysis | None,
    user_input: ProductInput | None,
) -> str:
    color_values = {
        str(value).strip().casefold()
        for value in [
            analysis.color if analysis else None,
            user_input.color if user_input else None,
            *[
                item.get("value")
                for item in ((analysis.variant_colors if analysis else []) or [])
                if isinstance(item, dict)
            ],
        ]
        if str(value or "").strip()
    }
    color_values.update({
        "белый", "белая", "белые", "черный", "черная", "черные",
        "красный", "красная", "красные", "синий", "синяя", "синие",
        "голубой", "голубая", "голубые", "зеленый", "зеленая", "зеленые",
        "желтый", "желтая", "желтые", "бежевый", "бежевая", "бежевые",
        "фиолетовый", "фиолетовая", "фиолетовые", "розовый", "розовая", "розовые",
        "серый", "серая", "серые", "коричневый", "коричневая", "коричневые",
    })
    kept: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", _normalize_spaces(text)):
        normalized = sentence.casefold()
        if re.search(r"\b(цвет|оттенок|цвета|оттенка)\b", normalized):
            continue
        if any(re.search(rf"(?<!\w){re.escape(color)}(?!\w)", normalized) for color in color_values):
            continue
        kept.append(sentence)
    return _normalize_spaces(" ".join(kept))[:1000]


def _audience_phrase(analysis: ImageAnalysis | None, user_input: ProductInput | None) -> str:
    source = " ".join(
        str(part or "")
        for part in [
            analysis.gender if analysis else "",
            user_input.gender if user_input else "",
            analysis.product_name if analysis else "",
            user_input.note if user_input else "",
        ]
    ).casefold()
    if any(token in source for token in ["мальчик", "boys", "boy"]):
        return "мальчикам и подросткам"
    if any(token in source for token in ["девоч", "girls", "girl"]):
        return "девочкам и подросткам"
    if any(token in source for token in ["дет", "kids", "children"]):
        return "детям"
    if "муж" in source:
        return "для мужчин"
    if "жен" in source:
        return "для женщин"
    return "для повседневного спроса"


def _extract_age_hint(analysis: ImageAnalysis | None, user_input: ProductInput | None) -> str | None:
    source = " ".join(
        str(part or "")
        for part in [
            user_input.note if user_input else "",
            analysis.product_name if analysis else "",
            " ".join(user_input.sizes if user_input else []),
        ]
    )
    years_match = re.search(r"(\d{1,2})\s*[-–]\s*(\d{1,2})\s*лет", source, re.IGNORECASE)
    if years_match:
        return f"{years_match.group(1)}-{years_match.group(2)} лет"
    single_year_match = re.search(r"с\s*(\d{1,2})\s*лет", source, re.IGNORECASE)
    if single_year_match:
        return f"от {single_year_match.group(1)} лет"
    plus_match = re.search(r"(\d{1,2})\s*\+", source)
    if plus_match:
        return f"от {plus_match.group(1)} лет"
    return None


def _family_title_cleanup(title: str, *, family: str, analysis: ImageAnalysis | None, user_input: ProductInput | None) -> str:
    result = title
    if family == "underwear":
        result = re.sub(r"(?:,\s*|\s+)(?:Облегающий|облегающий)$", "", result, flags=re.IGNORECASE).strip(", ")
        for addition in _underwear_title_additions(analysis, user_input):
            candidate = _normalize_spaces(f"{result} {addition}")
            if len(candidate) <= 60 and addition.casefold() not in result.casefold():
                result = candidate
    return result


def _underwear_title_additions(analysis: ImageAnalysis | None, user_input: ProductInput | None) -> list[str]:
    additions: list[str] = []
    source_text = " ".join(
        str(part or "")
        for part in [
            " ".join((analysis.features if analysis else []) or []),
            user_input.note if user_input else "",
        ]
    ).casefold()
    if any(token in source_text for token in ["человек-паук", "spider-man", "spiderman"]):
        additions.append("Человек-паук")
    if analysis and analysis.material and "хлоп" in analysis.material.casefold():
        additions.append("хлопок")
    return additions


def _token_key(value: str) -> str:
    text = re.sub(r"[^\w]+", "", value.casefold().replace("ё", "е"))
    for suffix in ("ами", "ями", "ого", "ему", "ому", "ыми", "ими", "ий", "ый", "ая", "ое", "ые", "ов", "ев", "ер", "ы", "и", "а", "о"):
        if text.endswith(suffix) and len(text) - len(suffix) >= 4:
            return text[: -len(suffix)]
    return text


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _pick_attribute(attributes: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = attributes.get(key)
        if isinstance(value, list):
            joined = " ".join(str(item).strip() for item in value if str(item).strip())
            if joined:
                return joined
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _dedupe_tokens(tokens: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        for part in _normalize_spaces(token).split():
            norm = _token_key(part)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            cleaned.append(part)
    return cleaned
