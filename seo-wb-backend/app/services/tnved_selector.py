from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from app.schemas.card import ImageAnalysis, ProductInput


_TOKEN_RE = re.compile(r"[^\wа-яА-Я]+", re.UNICODE)


@dataclass(slots=True)
class TnvedSelectionHint:
    subject_id: int
    subject_name: str | None = None
    category: str | None = None
    gender: str | None = None
    material: str | None = None
    search: str | None = None
    source_text: str = ""
    family: str | None = None
    audience: str | None = None
    knit_state: str | None = None
    material_family: str | None = None
    reasons: list[str] = field(default_factory=list)


class FashionTnvedSelector:
    @classmethod
    def build_hint(
        cls,
        *,
        subject_id: int,
        subject_name: str | None = None,
        search: str | None = None,
        user_input: ProductInput | None = None,
        analysis: ImageAnalysis | None = None,
        payload: Any | None = None,
        category: str | None = None,
        gender: str | None = None,
        material: str | None = None,
    ) -> TnvedSelectionHint:
        payload_bits = cls._payload_bits(payload)
        source_parts = [
            subject_name,
            category,
            user_input.category if user_input else None,
            analysis.category if analysis else None,
            search,
            payload_bits.get("title"),
            payload_bits.get("description"),
            payload_bits.get("category"),
            gender,
            user_input.gender if user_input else None,
            analysis.gender if analysis else None,
            payload_bits.get("gender"),
            material,
            user_input.attributes.get("Состав") if user_input else None,
            analysis.material if analysis else None,
            payload_bits.get("material"),
        ]
        source_text = " ".join(str(part).strip() for part in source_parts if part).strip()
        family = cls._infer_family(source_text)
        audience = cls._infer_audience(source_text)
        knit_state = cls._infer_knit_state(source_text)
        material_family = cls._infer_material_family(source_text)
        reasons = [
            f"family={family}" if family else None,
            f"audience={audience}" if audience else None,
            f"knit={knit_state}" if knit_state else None,
            f"material_family={material_family}" if material_family else None,
        ]
        return TnvedSelectionHint(
            subject_id=subject_id,
            subject_name=subject_name,
            category=category or (analysis.category if analysis else None) or (user_input.category if user_input else None),
            gender=gender or (analysis.gender if analysis else None) or (user_input.gender if user_input else None),
            material=material or (analysis.material if analysis else None),
            search=search,
            source_text=source_text,
            family=family,
            audience=audience,
            knit_state=knit_state,
            material_family=material_family,
            reasons=[reason for reason in reasons if reason],
        )

    @classmethod
    def select_best(cls, items: list[dict[str, Any]], hint: TnvedSelectionHint) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        if not items:
            return None, []
        scored: list[dict[str, Any]] = []
        for item in items:
            score, reasons = cls._score_item(item, hint)
            enriched = dict(item)
            enriched["score"] = round(score, 3)
            enriched["scoreReasons"] = reasons
            scored.append(enriched)
        scored.sort(
            key=lambda item: (
                float(item.get("score") or 0.0),
                len(str(item.get("name") or item.get("description") or "")),
            ),
            reverse=True,
        )
        return scored[0], scored

    @classmethod
    def _score_item(cls, item: dict[str, Any], hint: TnvedSelectionHint) -> tuple[float, list[str]]:
        text = cls._item_text(item)
        tokens = set(cls._tokens(text))
        score = 0.0
        reasons: list[str] = []
        tnved_code = str(item.get("tnved") or item.get("code") or "")
        expected_prefixes = cls._expected_prefixes(hint)
        if expected_prefixes:
            if any(tnved_code.startswith(prefix) for prefix in expected_prefixes):
                score += 4.0
                reasons.append(f"tnved_prefix_match={tnved_code}")
            else:
                score -= 1.0
                reasons.append("tnved_prefix_mismatch")

        family_terms = cls._family_terms(hint.family)
        if family_terms and any(term in text for term in family_terms):
            score += 2.4
            reasons.append(f"family_match={hint.family}")

        audience_terms = cls._audience_terms(hint.audience)
        if audience_terms and any(term in text for term in audience_terms):
            score += 1.8
            reasons.append(f"audience_match={hint.audience}")

        if hint.knit_state == "knit":
            if "трикотаж" in text or "вязан" in text:
                score += 1.6
                reasons.append("knit_match")
            if "не трикотаж" in text:
                score -= 1.4
                reasons.append("knit_conflict")
        elif hint.knit_state == "woven":
            if "не трикотаж" in text:
                score += 1.6
                reasons.append("woven_match")
            if "трикотаж" in text or "вязан" in text:
                score -= 1.4
                reasons.append("woven_conflict")

        material_terms = cls._material_terms(hint.material_family)
        if material_terms and any(term in text for term in material_terms):
            score += 1.5
            reasons.append(f"material_match={hint.material_family}")

        source_tokens = set(cls._tokens(hint.source_text))
        overlap = source_tokens & tokens
        if overlap:
            overlap_score = min(1.5, 0.25 * len(overlap))
            score += overlap_score
            reasons.append(f"token_overlap={','.join(sorted(list(overlap))[:6])}")

        return score, reasons

    @classmethod
    def _expected_prefixes(cls, hint: TnvedSelectionHint) -> list[str]:
        audience = hint.audience
        knit = hint.knit_state
        family = hint.family
        if not audience or not knit or not family:
            return []
        if family in {"pants", "jeans", "shorts", "skirt", "dress"}:
            if audience in {"female", "girls"}:
                return ["6104"] if knit == "knit" else ["6204"]
            if audience in {"male", "boys"}:
                return ["6103"] if knit == "knit" else ["6203"]
        if family in {"shirt", "blouse"}:
            if audience in {"female", "girls"}:
                return ["6106"] if knit == "knit" else ["6206"]
            if audience in {"male", "boys"}:
                return ["6105"] if knit == "knit" else ["6205"]
        if family in {"jacket", "coat"}:
            if audience in {"female", "girls"}:
                return ["6102"] if knit == "knit" else ["6202"]
            if audience in {"male", "boys"}:
                return ["6101"] if knit == "knit" else ["6201"]
        return []

    @staticmethod
    def _family_terms(family: str | None) -> tuple[str, ...]:
        mapping = {
            "pants": ("брюк", "брюки", "trousers", "pants"),
            "jeans": ("джинс", "jeans", "denim"),
            "shorts": ("шорт", "shorts"),
            "skirt": ("юбк", "skirt"),
            "dress": ("плать", "dress"),
            "shirt": ("рубаш", "shirt", "сорочк"),
            "blouse": ("блуз", "blouse"),
            "jacket": ("куртк", "жакет", "jacket"),
            "coat": ("пальт", "coat"),
        }
        return mapping.get(family or "", ())

    @staticmethod
    def _audience_terms(audience: str | None) -> tuple[str, ...]:
        mapping = {
            "female": ("женск", "жен", "women", "female"),
            "male": ("мужск", "муж", "men", "male"),
            "girls": ("девоч", "girls"),
            "boys": ("мальчик", "boys"),
            "unisex": ("unisex",),
        }
        return mapping.get(audience or "", ())

    @staticmethod
    def _material_terms(material_family: str | None) -> tuple[str, ...]:
        mapping = {
            "cotton": ("хлоп", "cotton"),
            "synthetic": ("синтет", "полиэстер", "polyester", "synthetic", "chemical", "химическ"),
            "wool": ("шерст", "wool"),
            "flax": ("лен", "flax", "linen"),
            "silk": ("шелк", "silk"),
            "leather": ("кожа", "leather"),
        }
        return mapping.get(material_family or "", ())

    @classmethod
    def _infer_family(cls, value: str) -> str | None:
        text = cls._normalize(value)
        if any(token in text for token in ("джинс", "jeans", "denim")):
            return "jeans"
        if any(token in text for token in ("брюк", "брюки", "trousers", "pants")):
            return "pants"
        if any(token in text for token in ("шорт", "shorts")):
            return "shorts"
        if any(token in text for token in ("юбк", "skirt")):
            return "skirt"
        if any(token in text for token in ("плать", "dress")):
            return "dress"
        if any(token in text for token in ("блуз", "blouse")):
            return "blouse"
        if any(token in text for token in ("рубаш", "shirt", "сорочк")):
            return "shirt"
        if any(token in text for token in ("куртк", "жакет", "jacket")):
            return "jacket"
        if any(token in text for token in ("пальт", "coat")):
            return "coat"
        return None

    @classmethod
    def _infer_audience(cls, value: str) -> str | None:
        text = cls._normalize(value)
        if any(token in text for token in ("девоч", "girls")):
            return "girls"
        if any(token in text for token in ("мальч", "boys")):
            return "boys"
        if any(token in text for token in ("женск", "жен", "women", "female")):
            return "female"
        if any(token in text for token in ("мужск", "men", "male", "boy")):
            return "male"
        if "unisex" in text:
            return "unisex"
        return None

    @classmethod
    def _infer_knit_state(cls, value: str) -> str | None:
        text = cls._normalize(value)
        if any(token in text for token in ("трикот", "вязан", "jersey", "knit")):
            return "knit"
        if any(token in text for token in ("деним", "джинс", "лен", "linen", "woven", "ткан", "костюм", "сороч")):
            return "woven"
        return None

    @classmethod
    def _infer_material_family(cls, value: str) -> str | None:
        text = cls._normalize(value)
        if any(token in text for token in ("хлоп", "cotton")):
            return "cotton"
        if any(token in text for token in ("полиэстер", "синтет", "synthetic", "polyester", "viscose", "вискоз")):
            return "synthetic"
        if any(token in text for token in ("шерст", "wool")):
            return "wool"
        if any(token in text for token in ("лен", "linen", "flax")):
            return "flax"
        if any(token in text for token in ("шелк", "silk")):
            return "silk"
        if any(token in text for token in ("кожа", "leather")):
            return "leather"
        return None

    @classmethod
    def _payload_bits(cls, payload: Any) -> dict[str, str]:
        variant = None
        if isinstance(payload, dict):
            variants = payload.get("variants") or payload.get("cardsToAdd") or []
            if isinstance(variants, list) and variants:
                variant = variants[0]
        elif isinstance(payload, list) and payload:
            first_group = payload[0] if isinstance(payload[0], dict) else None
            if first_group:
                variants = first_group.get("variants") or []
                if isinstance(variants, list) and variants:
                    variant = variants[0]
        if not isinstance(variant, dict):
            return {}
        return {
            "title": str(variant.get("title") or ""),
            "description": str(variant.get("description") or ""),
            "category": str(variant.get("subjectName") or ""),
            "gender": cls._extract_characteristic_text(variant, ("пол",)),
            "material": cls._extract_characteristic_text(variant, ("состав", "материал")),
        }

    @staticmethod
    def _extract_characteristic_text(variant: dict[str, Any], keys: tuple[str, ...]) -> str:
        values: list[str] = []
        for item in variant.get("characteristics") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").casefold()
            if not any(key in name for key in keys):
                continue
            raw = item.get("value")
            if isinstance(raw, list):
                values.extend(str(value) for value in raw if str(value).strip())
            elif raw:
                values.append(str(raw))
        return " ".join(values)

    @classmethod
    def _item_text(cls, item: dict[str, Any]) -> str:
        bits = []
        for key in ("tnved", "code", "name", "description", "title"):
            value = item.get(key)
            if value:
                bits.append(str(value))
        if not bits:
            bits.append(str(item))
        return cls._normalize(" ".join(bits))

    @classmethod
    def _normalize(cls, value: str) -> str:
        normalized = value.casefold().replace("ё", "е")
        normalized = _TOKEN_RE.sub(" ", normalized)
        return " ".join(normalized.split())

    @classmethod
    def _tokens(cls, value: str) -> list[str]:
        return [token for token in cls._normalize(value).split() if len(token) > 1]
