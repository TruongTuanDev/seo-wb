import re
from dataclasses import dataclass
from typing import Any

from app.schemas.card import ImageAnalysis, ProductInput


@dataclass(frozen=True)
class DescriptionRule:
    code: str
    roots: tuple[str, ...]
    subject_label: str
    focus: tuple[str, ...]
    use_cases: str
    styling: str
    care: str
    conflicting_subjects: tuple[str, ...]


DESCRIPTION_RULES = (
    DescriptionRule(
        code="trousers",
        roots=("брюк",),
        subject_label="брюки",
        focus=("силуэт", "посадка", "конструкция пояса и застежки"),
        use_cases="для повседневных образов, прогулок и учебы",
        styling="с рубашками, футболками, жакетами и базовой обувью",
        care="Деликатная стирка и сушка в расправленном виде помогают сохранить форму изделия.",
        conflicting_subjects=("джинс", "юбк", "плать"),
    ),
    DescriptionRule(
        code="jeans",
        roots=("джинс",),
        subject_label="джинсы",
        focus=("силуэт", "посадка", "детали кроя и отделки"),
        use_cases="на каждый день, для прогулок и активного отдыха",
        styling="с футболками, рубашками, худи и базовой обувью",
        care="Бережная стирка с вывернутым наизнанку изделием помогает дольше сохранить фактуру материала.",
        conflicting_subjects=("брюк", "юбк", "плать", "леггинс"),
    ),
    DescriptionRule(
        code="shorts",
        roots=("шорт",),
        subject_label="шорты",
        focus=("длина", "посадка", "форма штанин и конструктивные детали"),
        use_cases="для прогулок, отдыха и повседневных комплектов",
        styling="с футболками, топами, рубашками и легкой обувью",
        care="Щадящая стирка и аккуратная сушка помогают сохранить посадку и внешний вид изделия.",
        conflicting_subjects=("брюк", "джинс", "юбк"),
    ),
    DescriptionRule(
        code="skirt",
        roots=("юбк",),
        subject_label="юбка",
        focus=("длина", "силуэт", "пояс и конструктивные детали"),
        use_cases="для повседневных образов, прогулок и учебы",
        styling="с футболками, блузками, рубашками и кардиганами",
        care="Деликатная стирка и аккуратная сушка помогают сохранить силуэт изделия.",
        conflicting_subjects=("плать", "джинс", "брюк"),
    ),
    DescriptionRule(
        code="dress",
        roots=("плать",),
        subject_label="платье",
        focus=("длина", "силуэт", "рукава, вырез и детали конструкции"),
        use_cases="для повседневных выходов, прогулок и особых случаев, если это соответствует модели",
        styling="с базовой обувью, жакетом или легким верхним слоем",
        care="Бережная стирка и сушка в расправленном виде помогают сохранить форму модели.",
        conflicting_subjects=("юбк", "джинс", "брюк"),
    ),
    DescriptionRule(
        code="shirt",
        roots=("рубаш",),
        subject_label="рубашка",
        focus=("крой", "длина рукава", "воротник, застежка и карманы"),
        use_cases="для повседневных образов, учебы и прогулок",
        styling="с брюками, джинсами, юбками или шортами",
        care="Стирка на щадящем режиме и сушка на плечиках помогают сохранить аккуратный вид.",
        conflicting_subjects=("футбол", "худи", "свитшот", "куртк"),
    ),
    DescriptionRule(
        code="jacket",
        roots=("куртк",),
        subject_label="куртка",
        focus=("длина", "крой", "застежка, воротник, капюшон и карманы"),
        use_cases="для города, прогулок и поездок в подходящую по погоде температуру",
        styling="с базовыми вещами повседневного гардероба",
        care="При уходе следует учитывать рекомендации на ярлыке, чтобы сохранить форму и свойства материала.",
        conflicting_subjects=("пальто", "рубаш", "худи", "свитшот"),
    ),
)

GENERIC_RULE = DescriptionRule(
    code="generic",
    roots=(),
    subject_label="модель",
    focus=("крой", "конструктивные особенности", "комфорт в движении"),
    use_cases="для повседневного использования",
    styling="с подходящими базовыми вещами гардероба",
    care="Бережный уход в соответствии с рекомендациями на ярлыке помогает сохранить внешний вид изделия.",
    conflicting_subjects=(),
)

DESCRIPTION_META_PATTERNS = (
    "актуальные поисковые фразы",
    "в описании естественно раскрыты",
    "описание раскрывает",
    "ключевые слова",
    "seo",
    "сео",
)

COMMON_COLOR_ROOTS = (
    "бежев",
    "бел",
    "бирюз",
    "бордов",
    "голуб",
    "графит",
    "горчичн",
    "желт",
    "зелен",
    "золот",
    "кремов",
    "коричнев",
    "красн",
    "лилов",
    "молочн",
    "мятн",
    "оливков",
    "оранжев",
    "песочн",
    "розов",
    "салатов",
    "серебрист",
    "сер",
    "сиренев",
    "син",
    "терракот",
    "фиолет",
    "хаки",
    "черн",
)

GENDER_ROOTS = (
    "женск",
    "мужск",
    "девоч",
    "мальчик",
    "девуш",
    "женщин",
    "мужчин",
)


def build_description_prompt_context(subject_name: str | None) -> dict[str, Any]:
    rule = resolve_description_rule(subject_name)
    return {
        "subject_code": rule.code,
        "subject_label": rule.subject_label,
        "focus": list(rule.focus),
        "use_cases": rule.use_cases,
        "styling": rule.styling,
        "care": rule.care,
        "requirements": [
            "Write natural Russian prose in 3-5 short paragraphs without emoji or bullet lists.",
            "Describe only facts supported by image_analysis, user_input, or characteristics.",
            "Keep the product subject consistent in every sentence.",
            "Do not mention any concrete color, gender, audience, brand, SEO process, or keyword list.",
            "Do not invent composition, season, closure, lining, protection, certification, or guarantees.",
            "Another garment may appear only as an obvious styling companion.",
            "Target 350-750 characters and avoid generic filler.",
        ],
    }


def finalize_product_description(
    subject_name: str | None,
    candidate: str | None,
    analysis: ImageAnalysis,
    user_input: ProductInput,
) -> str:
    normalized = _normalize(candidate)
    if normalized and description_is_safe(subject_name, normalized, analysis, user_input):
        return normalized[:1000].strip()
    return build_product_description(subject_name, analysis, user_input)


def description_is_safe(
    subject_name: str | None,
    description: str,
    analysis: ImageAnalysis,
    user_input: ProductInput,
) -> bool:
    text = _normalize(description)
    folded = _fold(text)
    if len(text) < 220 or len(text) > 1000:
        return False
    if any(pattern in folded for pattern in DESCRIPTION_META_PATTERNS):
        return False
    if any(root in folded for root in GENDER_ROOTS):
        return False
    if _contains_common_color(folded):
        return False
    explicit_colors = [
        analysis.color,
        user_input.color,
        *[item.get("value") for item in analysis.variant_colors if isinstance(item, dict)],
        _first_value(user_input.attributes, analysis.attributes, keys=("Цвет", "color")),
    ]
    for color in explicit_colors:
        if _contains_attribute_value(folded, color):
            return False

    rule = resolve_description_rule(subject_name)
    for conflict in rule.conflicting_subjects:
        if _has_product_subject_conflict(text, conflict):
            return False

    material = _first_value(
        user_input.attributes,
        analysis.attributes,
        keys=("Состав", "Материал", "composition", "material"),
    ) or analysis.material
    material_folded = _fold(material)
    if "лен" in material_folded and any(root in folded for root in ("деним", "джинсов")):
        return False
    if any(root in material_folded for root in ("деним", "джинс")) and "льнян" in folded:
        return False

    fit_source = " ".join(
        str(value or "")
        for value in (
            analysis.fit_type,
            _first_value(user_input.attributes, analysis.attributes, keys=("Покрой", "Фасон", "fit", "silhouette")),
        )
    )
    fit_folded = _fold(fit_source)
    if "шир" in fit_folded and any(root in folded for root in ("скинни", "облегающ")):
        return False
    if any(root in fit_folded for root in ("скинни", "облегающ")) and "широк" in folded:
        return False

    rise = _first_value(user_input.attributes, analysis.attributes, keys=("Тип посадки", "Посадка", "rise"))
    rise_folded = _fold(rise)
    if "высок" in rise_folded and "низкой посад" in folded:
        return False
    if "низк" in rise_folded and "высокой посад" in folded:
        return False
    return True


def build_product_description(
    subject_name: str | None,
    analysis: ImageAnalysis,
    user_input: ProductInput,
) -> str:
    rule = resolve_description_rule(subject_name)
    label = rule.subject_label
    fit = _supported_fit(analysis, user_input)
    material = _material_phrase(analysis, user_input)
    features = _safe_features(analysis.features, rule=rule, material=material)

    opening = f"{label.capitalize()} отличается продуманным кроем и помогает сохранить комфорт в течение дня."
    if rule.code == "trousers":
        opening = "Брюки с продуманным кроем помогают создать аккуратный образ и сохраняют комфорт в течение дня."
    elif rule.code in {"dress", "skirt", "shirt", "jacket"}:
        opening = f"{label.capitalize()} отличается продуманным кроем и помогает создать аккуратный, цельный образ."
    elif rule.code == "jeans":
        opening = "Джинсы сочетают выразительный силуэт, практичность и комфорт для повседневной носки."
    elif rule.code == "shorts":
        opening = "Шорты обеспечивают свободу движений и легко вписываются в повседневный гардероб."

    construction_parts = []
    if fit:
        construction_parts.append(fit)
    construction_parts.extend(features[:3])
    if construction_parts:
        construction = (
            f"Особенности модели: {', '.join(construction_parts)}. "
            "Детали подобраны так, чтобы изделие удобно сидело и не перегружало силуэт."
        )
    else:
        construction = (
            f"В модели важны {', '.join(rule.focus[:2])}. "
            "Конструкция рассчитана на удобную посадку и свободу движений."
        )

    material_sentence = (
        f"Материал на основе {material} подходит для регулярной носки и помогает изделию сохранять аккуратный вид."
        if material
        else "Материал выглядит аккуратно и подходит для регулярной носки; точный состав следует указывать по данным ярлыка."
    )
    use_sentence = (
        f"Модель подходит {rule.use_cases} и легко сочетается {rule.styling}. "
        f"{rule.care}"
    )
    return _normalize(" ".join((opening, construction, material_sentence, use_sentence)))[:1000]


def resolve_description_rule(subject_name: str | None) -> DescriptionRule:
    source = _fold(subject_name)
    for rule in DESCRIPTION_RULES:
        if any(root in source for root in rule.roots):
            return rule
    label = _safe_subject_label(subject_name)
    if label:
        return DescriptionRule(
            code=GENERIC_RULE.code,
            roots=(),
            subject_label=label,
            focus=GENERIC_RULE.focus,
            use_cases=GENERIC_RULE.use_cases,
            styling=GENERIC_RULE.styling,
            care=GENERIC_RULE.care,
            conflicting_subjects=(),
        )
    return GENERIC_RULE


def _has_product_subject_conflict(description: str, conflict_root: str) -> bool:
    for sentence in re.split(r"[.!?]+", description):
        folded = _fold(sentence)
        if conflict_root not in folded:
            continue
        if any(marker in folded for marker in ("сочета", "комбиниру", "носить с", "в комплекте с")):
            continue
        return True
    return False


def _supported_fit(analysis: ImageAnalysis, user_input: ProductInput) -> str:
    value = analysis.fit_type or _first_value(
        user_input.attributes,
        analysis.attributes,
        keys=("Покрой", "Фасон", "Тип посадки", "fit", "silhouette", "rise"),
    )
    text = _normalize(value).strip(" ,.;:-")
    if not text or _contains_common_color(_fold(text)) or any(root in _fold(text) for root in GENDER_ROOTS):
        return ""
    return text.lower()


def _safe_features(features: list[str], *, rule: DescriptionRule, material: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    material_folded = _fold(material)
    for item in features:
        text = _normalize(item).strip(" ,.;:-").lower()
        folded = _fold(text)
        if not text or len(text) > 80:
            continue
        if _contains_common_color(folded) or any(root in folded for root in GENDER_ROOTS):
            continue
        if any(pattern in folded for pattern in DESCRIPTION_META_PATTERNS):
            continue
        if any(conflict in folded for conflict in rule.conflicting_subjects):
            continue
        if "лен" in material_folded and any(root in folded for root in ("деним", "джинсов")):
            continue
        if any(root in material_folded for root in ("деним", "джинс")) and "льнян" in folded:
            continue
        if folded in seen:
            continue
        seen.add(folded)
        result.append(text)
    return result


def _material_phrase(analysis: ImageAnalysis, user_input: ProductInput) -> str:
    value = _first_value(
        user_input.attributes,
        analysis.attributes,
        keys=("Состав", "Материал", "composition", "material"),
    ) or analysis.material
    text = _normalize(value).lower()
    if not text:
        return ""
    replacements = {
        "лен": "льна",
        "лён": "льна",
        "хлопок": "хлопка",
        "деним": "денима",
        "шерсть": "шерсти",
        "вискоза": "вискозы",
        "полиэстер": "полиэстера",
        "экокожа": "экокожи",
    }
    return replacements.get(text, text)


def _first_value(*sources: dict[str, Any], keys: tuple[str, ...]) -> str:
    normalized_keys = {_fold(key) for key in keys}
    for source in sources:
        for key, value in (source or {}).items():
            if _fold(key) not in normalized_keys or value in (None, "", []):
                continue
            if isinstance(value, list):
                return ", ".join(str(item).strip() for item in value if str(item).strip())
            return str(value).strip()
    return ""


def _safe_subject_label(subject_name: str | None) -> str:
    text = _normalize(subject_name).lower()
    if not text or len(text) > 60:
        return ""
    if not re.fullmatch(r"[а-яё -]+", text, flags=re.IGNORECASE):
        return ""
    return text


def _contains_attribute_value(folded_text: str, value: Any) -> bool:
    for token in re.findall(r"[а-яё]+", _fold(value)):
        if len(token) < 4:
            continue
        stem = token[: max(4, len(token) - 3)]
        if stem in folded_text:
            return True
    return False


def _contains_common_color(folded_text: str) -> bool:
    false_positive_prefixes = ("бель", "белк", "сертифик", "сервис", "серия", "синтет")
    for token in re.findall(r"[а-яё]+", folded_text):
        if token.startswith(false_positive_prefixes):
            continue
        if any(token.startswith(root) for root in COMMON_COLOR_ROOTS):
            return True
    return False


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _fold(value: Any) -> str:
    return _normalize(value).replace("ё", "е").casefold()
