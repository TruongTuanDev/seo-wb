from __future__ import annotations

import re
from typing import Any

from app.services.subject_rule_registry import SubjectRuleRegistry


class MarketplacePolicyValidator:
    _TITLE_FORBIDDEN_WORDS = (
        "женский",
        "женские",
        "мужской",
        "мужские",
        "для девочек",
        "для мальчиков",
        "лето",
        "зима",
        "демисезон",
        "всесезонный",
    )
    _COMMON_COLORS = (
        "белый",
        "белая",
        "белые",
        "черный",
        "черная",
        "черные",
        "красный",
        "красная",
        "красные",
        "синий",
        "синяя",
        "синие",
        "голубой",
        "голубая",
        "голубые",
        "зеленый",
        "зеленая",
        "зеленые",
        "желтый",
        "желтая",
        "желтые",
        "бежевый",
        "бежевая",
        "бежевые",
        "фиолетовый",
        "фиолетовая",
        "фиолетовые",
        "розовый",
        "розовая",
        "розовые",
        "серый",
        "серая",
        "серые",
        "коричневый",
        "коричневая",
        "коричневые",
        "оранжевый",
        "оранжевая",
        "оранжевые",
    )

    @classmethod
    def validate(
        cls,
        *,
        subject_name: str | None,
        title: str,
        description: str,
        confirmed_attributes: dict[str, Any] | None,
        inferred_attributes: dict[str, Any] | None,
    ) -> dict[str, Any]:
        title_norm = cls._norm(title)
        description_norm = cls._norm(description)
        blocking_issues: list[str] = []
        warnings: list[str] = []
        score = 100

        if len(title) > 60:
            blocking_issues.append("Title exceeds 60 characters.")
            score -= 30
        rule = SubjectRuleRegistry.resolve(subject_name)
        if rule and not any(name in title_norm for name in rule.ru_names):
            blocking_issues.append("Title does not identify the resolved WB subject.")
            score -= 35
        if "/" in title or title.count(",") >= 2:
            blocking_issues.append("Title contains alternative-name or keyword-chain punctuation.")
            score -= 20
        if re.search(r"\b\d{1,2}\s*(?:лет|год|года)\b", title_norm):
            blocking_issues.append("Title contains age.")
            score -= 25

        forbidden_title_values = [
            *cls._TITLE_FORBIDDEN_WORDS,
            *cls._COMMON_COLORS,
            *cls._attribute_values(confirmed_attributes, inferred_attributes, "gender", "Пол"),
            *cls._attribute_values(confirmed_attributes, inferred_attributes, "color", "Цвет"),
            *cls._attribute_values(confirmed_attributes, inferred_attributes, "composition", "Состав", "material"),
            *cls._attribute_values(confirmed_attributes, inferred_attributes, "season", "Сезон"),
        ]
        for value in cls._dedupe(forbidden_title_values):
            if cls._contains_value(title_norm, value):
                blocking_issues.append(f'Title contains forbidden attribute value "{value}".')
                score -= 18

        description_colors = [
            *cls._COMMON_COLORS,
            *cls._attribute_values(confirmed_attributes, inferred_attributes, "color", "Цвет"),
        ]
        for value in cls._dedupe(description_colors):
            if cls._contains_value(description_norm, value):
                blocking_issues.append(f'Description contains forbidden color "{value}".')
                score -= 20
                break

        meta_markers = (
            "актуальные поисковые фразы",
            "в описании естественно раскрыты детали модели",
            "описание раскрывает материал",
            "релевантные поисковые запросы",
        )
        if any(marker in description_norm for marker in meta_markers):
            blocking_issues.append("Description contains an SEO or AI meta sentence.")
            score -= 30

        return {
            "subject_rule_score": max(0, min(100, score)),
            "blocking_issues": cls._dedupe(blocking_issues),
            "warnings": warnings,
            "valid": not blocking_issues,
        }

    @staticmethod
    def _attribute_values(
        confirmed: dict[str, Any] | None,
        inferred: dict[str, Any] | None,
        *keys: str,
    ) -> list[str]:
        values: list[str] = []
        for source in (confirmed or {}, inferred or {}):
            for key in keys:
                value = source.get(key)
                if isinstance(value, list):
                    values.extend(str(item).strip() for item in value if str(item).strip())
                elif value is not None and str(value).strip():
                    values.append(str(value).strip())
        return values

    @classmethod
    def _contains_value(cls, normalized_text: str, value: str) -> bool:
        normalized_value = cls._norm(value)
        if not normalized_value:
            return False
        return bool(re.search(rf"(?<!\w){re.escape(normalized_value)}(?!\w)", normalized_text))

    @staticmethod
    def _dedupe(values: list[str] | tuple[str, ...]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value or "").strip()
            key = text.casefold()
            if text and key not in seen:
                seen.add(key)
                result.append(text)
        return result

    @staticmethod
    def _norm(value: str | None) -> str:
        return re.sub(r"\s+", " ", str(value or "").replace("ё", "е").casefold()).strip()
