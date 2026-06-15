from __future__ import annotations

import re
from typing import Any

from app.services.subject_rule_registry import SubjectRuleRegistry


class SemanticConsistencyValidator:
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
        rule = SubjectRuleRegistry.resolve(subject_name)
        haystack = cls._norm(" ".join([subject_name or "", title, description]))
        conflicts: list[str] = []

        if rule:
            for conflict_term in rule.semantic_conflicts.get("cross_subject", ()):
                if cls._is_conflicting_category_use(title, description, conflict_term):
                    conflicts.append(f'Generated text mentions conflicting category "{conflict_term}".')

        material = cls._attr(confirmed_attributes, inferred_attributes, "composition", "Состав", "material")
        if material:
            material_norm = cls._norm(material)
            if "лен" in material_norm and any(token in haystack for token in ("деним", "джинс")):
                conflicts.append('Material conflict: linen product mentions denim or jeans semantics.')
            if "деним" in material_norm and "лен" in haystack:
                conflicts.append('Material conflict: denim product mentions linen semantics.')

        color = cls._attr(confirmed_attributes, inferred_attributes, "color", "Цвет")
        if color:
            color_norm = cls._norm(color)
            if color_norm and color_norm in cls._norm(description):
                conflicts.append(f'Description contains forbidden color "{color}".')
            if "беж" in color_norm and "голуб" in haystack:
                conflicts.append('Color conflict: beige product mentions blue.')
            if "голуб" in color_norm and "беж" in haystack:
                conflicts.append('Color conflict: blue product mentions beige.')

        fit = cls._attr(confirmed_attributes, inferred_attributes, "fit", "Тип посадки", "Покрой")
        if fit:
            fit_norm = cls._norm(fit)
            if "шир" in fit_norm and "скинни" in haystack:
                conflicts.append('Fit conflict: wide fit product mentions skinny fit.')
            if "скинни" in fit_norm and "широк" in haystack:
                conflicts.append('Fit conflict: skinny fit product mentions wide fit.')

        rise = cls._attr(confirmed_attributes, inferred_attributes, "rise", "Тип посадки", "Посадка")
        if rise:
            rise_norm = cls._norm(rise)
            if "высок" in rise_norm and "низк" in haystack:
                conflicts.append('Rise conflict: high-rise product mentions low rise.')
            if "низк" in rise_norm and "высок" in haystack:
                conflicts.append('Rise conflict: low-rise product mentions high rise.')

        semantic_score = max(0, 100 - len(conflicts) * 25)
        status = "pass" if not conflicts else "warning" if semantic_score >= 50 else "fail"
        return {"semantic_score": semantic_score, "conflicts": conflicts, "status": status}

    @classmethod
    def _is_conflicting_category_use(cls, title: str, description: str, conflict_term: str) -> bool:
        if conflict_term in cls._norm(title):
            return True
        for sentence in re.split(r"[.!?]+", description):
            normalized = cls._norm(sentence)
            if conflict_term not in normalized:
                continue
            if any(marker in normalized for marker in ("сочетается с", "сочетаются с", "комбинируется с", "носить с")):
                continue
            return True
        return False

    @staticmethod
    def _attr(confirmed: dict[str, Any] | None, inferred: dict[str, Any] | None, *keys: str) -> str | None:
        for source in (confirmed or {}, inferred or {}):
            for key in keys:
                value = source.get(key)
                if isinstance(value, list):
                    text = ", ".join(str(item).strip() for item in value if str(item).strip())
                    if text:
                        return text
                if value is not None and str(value).strip():
                    return str(value).strip()
        return None

    @staticmethod
    def _norm(value: str | None) -> str:
        return re.sub(r"\s+", " ", str(value or "").replace("ё", "е").casefold()).strip()
