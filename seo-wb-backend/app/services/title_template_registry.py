import re
from typing import Any

from app.services.subject_rule_registry import SubjectRuleRegistry


class TitleTemplateRegistry:
    @classmethod
    def preferred_pattern(cls, subject_name: str | None) -> list[str]:
        rule = SubjectRuleRegistry.resolve(subject_name)
        if rule and rule.title_patterns:
            return list(rule.title_patterns[0])
        return ["subject", "main_attribute", "fit", "detail"]

    @classmethod
    def build_title(
        cls,
        *,
        subject_name: str | None,
        attributes: dict[str, Any] | None,
        include_gender_in_title: bool = False,
        gender: str | None = None,
    ) -> str:
        attrs = attributes or {}
        rule = SubjectRuleRegistry.resolve(subject_name)
        pattern = list(rule.title_patterns[0]) if rule and rule.title_patterns else cls.preferred_pattern(subject_name)
        slots = {
            "subject": cls._clean(subject_name),
            # Marketplace rule: gender belongs in attributes, not in the title.
            "gender": None,
            "main_attribute": cls._first(attrs, "main_attribute", "model", "construction", "feature", "purpose"),
            "fit": cls._first(attrs, "fit", "silhouette"),
            "secondary_attribute": cls._first(attrs, "secondary_attribute", "decor", "detail"),
            "material": None,
            "color": None,
            "material_or_color": None,
            "rise": cls._first(attrs, "rise"),
            "rise_phrase": cls._rise_phrase(cls._first(attrs, "rise")),
            "decor": cls._first(attrs, "decor", "pattern", "detail"),
            "detail": cls._first(attrs, "detail", "decor", "feature", "pattern"),
            "length": cls._first(attrs, "length"),
            "length_sentence": cls._length_sentence(cls._first(attrs, "length")),
            "occasion": cls._first(attrs, "occasion", "purpose"),
            "season": None,
            "season_or_use": cls._first(attrs, "purpose", "occasion"),
            "construction": cls._first(attrs, "construction", "feature"),
            "support": cls._first(attrs, "support", "model"),
            "model": cls._first(attrs, "model"),
            "style": cls._first(attrs, "style", "fit", "model"),
            "silhouette": cls._first(attrs, "silhouette", "fit", "model"),
            "fit_or_material": cls._first(attrs, "fit"),
            "material_or_detail": cls._first(attrs, "detail", "decor"),
            "hood_phrase": "с капюшоном",
            "set_quantity": cls._set_quantity(attrs),
            "hood_feature": cls._first(attrs, "hood_feature", "feature", "fit"),
            "bra_type": cls._first(attrs, "bra_type", "type", "model"),
            "wire_state": cls._wire_state(cls._first(attrs, "wire_state", "support", "construction")),
            "effect": cls._first(attrs, "effect", "feature"),
            "panties_type": cls._first(attrs, "panties_type", "type", "model"),
            "purpose": cls._first(attrs, "purpose"),
        }
        parts: list[str] = []
        for key in pattern:
            value = slots.get(key)
            if value and (not parts or parts[-1].casefold() != value.casefold()):
                parts.append(value)
        title = cls._normalize_spaces(" ".join(parts))
        return title.strip(",.-/ ")

    @staticmethod
    def _wire_state(value: str | None) -> str | None:
        source = TitleTemplateRegistry._norm(value)
        if not source:
            return None
        if any(token in source for token in ("без", "no", "none")):
            return "без косточек"
        if any(token in source for token in ("кост", "wire", "push")):
            return "на косточках"
        return TitleTemplateRegistry._clean(value)

    @staticmethod
    def _length_sentence(value: str | None) -> str | None:
        text = TitleTemplateRegistry._clean(value)
        if not text:
            return None
        return text

    @staticmethod
    def _set_quantity(attributes: dict[str, Any]) -> str | None:
        raw = TitleTemplateRegistry._first(attributes, "quantity_in_set", "quantity")
        if not raw:
            return None
        text = TitleTemplateRegistry._clean(raw)
        return f"набор {text}" if re.search(r"\d", text) else text

    @staticmethod
    def _first(attributes: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = attributes.get(key)
            if value is None:
                continue
            text = TitleTemplateRegistry._clean(value)
            if text:
                return text
        return None

    @staticmethod
    def _clean(value: Any) -> str | None:
        text = TitleTemplateRegistry._normalize_spaces(str(value or ""))
        return text or None

    @staticmethod
    def _gender_value(gender: str | None) -> str | None:
        source = TitleTemplateRegistry._norm(gender)
        if not source:
            return None
        if "жен" in source:
            return "женские"
        if "муж" in source:
            return "мужские"
        if "дев" in source:
            return "для девочек"
        if "мал" in source:
            return "для мальчиков"
        return TitleTemplateRegistry._clean(gender)

    @staticmethod
    def _rise_phrase(value: str | None) -> str | None:
        source = TitleTemplateRegistry._norm(value)
        if not source:
            return None
        if "высок" in source:
            return "с высокой посадкой"
        if "сред" in source:
            return "со средней посадкой"
        if "низк" in source:
            return "с низкой посадкой"
        return TitleTemplateRegistry._clean(value)

    @staticmethod
    def _normalize_spaces(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _norm(value: str | None) -> str:
        return TitleTemplateRegistry._normalize_spaces(str(value or "")).casefold()
