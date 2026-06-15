import re
from hashlib import sha256
from typing import Any

from app.schemas.card import ImageAnalysis, ProductInput


_FORBIDDEN_TITLE_VALUES = {
    "женский",
    "женская",
    "женские",
    "мужской",
    "мужская",
    "мужские",
    "детский",
    "детская",
    "детские",
}

_FORBIDDEN_GENERIC_TERMS = {
    "женский",
    "женская",
    "женские",
    "мужской",
    "мужская",
    "мужские",
    "детский",
    "детская",
    "детские",
    "для девочек",
    "для мальчиков",
    "летний",
    "летняя",
    "летние",
    "зимний",
    "зимняя",
    "зимние",
    "демисезонный",
    "демисезонная",
    "демисезонные",
}

_SUBJECT_FEATURE_RULES: dict[str, tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]] = {
    "shorts": (
        (("бермуд",), ("бермуд",)),
        (("карго",), ("карго",)),
        (("высок", "завыш"), ("высок", "завыш")),
        (("средн", "стандартн"), ("средн", "стандартн")),
        (("низк", "заниж"), ("низк", "заниж")),
    ),
    "skirt": (
        (("мини",), ("мини",)),
        (("миди",), ("миди",)),
        (("макси",), ("макси",)),
        (("а-силуэт", "а силуэт"), ("а-силуэт", "а силуэт")),
        (("карандаш",), ("карандаш",)),
        (("плисс",), ("плисс",)),
        (("запах",), ("запах",)),
        (("разрез",), ("разрез",)),
    ),
    "dress": (
        (("мини",), ("мини",)),
        (("миди",), ("миди",)),
        (("макси",), ("макси",)),
        (("притал",), ("притал",)),
        (("а-силуэт", "а силуэт"), ("а-силуэт", "а силуэт")),
        (("трапец",), ("трапец",)),
        (("запах",), ("запах",)),
        (("разрез",), ("разрез",)),
        (("длинн", "рукав"), ("длинн", "рукав")),
        (("коротк", "рукав"), ("коротк", "рукав")),
    ),
    "shirt": (
        (("оверсайз",), ("оверсайз",)),
        (("свобод",), ("свобод",)),
        (("притал",), ("притал",)),
        (("длинн", "рукав"), ("длинн", "рукав")),
        (("коротк", "рукав"), ("коротк", "рукав")),
        (("без рукав",), ("без рукав",)),
        (("воротник",), ("воротник",)),
        (("без воротник",), ("без воротник",)),
    ),
    "jacket": (
        (("утепл",), ("утепл",)),
        (("стеган", "стёган"), ("стеган", "стёган")),
        (("укороч",), ("укороч",)),
        (("удлин",), ("удлин",)),
        (("оверсайз",), ("оверсайз",)),
        (("капюш",), ("капюш",)),
        (("пояс",), ("пояс",)),
    ),
}

def select_best_ai_title(
    subject_name: str,
    candidates: list[str],
    analysis: ImageAnalysis,
    user_input: ProductInput,
    brand: str | None = None,
) -> str | None:
    subject = _clean(subject_name)
    valid: list[tuple[int, int, str]] = []
    for index, candidate in enumerate(candidates):
        title = _clean(candidate)
        if not _is_valid_ai_title(title, subject, analysis, user_input, brand):
            continue
        valid.append((_score_ai_title(title, analysis, user_input), -index, title))
    return max(valid, default=(0, 0, None))[2]


def _is_valid_ai_title(
    title: str,
    subject: str,
    analysis: ImageAnalysis,
    user_input: ProductInput,
    brand: str | None,
) -> bool:
    if not 10 <= len(title) <= 60:
        return False
    if subject and not title.casefold().startswith(subject.casefold()):
        return False
    if not re.search(r"[А-Яа-яЁё]", title):
        return False
    if any(symbol in title for symbol in (",", "/", "\\", "|", "#", ";")):
        return False
    normalized = _norm(title)
    forbidden_values = {
        _norm(analysis.color),
        _norm(user_input.color),
        _norm(analysis.gender),
        _norm(user_input.gender),
        _norm(analysis.material),
        _norm(analysis.season),
        _norm(brand),
        _norm(user_input.brand),
    }
    forbidden_values.discard("")
    if any(_contains_forbidden_value(normalized, value) for value in forbidden_values):
        return False
    if any(term in normalized for term in _FORBIDDEN_GENERIC_TERMS):
        return False
    if re.search(r"\b(?:высокая|средняя|низкая)\b(?!\s+посадк)", normalized):
        return False
    title_body = normalized[len(_norm(subject)):].strip() if subject and normalized.startswith(_norm(subject)) else normalized
    words = re.findall(r"[а-яё0-9-]+", title_body)
    if _contains_inflected_forbidden_terms(words, analysis, user_input):
        return False
    if re.search(r"\b\d{1,2}\s*(?:лет|год|года)\b", normalized):
        return False
    meaningful = [word for word in words if len(word) > 2]
    if len(meaningful) != len(set(meaningful)):
        return False
    if _contains_unsupported_subject_feature(normalized, subject, analysis, user_input):
        return False
    return True


def _contains_unsupported_subject_feature(
    title: str,
    subject: str,
    analysis: ImageAnalysis,
    user_input: ProductInput,
) -> bool:
    subject_code = _subject_code(subject)
    rules = _SUBJECT_FEATURE_RULES.get(subject_code, ())
    if not rules:
        return False
    evidence = _collect_evidence(analysis, user_input, None)
    for title_markers, evidence_markers in rules:
        if all(marker in title for marker in title_markers) and not all(marker in evidence for marker in evidence_markers):
            return True
    return False


def _contains_inflected_forbidden_terms(
    title_words: list[str],
    analysis: ImageAnalysis,
    user_input: ProductInput,
) -> bool:
    source = _norm(
        " ".join(
            [
                analysis.color or "",
                user_input.color or "",
                analysis.material or "",
            ]
        )
    )
    roots = {
        "бел": ("бел",),
        "беж": ("беж",),
        "бирюз": ("бирюз",),
        "бордов": ("бордов",),
        "голуб": ("голуб",),
        "желт": ("желт", "жёлт"),
        "зел": ("зелен", "зелён"),
        "корич": ("корич",),
        "красн": ("красн",),
        "оранж": ("оранж",),
        "розов": ("розов",),
        "син": ("син",),
        "фиолет": ("фиолет",),
        "черн": ("черн", "чёрн"),
        "вискоз": ("вискоз",),
        "деним": ("деним",),
        "замш": ("замш",),
        "кож": ("кож",),
        "лен": ("льня",),
        "лён": ("льня",),
        "полиэст": ("полиэст",),
        "трикот": ("трикот",),
        "хлоп": ("хлоп",),
        "шелк": ("шелк", "шёлк"),
        "шёлк": ("шелк", "шёлк"),
        "шерст": ("шерст",),
    }
    active_roots = {
        root
        for marker, variants in roots.items()
        if marker in source
        for root in variants
    }
    if any(word.startswith(root) for word in title_words for root in active_roots):
        return True
    if "сер" in source and any(
        word in {"серый", "серая", "серое", "серые", "серого", "серой", "серых"}
        for word in title_words
    ):
        return True
    return False


def _contains_forbidden_value(title: str, value: str) -> bool:
    title_words = re.findall(r"[а-яёa-z0-9-]+", title)
    value_words = re.findall(r"[а-яёa-z0-9-]+", value)
    for forbidden_word in value_words:
        if len(forbidden_word) >= 5:
            stem = forbidden_word[:5]
            if any(word.startswith(stem) for word in title_words):
                return True
        elif forbidden_word in title_words:
            return True
    return False


def _score_ai_title(title: str, analysis: ImageAnalysis, user_input: ProductInput) -> int:
    normalized = _norm(title)
    evidence = _norm(
        " ".join(
            [
                analysis.product_name or "",
                analysis.fit_type or "",
                *analysis.features,
                *[str(value) for value in analysis.attributes.values()],
                *[str(value) for value in user_input.attributes.values()],
            ]
        )
    )
    score = 100
    if 22 <= len(title) <= 52:
        score += 8
    for token in re.findall(r"[а-яё-]{4,}", normalized):
        stem = token[:5]
        if stem in evidence:
            score += 2
    if any(phrase in normalized for phrase in ("с ", "со ", "без ", "оверсайз", "миди", "макси", "мини")):
        score += 3
    score -= max(0, len(title) - 52)
    return score


def build_product_title(
    subject_name: str,
    analysis: ImageAnalysis,
    user_input: ProductInput,
    candidate_title: str | None = None,
) -> str:
    subject = _clean(subject_name) or _clean(analysis.category) or _clean(user_input.category) or "Товар"
    safe_candidate = select_best_ai_title(subject, [candidate_title or ""], analysis, user_input)
    if safe_candidate:
        return safe_candidate
    evidence = _collect_evidence(analysis, user_input, candidate_title)
    candidates = _subject_title_candidates(subject, evidence)
    if not candidates:
        return _safe_generic_fallback(subject)
    fingerprint = _product_fingerprint(analysis, user_input, evidence)
    title = candidates[int(sha256(fingerprint.encode("utf-8")).hexdigest(), 16) % len(candidates)]
    return (title if len(title) >= 10 else f"{subject} базовая модель")[:60].strip()


def _subject_code(subject: str) -> str:
    normalized = _norm(subject)
    mappings = (
        ("trousers", ("брюк",)),
        ("jeans", ("джинс",)),
        ("shorts", ("шорт",)),
        ("skirt", ("юбк",)),
        ("dress", ("плать",)),
        ("shirt", ("рубаш",)),
        ("jacket", ("куртк",)),
    )
    for code, roots in mappings:
        if any(root in normalized for root in roots):
            return code
    return "generic"


def _safe_generic_fallback(subject: str) -> str:
    return f"{subject} базового кроя"[:60].strip()


def _subject_title_candidates(subject: str, evidence: str) -> list[str]:
    code = _subject_code(subject)
    if code in {"trousers", "jeans"}:
        silhouette = _silhouette_phrase(evidence)
        rise = _rise_phrase(evidence)
        detail = _bottom_detail_phrase(evidence, code)
        return _title_candidates(subject, silhouette, rise, detail)
    if code == "shorts":
        return _shorts_title_candidates(subject, evidence)
    if code == "skirt":
        return _skirt_title_candidates(subject, evidence)
    if code == "dress":
        return _dress_title_candidates(subject, evidence)
    if code == "shirt":
        return _shirt_title_candidates(subject, evidence)
    if code == "jacket":
        return _jacket_title_candidates(subject, evidence)
    return []


def _shorts_title_candidates(subject: str, evidence: str) -> list[str]:
    model = _match_phrase(
        evidence,
        (
            (("бермуд",), "бермуды"),
            (("карго",), "карго"),
        ),
    )
    subject_label = f"{subject}-бермуды" if model == "бермуды" else subject
    model_phrase = None if model == "бермуды" else model
    silhouette = _silhouette_phrase(evidence)
    rise = _rise_phrase(evidence)
    detail = _match_phrase(evidence, ((("подворот",), "с подворотами"), (("лампас",), "с лампасами")))
    return _valid_candidates(
        _join_unique(subject_label, model_phrase, silhouette, rise, detail),
        _join_unique(subject_label, silhouette, model_phrase, detail, rise),
        _join_unique(subject_label, rise, silhouette, model_phrase, detail),
    )


def _skirt_title_candidates(subject: str, evidence: str) -> list[str]:
    length = _length_phrase(evidence)
    silhouette = _match_phrase(
        evidence,
        (
            (("а-силуэт", "а силуэт", "a-line"), "А-силуэта"),
            (("карандаш", "pencil"), "карандаш"),
            (("плисс", "pleat"), "плиссированные"),
            (("трапец",), "трапециевидного кроя"),
            (("прям",), "прямого кроя"),
        ),
    )
    detail = _match_phrase(
        evidence,
        (
            (("запах",), "с запахом"),
            (("разрез",), "с разрезом"),
            (("пуговиц",), "на пуговицах"),
        ),
    )
    return _valid_candidates(_join_unique(subject, length, silhouette, detail))


def _dress_title_candidates(subject: str, evidence: str) -> list[str]:
    length = _length_phrase(evidence)
    silhouette = _match_phrase(
        evidence,
        (
            (("притал", "fitted"), "приталенного силуэта"),
            (("а-силуэт", "а силуэт", "a-line"), "А-силуэта"),
            (("трапец",), "силуэта трапеция"),
            (("свобод", "oversize"), "свободного кроя"),
            (("прям",), "прямого кроя"),
        ),
    )
    construction = (
        _required_phrase(evidence, ("длинн", "рукав"), "с длинным рукавом")
        or _required_phrase(evidence, ("коротк", "рукав"), "с коротким рукавом")
        or _match_phrase(
            evidence,
            (
                (("без рукав",), "без рукавов"),
                (("запах",), "с запахом"),
                (("разрез",), "с разрезом"),
            ),
        )
    )
    return _valid_candidates(_join_unique(subject, length, silhouette, construction))


def _shirt_title_candidates(subject: str, evidence: str) -> list[str]:
    fit = _match_phrase(
        evidence,
        (
            (("оверсайз", "oversize"), "оверсайз"),
            (("свобод", "loose"), "свободного кроя"),
            (("притал", "fitted"), "приталенного кроя"),
            (("прям", "straight"), "прямого кроя"),
        ),
    )
    sleeve = (
        _required_phrase(evidence, ("длинн", "рукав"), "с длинным рукавом")
        or _required_phrase(evidence, ("коротк", "рукав"), "с коротким рукавом")
        or _match_phrase(evidence, ((("без рукав",), "без рукавов"),))
    )
    detail = _match_phrase(
        evidence,
        (
            (("без воротник",), "без воротника"),
            (("воротник",), "с воротником"),
            (("пуговиц",), "на пуговицах"),
            (("накладн", "карман"), "с накладными карманами"),
        ),
    )
    combined_detail = _combine_with_and(sleeve, detail)
    return _valid_candidates(
        _join_unique(subject, fit, combined_detail or sleeve, None if combined_detail else detail)
    )


def _jacket_title_candidates(subject: str, evidence: str) -> list[str]:
    construction = _match_phrase(
        evidence,
        (
            (("утепл",), "утепленные"),
            (("стеган", "стёган"), "стеганые"),
            (("укороч",), "укороченные"),
            (("удлин",), "удлиненные"),
            (("оверсайз",), "оверсайз"),
        ),
    )
    detail = _match_phrase(
        evidence,
        (
            (("капюш",), "с капюшоном"),
            (("пояс",), "с поясом"),
            (("воротник", "стойк"), "с воротником-стойкой"),
            (("молн",), "на молнии"),
        ),
    )
    secondary = _match_phrase(
        evidence,
        (
            (("накладн", "карман"), "с накладными карманами"),
            (("кулиск",), "с кулиской"),
        ),
    )
    return _valid_candidates(_join_unique(subject, construction, detail, secondary))


def _valid_candidates(*candidates: str) -> list[str]:
    return list(dict.fromkeys(candidate for candidate in candidates if 10 <= len(candidate) <= 60))


def _combine_with_and(first: str | None, second: str | None) -> str | None:
    if not first or not second or not second.startswith("с "):
        return None
    return f"{first} и {second[2:]}"


def _required_phrase(source: str, tokens: tuple[str, ...], phrase: str) -> str | None:
    return phrase if all(token in source for token in tokens) else None


def _length_phrase(source: str) -> str | None:
    return _match_phrase(
        source,
        (
            (("мини",), "мини"),
            (("миди",), "миди"),
            (("макси",), "макси"),
            (("укороч",), "укороченные"),
            (("удлин",), "удлиненные"),
        ),
    )


def _bottom_detail_phrase(source: str, subject_code: str) -> str | None:
    subject_specific = ()
    if subject_code == "shorts":
        subject_specific = (
            (("бермуд",), "бермуды"),
            (("подворот",), "с подворотами"),
        )
    return _match_phrase(
        source,
        subject_specific
        + (
            (("рван", "distress", "ripped"), "рваные"),
            (("лампас",), "с лампасами"),
            (("разрез",), "с разрезами"),
        ),
    )


def _title_candidates(subject: str, silhouette: str | None, rise: str | None, detail: str | None) -> list[str]:
    candidates = [
        _join_unique(subject, silhouette, rise, detail),
        _join_unique(subject, silhouette, detail, rise),
    ]
    alternate_rise = _alternate_rise_phrase(rise)
    if alternate_rise:
        candidates.append(_join_unique(subject, silhouette, alternate_rise, detail))
    construction = _silhouette_construction(silhouette)
    if rise and construction:
        candidates.append(_join_unique(subject, rise, construction, detail))
    if alternate_rise and construction:
        candidates.append(_join_unique(subject, alternate_rise, construction, detail))
    if rise and silhouette:
        combined = _combined_silhouette_rise(silhouette, rise)
        if combined:
            candidates.append(_join_unique(subject, combined, detail))
    return list(dict.fromkeys(candidate for candidate in candidates if 10 <= len(candidate) <= 60))


def _product_fingerprint(analysis: ImageAnalysis, user_input: ProductInput, evidence: str) -> str:
    attributes = "|".join(f"{key}:{value}" for key, value in sorted(user_input.attributes.items()))
    return "|".join(
        [
            _norm(analysis.product_name),
            _norm(analysis.category),
            _norm(analysis.fit_type),
            _norm(user_input.vendor_code),
            _norm(analysis.vendor_code_base),
            _norm(user_input.note),
            attributes.casefold(),
            evidence,
        ]
    )


def _silhouette_construction(silhouette: str | None) -> str | None:
    return {
        "широкие": "широкого кроя",
        "прямые": "прямого кроя",
        "зауженные": "зауженного кроя",
        "облегающие": "облегающего кроя",
        "свободного кроя": "свободного кроя",
        "клеш": "расклешенного кроя",
        "карго": "в стиле карго",
        "палаццо": "палаццо",
        "оверсайз": "в стиле оверсайз",
    }.get(silhouette or "")


def _combined_silhouette_rise(silhouette: str, rise: str) -> str | None:
    if silhouette == "широкие":
        return f"с широкими штанинами и {_rise_without_preposition(rise)}"
    if silhouette == "прямые":
        return f"прямого кроя с {_rise_without_preposition(rise)}"
    return None


def _rise_without_preposition(rise: str) -> str:
    return re.sub(r"^(?:с|со)\s+", "", rise, flags=re.IGNORECASE)


def _alternate_rise_phrase(rise: str | None) -> str | None:
    return {
        "с высокой посадкой": "с завышенной талией",
        "со средней посадкой": "со стандартной посадкой",
        "с низкой посадкой": "с заниженной талией",
    }.get(rise or "")


def _join_unique(*parts: str | None) -> str:
    result: list[str] = []
    for part in parts:
        value = _clean(part)
        if value and value.casefold() not in " ".join(result).casefold():
            result.append(value)
    return _clean(" ".join(result))


def _collect_evidence(analysis: ImageAnalysis, user_input: ProductInput, candidate_title: str | None) -> str:
    values: list[Any] = [
        analysis.product_name,
        analysis.fit_type,
        *analysis.features,
        *analysis.attributes.values(),
        *user_input.attributes.values(),
        candidate_title,
    ]
    blocked = {
        _norm(analysis.color),
        _norm(user_input.color),
        _norm(analysis.gender),
        _norm(user_input.gender),
        _norm(analysis.material),
        _norm(analysis.season),
    } | _FORBIDDEN_TITLE_VALUES
    words = []
    for value in values:
        for word in _clean(str(value or "")).split():
            if _norm(word).strip(",.-/") not in blocked:
                words.append(word)
    return _norm(" ".join(words))


def _silhouette_phrase(source: str) -> str | None:
    mappings = (
        (("палаццо", "palazzo"), "палаццо"),
        (("карго", "cargo"), "карго"),
        (("клеш", "расклеш", "flare"), "клеш"),
        (("широк", "wide"), "широкие"),
        (("прям", "straight"), "прямые"),
        (("зауж", "tapered"), "зауженные"),
        (("оверсайз", "oversize"), "оверсайз"),
        (("свобод", "loose"), "свободного кроя"),
        (("облег", "skinny", "скинни"), "облегающие"),
    )
    return _match_phrase(source, mappings)


def _rise_phrase(source: str) -> str | None:
    mappings = (
        (("высок", "high rise", "high-rise"), "с высокой посадкой"),
        (("средн", "mid rise", "mid-rise"), "со средней посадкой"),
        (("низк", "low rise", "low-rise"), "с низкой посадкой"),
    )
    return _match_phrase(source, mappings)


def _detail_phrase(source: str) -> str | None:
    mappings = (
        (("рван", "distress", "ripped"), "рваные"),
        (("лампас",), "с лампасами"),
        (("разрез",), "с разрезами"),
        (("утепл",), "утепленные"),
    )
    return _match_phrase(source, mappings)


def _match_phrase(source: str, mappings: tuple[tuple[tuple[str, ...], str], ...]) -> str | None:
    for tokens, phrase in mappings:
        if any(token in source for token in tokens):
            return phrase
    return None


def _clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" ,.-/")


def _norm(value: str | None) -> str:
    return _clean(value).casefold()
