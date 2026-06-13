import re
from typing import Any

from app.schemas.card import ImageAnalysis, ProductInput


FORBIDDEN_CLAIMS = [
    "оригинал",
    "брендовый",
    "лечебный",
    "сертифицированный",
    "100% гарантия",
]


class SeoKeywordPlanner:
    @classmethod
    def build_plan(
        cls,
        *,
        category: str | None,
        subject_name: str | None,
        brand: str | None,
        gender: str | None,
        analysis: ImageAnalysis | None,
        user_input: ProductInput | None,
        confirmed_attributes: dict[str, Any] | None,
        wb_characteristics: list[dict[str, Any]] | None,
        product_family_policy: dict[str, Any] | None,
    ) -> dict[str, Any]:
        seo_inputs = user_input.seo_inputs if user_input else None
        subject_source = (subject_name or category or analysis.category if analysis else category or "товар").strip()
        gender_value = cls._first_non_empty(
            getattr(seo_inputs, "target_audience", None),
            gender,
            analysis.gender if analysis else None,
            user_input.gender if user_input else None,
        )
        material = cls._first_non_empty(
            getattr(seo_inputs, "material", None),
            cls._lookup_attr(confirmed_attributes, "composition", "Состав", "material"),
            analysis.material if analysis else None,
        )
        color = cls._first_non_empty(
            getattr(seo_inputs, "color", None),
            cls._lookup_attr(confirmed_attributes, "color", "Цвет"),
            analysis.color if analysis else None,
            user_input.color if user_input else None,
        )
        fit = cls._first_non_empty(
            getattr(seo_inputs, "fit", None),
            cls._lookup_attr(confirmed_attributes, "fit", "Тип посадки", "Покрой"),
            analysis.fit_type if analysis else None,
        )
        season = cls._first_non_empty(
            getattr(seo_inputs, "season", None),
            cls._lookup_attr(confirmed_attributes, "season", "Сезон"),
            analysis.season if analysis else None,
        )
        pattern = cls._first_non_empty(
            getattr(seo_inputs, "pattern", None),
            cls._lookup_attr(confirmed_attributes, "pattern", "Рисунок"),
        )
        key_feature = cls._first_non_empty(getattr(seo_inputs, "key_feature", None))

        category_tokens = cls._tokenize(subject_source)
        keyword_seed = []
        if getattr(seo_inputs, "primary_keyword_override", None):
            primary_keyword = seo_inputs.primary_keyword_override.strip()
        else:
            keyword_seed.extend(category_tokens[:3] or ["товар"])
            if gender_value:
                keyword_seed.extend(cls._tokenize(gender_value)[:2])
            if fit:
                keyword_seed.extend(cls._tokenize(fit)[:3])
            primary_keyword = cls._normalize_phrase(" ".join(keyword_seed))

        secondary_keywords: list[str] = []
        secondary_candidates = [
            *[
                cls._normalize_phrase(item)
                for item in getattr(seo_inputs, "secondary_keywords", []) or []
            ],
            cls._normalize_phrase(" ".join(filter(None, [subject_source, fit]))),
            cls._normalize_phrase(" ".join(filter(None, [subject_source, color]))),
            cls._normalize_phrase(" ".join(filter(None, [subject_source, material]))),
            cls._normalize_phrase(" ".join(filter(None, [subject_source, season]))),
            cls._normalize_phrase(" ".join(filter(None, [subject_source, pattern]))),
            cls._normalize_phrase(" ".join(filter(None, [fit, subject_source]))),
        ]
        for candidate in secondary_candidates:
            if (
                candidate
                and candidate.casefold() != primary_keyword.casefold()
                and candidate.casefold() not in {item.casefold() for item in secondary_keywords}
            ):
                secondary_keywords.append(candidate)

        long_tail_keywords: list[str] = []
        long_tail_candidates = [
            cls._normalize_phrase(" ".join(filter(None, [gender_value, color, subject_source, fit]))),
            cls._normalize_phrase(" ".join(filter(None, [subject_source, material, "для", getattr(seo_inputs, "purpose", None)]))),
            cls._normalize_phrase(" ".join(filter(None, [subject_source, key_feature, color]))),
        ]
        for candidate in long_tail_candidates:
            if candidate and candidate not in long_tail_keywords and len(candidate.split()) >= 3:
                long_tail_keywords.append(candidate)

        must_have_entities = cls._dedupe_preserve(
            [
                *cls._tokenize(primary_keyword),
                *(cls._tokenize(color) if color else []),
                *(cls._tokenize(fit) if fit else []),
                *(cls._tokenize(material) if material else []),
            ]
        )[:8]

        warnings: list[str] = []
        category_hint = cls._first_non_empty(category, subject_name)
        if analysis and category_hint and analysis.category and cls._normalize_phrase(category_hint) != cls._normalize_phrase(analysis.category):
            warnings.append("Image analysis conflicts with selected category; selected category was preferred.")

        confidence_signals = 0
        if category_hint:
            confidence_signals += 1
        if confirmed_attributes:
            confidence_signals += min(3, len([value for value in confirmed_attributes.values() if value]))
        if seo_inputs and any(seo_inputs.model_dump(exclude_none=True).values()):
            confidence_signals += 2
        if wb_characteristics:
            confidence_signals += 1
        confidence = min(1.0, round(confidence_signals / 7, 2))

        return {
            "primary_keyword": primary_keyword or cls._normalize_phrase(subject_source) or "товар",
            "secondary_keywords": secondary_keywords[:6],
            "long_tail_keywords": long_tail_keywords[:4],
            "must_have_entities": must_have_entities,
            "forbidden_claims": list(FORBIDDEN_CLAIMS),
            "search_intent": "marketplace product search",
            "confidence": confidence,
            "warnings": warnings,
            "brand_used": brand.strip() if brand and brand.strip() else None,
            "family": (product_family_policy or {}).get("family"),
        }

    @staticmethod
    def _lookup_attr(attributes: dict[str, Any] | None, *keys: str) -> str | None:
        if not attributes:
            return None
        for key in keys:
            value = attributes.get(key)
            if isinstance(value, list):
                joined = ", ".join(str(item).strip() for item in value if str(item).strip())
                if joined:
                    return joined
            if value is not None and str(value).strip():
                return str(value).strip()
        return None

    @staticmethod
    def _first_non_empty(*values: Any) -> str | None:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    @staticmethod
    def _normalize_phrase(value: str | None) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip(" ,.-")
        return text

    @staticmethod
    def _tokenize(value: str | None) -> list[str]:
        return [token for token in re.split(r"[\s,./()\-]+", str(value or "").strip()) if token]

    @staticmethod
    def _dedupe_preserve(values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(value)
        return result
