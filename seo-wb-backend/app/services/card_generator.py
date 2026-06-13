import json
import uuid
from typing import Any

from openai import OpenAI

from app.core.config import Settings
from app.core.errors import AppError
from app.schemas.card import CardUploadGroup, Dimensions, ImageAnalysis, ProductInput, SizeItem, Variant
from app.services.product_copy_policy import (
    build_seo_title,
    build_copy_policy_context,
    cleanup_description,
    cleanup_title,
    render_description,
    resolve_product_family,
)
from app.services.product_intent_parser import ProductIntent, ProductIntentParser


SYSTEM_PROMPT = (
    "Ты профессиональный SEO-копирайтер и эксперт по созданию продающих карточек товара Wildberries. "
    "Верни только валидный JSON без markdown. "
    "Формат: массив объектов {subjectID, variants}. Каждый variant содержит vendorCode, title, description, brand, dimensions, characteristics, sizes. "
    "Пиши title и description на русском языке. "
    "ПРАВИЛА ДЛЯ СОЗДАНИЯ ОПИСАНИЯ (description): "
    "- Сделай описание связным, живым и естественным текстом без сухого перечисления характеристик. "
    "- Длина описания должна быть строго в пределах от 600 до 900 символов. "
    "- Используй family_copy_policy из payload как главный ориентир для tone, focus_points, use_cases и forbidden_phrases. "
    "- Не применяй универсальные fashion-формулировки ко всем категориям: белье, домашняя одежда, аксессуары, верхняя одежда и базовая одежда требуют разного контекста. "
    "- Пиши только релевантные сценарии использования и выгоды для конкретной категории товара. "
    "ПРАВИЛА ДЛЯ ХАРАКТЕРИСТИК (characteristics): "
    "- Characteristics заполняй только из provided fillable_charcs: используй точный id, не придумывай id. "
    "- Заполняй required и popular характеристики, если значение можно уверенно вывести из image_analysis или user_input. "
    "- Для стандартных безопасных полей можно использовать типовые значения: Уход за вещами, Рисунок, Назначение, Комплектация. "
    "- Не заполняй юридические номера сертификатов/деклараций, если пользователь их не указал. "
    "- Не выдумывай brand: если бренд не указан пользователем, используй Нет бренда. "
    "ПРАВИЛА ДЛЯ ВАРИАНТОВ И РАЗМЕРОВ: "
    "- Если extracted_user_intent содержит несколько цветов, создай variant для каждого цвета. "
    "- Размеры S-42 преобразуй в techSize=S и wbSize=42. Одиночный размер S означает techSize=S и wbSize=S. "
    "- Если есть vendor_code, vendorCode должен быть base/РусскийЦвет."
)


class CardGenerator:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self._model = settings.openai_card_model

    def generate(
        self,
        user_input: ProductInput,
        analysis: ImageAnalysis,
        subject: dict[str, Any],
        charcs: list[dict[str, Any]],
        garment_json: dict[str, Any] | None = None,
        seo_keyword_plan: dict[str, Any] | None = None,
        attribute_confidence: dict[str, Any] | None = None,
    ) -> list[CardUploadGroup]:
        fallback_intent = ProductIntentParser.parse(user_input.note)
        gemini_intent = ProductIntentParser.from_analysis(analysis)
        intent = gemini_intent.merge_missing(fallback_intent)
        if self._client and self._model:
            return self._generate_with_openai(
                user_input,
                analysis,
                subject,
                charcs,
                intent,
                garment_json or {},
                seo_keyword_plan or {},
                attribute_confidence or {},
            )
        return self._generate_fallback(
            user_input,
            analysis,
            subject,
            charcs,
            intent,
            seo_keyword_plan or {},
            attribute_confidence or {},
        )

    def _generate_with_openai(
        self,
        user_input: ProductInput,
        analysis: ImageAnalysis,
        subject: dict[str, Any],
        charcs: list[dict[str, Any]],
        intent: ProductIntent,
        garment_json: dict[str, Any],
        seo_keyword_plan: dict[str, Any],
        attribute_confidence: dict[str, Any],
    ) -> list[CardUploadGroup]:
        confirmed_attributes = (attribute_confidence or {}).get("confirmed_attributes") or {}
        inferred_attributes = (attribute_confidence or {}).get("inferred_attributes") or {}
        user_payload = {
            "task": "generate_wildberries_product_card",
            "user_input": user_input.model_dump(),
            "extracted_user_intent": self._intent_payload(intent),
            "image_analysis": analysis.model_dump(),
            "garment_analysis": garment_json,
            "seo_keyword_plan": seo_keyword_plan,
            "title_formula": "[Product type] + [target audience/gender] + [main attribute] + [material/color/fit] + [quantity if set]",
            "confirmed_attributes": confirmed_attributes,
            "inferred_attributes": inferred_attributes,
            "attribute_confidence": attribute_confidence,
            "family_copy_policy": build_copy_policy_context(subject, analysis, user_input),
            "category_context": {
                "subjectID": subject["subjectID"],
                "subjectName": subject.get("subjectName"),
                "parentID": subject.get("parentID"),
                "parentName": subject.get("parentName"),
            },
            "required_charcs": [item for item in charcs if item.get("required")],
            "popular_charcs": [item for item in charcs if item.get("popular")][:20],
            "fillable_charcs": self._fillable_charcs(charcs),
        }
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, separators=(",", ":"))},
                ],
                temperature=0.2,
            )
            raw = json.loads(response.choices[0].message.content or "[]")
            raw = self._enrich_openai_output(raw, user_input, analysis, subject, intent, charcs, seo_keyword_plan, attribute_confidence)
            return [CardUploadGroup.model_validate(item) for item in raw]
        except Exception:
            return self._generate_fallback(user_input, analysis, subject, charcs, intent, seo_keyword_plan, attribute_confidence)

    @staticmethod
    def _intent_payload(intent: ProductIntent) -> dict[str, Any]:
        return {
            "colors": [{"value": color.value, "code": color.code} for color in intent.colors],
            "sizes": intent.sizes,
            "dimensions": intent.dimensions,
            "vendor_code": intent.vendor_code,
        }

    @staticmethod
    def _fillable_charcs(charcs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        blocked = {
            "Номер декларации соответствия",
            "Номер сертификата соответствия",
            "Дата регистрации сертификата/декларации",
            "Дата окончания действия сертификата/декларации",
        }
        items = []
        for item in charcs:
            name = str(item.get("name") or "")
            if name in blocked:
                continue
            if not item.get("required") and not item.get("popular"):
                continue
            items.append(
                {
                    "id": item.get("charcID"),
                    "name": name,
                    "required": bool(item.get("required")),
                    "popular": bool(item.get("popular")),
                    "maxCount": item.get("maxCount"),
                    "unitName": item.get("unitName") or "",
                }
            )
        return items[:35]

    def _enrich_openai_output(
        self,
        raw: Any,
        user_input: ProductInput,
        analysis: ImageAnalysis,
        subject: dict[str, Any],
        intent: ProductIntent,
        charcs: list[dict[str, Any]],
        seo_keyword_plan: dict[str, Any],
        attribute_confidence: dict[str, Any],
    ) -> Any:
        if not isinstance(raw, list):
            return raw
        default_category = subject.get("subjectName") or analysis.category or user_input.category or "Товар"
        for group in raw:
            if not isinstance(group, dict):
                continue
            for variant in group.get("variants", []) or []:
                if not isinstance(variant, dict):
                    continue
                variant.setdefault("vendorCode", self._vendor_base(user_input, intent))
                variant["brand"] = self._brand(user_input)
                variant.setdefault("dimensions", self._dimensions(user_input, intent))
                if not variant.get("sizes"):
                    variant["sizes"] = [size.model_dump(mode="json", exclude_none=True) for size in self._sizes(user_input, intent)]
                title_payload = build_seo_title(
                    default_category,
                    analysis.gender or user_input.gender,
                    self._title_attributes(user_input, analysis, subject, seo_keyword_plan, attribute_confidence),
                    seo_keyword_plan,
                    brand=self._brand(user_input),
                )
                variant["title"] = cleanup_title(str(title_payload.get("title") or variant.get("title") or ""), default_category, analysis, user_input)
                variant["description"] = cleanup_description(
                    str(variant.get("description") or ""),
                    title=variant["title"],
                    subject=subject,
                    analysis=analysis,
                    user_input=user_input,
                )
        self._apply_intent_to_raw(raw, user_input, intent, charcs)
        return raw

    def _generate_fallback(
        self,
        user_input: ProductInput,
        analysis: ImageAnalysis,
        subject: dict[str, Any],
        charcs: list[dict[str, Any]],
        intent: ProductIntent,
        seo_keyword_plan: dict[str, Any],
        attribute_confidence: dict[str, Any],
    ) -> list[CardUploadGroup]:
        subject_id = int(subject["subjectID"])
        default_category = subject.get("subjectName") or "Товар"
        title = self._title(user_input, analysis, subject, default_category, seo_keyword_plan, attribute_confidence)
        variant = Variant(
            vendorCode=self._vendor_base(user_input, intent),
            title=title,
            description=self._description(analysis, user_input, subject, title),
            brand=self._brand(user_input),
            dimensions=Dimensions.model_validate(self._dimensions(user_input, intent)),
            characteristics=self._characteristics(user_input, analysis, charcs),
            sizes=self._sizes(user_input, intent),
        )
        raw = [CardUploadGroup(subjectID=subject_id, variants=[variant]).model_dump(mode="json", exclude_none=True)]
        self._apply_intent_to_raw(raw, user_input, intent, charcs)
        return [CardUploadGroup.model_validate(item) for item in raw]

    @staticmethod
    def _brand(user_input: ProductInput) -> str:
        return (user_input.brand or "").strip() or "Нет бренда"

    @staticmethod
    def _title(
        user_input: ProductInput,
        analysis: ImageAnalysis,
        subject: dict[str, Any],
        default_category: str,
        seo_keyword_plan: dict[str, Any],
        attribute_confidence: dict[str, Any],
    ) -> str:
        title_payload = build_seo_title(
            default_category,
            analysis.gender or user_input.gender,
            CardGenerator._title_attributes(user_input, analysis, subject, seo_keyword_plan, attribute_confidence),
            seo_keyword_plan,
            brand=CardGenerator._brand(user_input),
        )
        title = str(title_payload.get("title") or "").strip()
        if not title:
            pieces = [analysis.product_name or user_input.category or default_category, analysis.fit_type]
            title = " ".join(str(piece).strip() for piece in pieces if piece).strip()[:60].strip()
        return cleanup_title(title, default_category, analysis, user_input)

    @staticmethod
    def _description(analysis: ImageAnalysis, user_input: ProductInput, subject: dict[str, Any], title: str) -> str:
        policy = resolve_product_family(subject, analysis, user_input)
        text = render_description(policy, title=title, analysis=analysis, user_input=user_input)
        return cleanup_description(text, title=title, subject=subject, analysis=analysis, user_input=user_input)

    @staticmethod
    def _title_attributes(
        user_input: ProductInput,
        analysis: ImageAnalysis,
        subject: dict[str, Any],
        seo_keyword_plan: dict[str, Any],
        attribute_confidence: dict[str, Any],
    ) -> dict[str, Any]:
        confirmed = (attribute_confidence or {}).get("confirmed_attributes") or {}
        inferred = (attribute_confidence or {}).get("inferred_attributes") or {}
        seo_inputs = user_input.seo_inputs if user_input else None
        return {
            "material": getattr(seo_inputs, "material", None) or confirmed.get("composition") or inferred.get("composition") or analysis.material,
            "color": getattr(seo_inputs, "color", None) or confirmed.get("color") or inferred.get("color") or analysis.color or user_input.color,
            "fit": getattr(seo_inputs, "fit", None) or confirmed.get("fit") or inferred.get("fit") or analysis.fit_type,
            "season": getattr(seo_inputs, "season", None) or confirmed.get("season") or inferred.get("season") or analysis.season,
            "quantity_in_set": getattr(seo_inputs, "quantity_in_set", None),
            "key_feature": getattr(seo_inputs, "key_feature", None),
            "subject": subject.get("subjectName"),
            "primary_keyword": seo_keyword_plan.get("primary_keyword"),
        }

    @staticmethod
    def _sizes(user_input: ProductInput, intent: ProductIntent | None = None) -> list[SizeItem]:
        if intent and intent.sizes:
            return [SizeItem(techSize=item["techSize"], wbSize=item["wbSize"], skus=[]) for item in intent.sizes[:30]]
        sizes = user_input.sizes or ["0"]
        return [SizeItem(techSize=str(size), wbSize=str(size), skus=[]) for size in sizes[:30]]

    @staticmethod
    def _dimensions(user_input: ProductInput, intent: ProductIntent | None = None) -> dict[str, Any]:
        dimensions = {**(user_input.dimensions or {}), **((intent.dimensions if intent else {}) or {})}
        return {
            "length": dimensions.get("length") or 30,
            "width": dimensions.get("width") or 25,
            "height": dimensions.get("height") or 5,
            "weightBrutto": dimensions.get("weightBrutto") or 0.5,
        }

    @staticmethod
    def _characteristics(user_input: ProductInput, analysis: ImageAnalysis, charcs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        values_by_name: dict[str, Any] = {}
        values_by_name.update({str(key): value for key, value in user_input.attributes.items() if value})
        values_by_name.update({str(key): value for key, value in analysis.attributes.items() if value})
        first_variant_color = (analysis.variant_colors or [{}])[0].get("value") if analysis.variant_colors else None
        if analysis.color or user_input.color or first_variant_color:
            values_by_name.setdefault("Цвет", analysis.color or user_input.color or first_variant_color)
        if analysis.gender or user_input.gender:
            values_by_name.setdefault("Пол", analysis.gender or user_input.gender)
        if analysis.material:
            values_by_name.setdefault("Состав", analysis.material)
        if analysis.season:
            values_by_name.setdefault("Сезон", analysis.season)
        if analysis.fit_type:
            values_by_name.setdefault("Покрой", analysis.fit_type)

        characteristics = []
        seen_ids = set()
        for charc in charcs:
            charc_id = charc.get("charcID")
            name = charc.get("name")
            if not charc_id or not name or charc_id in seen_ids:
                continue
            value = values_by_name.get(name)
            if not value and charc.get("required"):
                value = CardGenerator._fallback_required_value(name, analysis, user_input)
            if value:
                characteristics.append({"id": int(charc_id), "value": CardGenerator._normalize_value(value)})
                seen_ids.add(charc_id)
        if not characteristics:
            raise AppError("no_characteristics", "Could not map characteristics for this subject.", 422)
        return characteristics

    @staticmethod
    def _fallback_required_value(name: str, analysis: ImageAnalysis, user_input: ProductInput) -> str | None:
        lower = name.casefold()
        if "цвет" in lower:
            return analysis.color or user_input.color
        if "пол" in lower:
            return analysis.gender or user_input.gender
        if "состав" in lower:
            return analysis.material
        if "бренд" in lower:
            return user_input.brand
        return None

    @staticmethod
    def _normalize_value(value: Any) -> Any:
        if isinstance(value, list):
            return value
        if isinstance(value, (int, float)):
            return value
        text = str(value).strip()
        if ";" in text:
            return [part.strip() for part in text.split(";") if part.strip()]
        return [text]

    @classmethod
    def _apply_intent_to_raw(
        cls,
        raw: list[dict[str, Any]],
        user_input: ProductInput,
        intent: ProductIntent,
        charcs: list[dict[str, Any]],
    ) -> None:
        if not raw:
            return
        color_charc_id = cls._find_charc_id(charcs, ["Цвет", "color"])
        sizes = [size.model_dump(mode="json", exclude_none=True) for size in cls._sizes(user_input, intent)]
        dimensions = cls._dimensions(user_input, intent)
        vendor_base = cls._vendor_base(user_input, intent)

        for group in raw:
            variants = group.get("variants") or []
            if not variants:
                continue
            if intent.colors:
                template = variants[0]
                expanded = []
                for color in intent.colors:
                    variant = json.loads(json.dumps(template, ensure_ascii=False))
                    color_suffix = ProductIntentParser.display_value_from_color(color.value)
                    variant["vendorCode"] = f"{vendor_base}/{color_suffix}"
                    variant["brand"] = cls._brand(user_input)
                    variant["sizes"] = sizes
                    variant["dimensions"] = dimensions
                    if color_charc_id:
                        cls._upsert_characteristic(variant, color_charc_id, [color.value])
                    expanded.append(variant)
                group["variants"] = expanded
            else:
                for index, variant in enumerate(variants, 1):
                    if variant.get("vendorCode") in {None, "", "CHANGE-ME"}:
                        variant["vendorCode"] = f"{vendor_base}/{index}" if len(variants) > 1 else vendor_base
                    variant["brand"] = cls._brand(user_input)
                    variant["sizes"] = sizes
                    variant["dimensions"] = dimensions
            cls._ensure_unique_vendor_codes(group.get("variants") or [])

    @staticmethod
    def _find_charc_id(charcs: list[dict[str, Any]], names: list[str]) -> int | None:
        normalized = {name.casefold() for name in names}
        for charc in charcs:
            if str(charc.get("name") or "").casefold() in normalized and charc.get("charcID"):
                return int(charc["charcID"])
        return None

    @staticmethod
    def _vendor_base(user_input: ProductInput, intent: ProductIntent) -> str:
        base = (intent.vendor_code or user_input.vendor_code or "").strip()
        if base and base != "CHANGE-ME":
            return base
        return f"AUTO-{uuid.uuid4().hex[:8].upper()}"

    @staticmethod
    def _upsert_characteristic(variant: dict[str, Any], charc_id: int, value: Any) -> None:
        characteristics = variant.setdefault("characteristics", [])
        for item in characteristics:
            if isinstance(item, dict) and int(item.get("id") or 0) == charc_id:
                item["value"] = value
                return
        characteristics.append({"id": charc_id, "value": value})

    @staticmethod
    def _ensure_unique_vendor_codes(variants: list[dict[str, Any]]) -> None:
        seen: dict[str, int] = {}
        for variant in variants:
            base = str(variant.get("vendorCode") or "AUTO").strip() or "AUTO"
            key = base.casefold()
            count = seen.get(key, 0)
            if count:
                variant["vendorCode"] = f"{base}-{count + 1}"
            seen[key] = count + 1
