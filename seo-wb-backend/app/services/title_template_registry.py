import re
from typing import Any


class TitleTemplateRegistry:
    _SUBJECT_RULES = [
        {
            "match": ("джинс", "jeans"),
            "pattern": ["subject", "gender", "model", "rise_phrase", "decor"],
            "force_gender": True,
        },
        {
            "match": ("плать", "dress"),
            "pattern": ["subject", "length", "occasion"],
        },
        {
            "match": ("бюстгальтер", "bra"),
            "pattern": ["subject", "construction", "support"],
        },
        {
            "match": ("трус", "panties", "slip"),
            "pattern": ["subject", "model", "material", "set_quantity"],
        },
        {
            "match": ("худи", "hoodie"),
            "pattern": ["subject", "fit", "hood_feature"],
        },
        {
            "match": ("футбол", "t-shirt", "tshirt"),
            "pattern": ["subject", "fit", "material"],
        },
    ]

    @classmethod
    def preferred_pattern(cls, subject_name: str | None) -> list[str]:
        source = cls._norm(subject_name)
        for rule in cls._SUBJECT_RULES:
            if any(token in source for token in rule["match"]):
                return list(rule["pattern"])
        return ["subject", "main_attribute", "fit", "secondary_attribute"]

    @classmethod
    def _rule(cls, subject_name: str | None) -> dict[str, Any] | None:
        source = cls._norm(subject_name)
        for rule in cls._SUBJECT_RULES:
            if any(token in source for token in rule["match"]):
                return rule
        return None

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
        rule = cls._rule(subject_name) or {}
        pattern = list(rule.get("pattern") or cls.preferred_pattern(subject_name))
        slots = {
            "subject": cls._clean(subject_name),
            "gender": cls._gender_value(gender),
            "main_attribute": cls._first(attrs, "main_attribute", "model", "construction", "feature", "purpose"),
            "fit": cls._first(attrs, "fit", "silhouette"),
            "secondary_attribute": cls._first(attrs, "secondary_attribute", "material", "color", "season", "decor"),
            "material": cls._first(attrs, "material"),
            "color": cls._first(attrs, "color"),
            "rise": cls._first(attrs, "rise"),
            "rise_phrase": cls._rise_phrase(cls._first(attrs, "rise")),
            "decor": cls._first(attrs, "decor", "pattern"),
            "length": cls._first(attrs, "length"),
            "occasion": cls._first(attrs, "occasion", "purpose"),
            "construction": cls._first(attrs, "construction", "feature"),
            "support": cls._first(attrs, "support", "model"),
            "model": cls._first(attrs, "model"),
            "set_quantity": cls._set_quantity(attrs),
            "hood_feature": cls._first(attrs, "hood_feature", "feature", "fit"),
        }
        parts: list[str] = []
        for key in pattern:
            value = slots.get(key)
            if value:
                if not parts or parts[-1].casefold() != value.casefold():
                    parts.append(value)
        if (include_gender_in_title or bool(rule.get("force_gender"))) and slots.get("gender") and "gender" not in pattern:
            parts.insert(1, slots["gender"])
        title = cls._normalize_spaces(" ".join(parts))
        return title.strip(",.-/ ")

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
