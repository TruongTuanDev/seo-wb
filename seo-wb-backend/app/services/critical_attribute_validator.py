from typing import Any


class CriticalAttributeValidator:
    _REQUIRED_BY_SUBJECT = [
        {
            "match": ("джинс", "jeans"),
            "required": ["Модель джинсов", "Тип посадки", "Вид застежки"],
            "aliases": {
                "Модель джинсов": ("pants_model", "Покрой", "Модель брюк"),
                "Тип посадки": ("fit", "Тип посадки"),
                "Вид застежки": ("closure", "Вид застежки"),
            },
        },
        {
            "match": ("плать", "dress"),
            "required": ["Длина изделия", "Фасон", "Сезон"],
            "aliases": {
                "Длина изделия": ("length", "Длина изделия"),
                "Фасон": ("fit", "Фасон"),
                "Сезон": ("season", "Сезон"),
            },
        },
        {
            "match": ("трус", "panties", "slip"),
            "required": ["Состав", "Тип модели", "Количество в наборе"],
            "aliases": {
                "Состав": ("composition", "Состав"),
                "Тип модели": ("model", "underwear_features"),
                "Количество в наборе": ("quantity_in_set", "quantity", "contents"),
            },
        },
    ]

    @classmethod
    def validate(
        cls,
        *,
        subject_name: str | None,
        confirmed_attributes: dict[str, Any] | None,
        inferred_attributes: dict[str, Any] | None,
    ) -> dict[str, Any]:
        rule = cls._rule(subject_name)
        if not rule:
            return {"missing_critical_attributes": [], "critical_score": 100}

        missing: list[str] = []
        for required_name in rule["required"]:
            aliases = rule["aliases"].get(required_name, ())
            if not cls._has_any(confirmed_attributes, inferred_attributes, aliases):
                missing.append(required_name)
        score = max(0, 100 - len(missing) * 20)
        return {
            "missing_critical_attributes": missing,
            "critical_score": score,
        }

    @classmethod
    def _rule(cls, subject_name: str | None) -> dict[str, Any] | None:
        source = str(subject_name or "").casefold()
        for rule in cls._REQUIRED_BY_SUBJECT:
            if any(token in source for token in rule["match"]):
                return rule
        return None

    @staticmethod
    def _has_any(confirmed: dict[str, Any] | None, inferred: dict[str, Any] | None, aliases: tuple[str, ...]) -> bool:
        for source in (confirmed or {}, inferred or {}):
            for alias in aliases:
                value = source.get(alias)
                if value is not None and str(value).strip():
                    return True
        return False
