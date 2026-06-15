from __future__ import annotations

from typing import Any

from app.services.subject_rule_registry import SubjectRuleRegistry


class CriticalAttributeValidator:
    _ALIASES = {
        "Модель джинсов": ("pants_model", "model", "Покрой", "Модель брюк"),
        "Тип посадки": ("fit", "Тип посадки", "Посадка"),
        "Вид застежки": ("closure", "Вид застежки", "Тип застежки"),
        "Декоративные элементы": ("decor", "detail", "Декоративные элементы"),
        "Состав": ("composition", "Состав", "material"),
        "Модель брюк": ("pants_model", "model", "Модель брюк", "Покрой"),
        "Длина изделия": ("length", "Длина изделия"),
        "Фасон": ("fit", "Фасон", "style"),
        "Вырез горловины": ("neckline", "Вырез горловины"),
        "Сезон": ("season", "Сезон"),
        "Тип рукава": ("sleeve_type", "Тип рукава"),
        "Покрой": ("fit", "Покрой", "model"),
        "Тип бюстгальтера": ("bra_type", "type", "Тип бюстгальтера"),
        "Наличие косточек": ("wire_state", "support", "Наличие косточек"),
        "Размер чашки": ("cup_size", "Размер чашки"),
        "Тип трусов": ("panties_type", "type", "Тип трусов"),
        "Количество в наборе": ("quantity_in_set", "quantity", "Количество в наборе", "contents"),
        "Посадка": ("fit", "Посадка", "Тип посадки"),
        "Комплектация": ("contents", "Комплектация"),
        "Назначение": ("purpose", "Назначение"),
        "Тип карманов": ("pocket_type", "Тип карманов"),
    }

    @classmethod
    def validate(
        cls,
        *,
        subject_name: str | None,
        confirmed_attributes: dict[str, Any] | None,
        inferred_attributes: dict[str, Any] | None,
        wb_characteristics: list[dict[str, Any]] | None = None,
        low_confidence_attributes: list[str] | None = None,
    ) -> dict[str, Any]:
        rule = SubjectRuleRegistry.resolve(subject_name)
        if not rule:
            return {
                "missing_critical_attributes": [],
                "low_confidence_critical_attributes": [],
                "critical_score": 100,
                "subject_rule_applied": False,
            }

        available_names = {str(item.get("name") or "").strip() for item in (wb_characteristics or []) if str(item.get("name") or "").strip()}
        rule_required_names = [
            name
            for name in rule.critical_attributes
            if not available_names or name in available_names or any(alias in available_names for alias in cls._ALIASES.get(name, ()))
        ]
        live_required_names = [
            str(item.get("name") or "").strip()
            for item in (wb_characteristics or [])
            if item.get("required") and str(item.get("name") or "").strip()
        ]
        required_names = list(dict.fromkeys([*rule_required_names, *live_required_names]))
        missing: list[str] = []
        low_confidence_hits: list[str] = []
        low_confidence_keys = {str(item).strip() for item in (low_confidence_attributes or []) if str(item).strip()}
        for required_name in required_names:
            aliases = cls._ALIASES.get(required_name, (required_name,))
            if not cls._has_any(confirmed_attributes, inferred_attributes, aliases):
                missing.append(required_name)
                continue
            if any(alias in low_confidence_keys for alias in aliases):
                low_confidence_hits.append(required_name)
        score = max(0, 100 - len(missing) * 15 - len(low_confidence_hits) * 8)
        return {
            "missing_critical_attributes": missing,
            "low_confidence_critical_attributes": low_confidence_hits,
            "critical_score": score,
            "subject_rule_applied": True,
        }

    @staticmethod
    def _has_any(confirmed: dict[str, Any] | None, inferred: dict[str, Any] | None, aliases: tuple[str, ...]) -> bool:
        for source in (confirmed or {}, inferred or {}):
            for alias in aliases:
                value = source.get(alias)
                if value is not None and str(value).strip():
                    return True
        return False
