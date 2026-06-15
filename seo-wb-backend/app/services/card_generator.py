import json
import uuid
from typing import Any

from openai import OpenAI

from app.core.config import Settings
from app.core.errors import AppError
from app.schemas.card import CardUploadGroup, Dimensions, ImageAnalysis, ProductInput, SizeItem, Variant
from app.services.product_description_builder import (
    build_description_prompt_context,
    build_product_description,
    finalize_product_description,
)
from app.services.product_intent_parser import ProductIntent, ProductIntentParser
from app.services.product_title_builder import build_product_title, select_best_ai_title


SYSTEM_PROMPT = (
    "Ты профессиональный SEO-копирайтер и эксперт по созданию продающих карточек товара Wildberries. "
    "Верни только валидный JSON без markdown. "
    "Формат: массив объектов {subjectID, variants}. Каждый variant содержит vendorCode, title, description, brand, dimensions, characteristics, sizes. "
    "Пиши title и description на русском языке. "
    "ПРАВИЛА ДЛЯ СОЗДАНИЯ ОПИСАНИЯ (description): "
    "- Сделай описание структурированным, продающим и привлекательным. "
    "- Обязательно используй следующую структуру: "
    "  1. Вовлекающее введение, описывающее стиль и ценность товара (2-3 предложения). "
    "  2. Список ключевых преимуществ и особенностей товара (используй аккуратные эмодзи для списков). "
    "  3. Идеи для образов: с чем носить, для каких случаев подходит (работа, прогулка, праздник). "
    "  4. Рекомендации по уходу или выбору размера. "
    "- Органично интегрируй популярные поисковые запросы (SEO), соответствующие категории товара, избегая спама. "
    "- Текст должен быть легким для чтения, без сплошных длинных абзацев. "
    "ПРАВИЛА ДЛЯ ХАРАКТЕРИСТИК (characteristics): "
    "- Characteristics заполняй только из provided fillable_charcs: используй точный id, не придумывай id. "
    "- Заполняй required и popular характеристики, если значение можно уверенно вывести из image_analysis или user_input. "
    "- Для стандартных безопасных полей можно использовать типовые значения: Уход за вещами, Рисунок, Назначение, Комплектация. "
    "- Не заполняй юридические номера сертификатов/деклараций, если пользователь их не указал. "
    "- Не выдумывай brand: если бренд не указан пользователем, используй Нет бренда. "
    "ПРАВИЛА ДЛЯ ВАРИАНТОВ И РАЗМЕРОВ: "
    "- Если extracted_user_intent содержит несколько цветов, создай variant для каждого цвета. "
    "- Размеры S-42 преобразуй в techSize=S и wbSize=42. Одиночный размер S означает techSize=S и wbSize=S. "
    "- Если есть vendor_code, vendorCode должен быть base/colorCode."
)

TITLE_GENERATION_PROMPT = """
TITLE GENERATION RULES FOR ALL FASHION SUBJECTS:
- Each variant must return titleCandidates: an array of 3 to 5 distinct Russian title options.
- Write each option as natural Russian, not as concatenated attribute tokens.
- Start every option with the exact resolved WB subjectName from category_context.
- Adapt grammar and structure to the actual subject: tops, bottoms, dresses, skirts, outerwear, underwear, sets, sleepwear, and accessories require different wording.
- Use only facts supported by image_analysis, user_input, and provided characteristics.
- Prioritize product model, silhouette, length, construction, sleeve/neckline/closure, and one distinctive detail when relevant.
- Never include gender, audience, age, color, brand, season, composition, or material.
- Never add synonyms, keyword chains, unsupported claims, or duplicated meanings.
- Do not output raw values such as "Высокая"; convert them into a grammatically complete phrase only when relevant to that subject.
- Every option must be at most 60 characters.
- Keep title as the strongest option, but still return titleCandidates for deterministic validation.

SUBJECT PRIORITIES:
- Брюки/Джинсы: model or silhouette, rise, supported construction detail.
- Шорты: model such as бермуды or карго, silhouette, rise, supported detail.
- Юбки: mini/midi/maxi length, silhouette such as А-силуэт or карандаш, pleats, wrap, or slit.
- Платья: mini/midi/maxi length, silhouette, sleeve or supported construction detail.
- Рубашки: fit, sleeve length, collar, buttons, or supported pocket construction.
- Куртки: construction such as утепленная or стеганая, length, hood, collar, zipper, or belt.
- Do not reuse trousers vocabulary such as штанинами or посадкой for dresses, shirts, or jackets.
""".strip()

DESCRIPTION_GENERATION_PROMPT = """
DESCRIPTION GENERATION RULES FOR ALL FASHION SUBJECTS:
- Write natural Russian prose specific to the exact resolved WB subject.
- Use the provided description_blueprint as guidance, not as text to copy.
- Describe supported construction, fit, material, comfort, use cases, styling, and safe care guidance.
- Never mention a concrete color, gender, audience, brand, SEO process, keyword list, or raw attribute dump.
- Never call the product another subject. Another garment may appear only as an obvious styling companion.
- Never invent composition, season, closure, lining, protection, certification, originality, or guarantees.
- Avoid emoji, bullet lists, keyword chains, repeated filler, and meta sentences about the description.
- Write 3 to 5 short paragraphs, target 350 to 750 characters, and keep the language varied and natural.
""".strip()


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
    ) -> list[CardUploadGroup]:
        fallback_intent = ProductIntentParser.parse(user_input.note)
        gemini_intent = ProductIntentParser.from_analysis(analysis)
        intent = gemini_intent.merge_missing(fallback_intent)
        if self._client and self._model:
            return self._generate_with_openai(user_input, analysis, subject, charcs, intent)
        return self._generate_fallback(user_input, analysis, subject, charcs, intent)

    def _generate_with_openai(
        self,
        user_input: ProductInput,
        analysis: ImageAnalysis,
        subject: dict[str, Any],
        charcs: list[dict[str, Any]],
        intent: ProductIntent,
    ) -> list[CardUploadGroup]:
        user_payload = {
            "task": "generate_wildberries_product_card",
            "user_input": user_input.model_dump(),
            "extracted_user_intent": self._intent_payload(intent),
            "image_analysis": analysis.model_dump(),
            "title_generation_rules": {
                "candidate_count": 5,
                "language": "ru",
                "max_length": 60,
                "must_start_with_subject": True,
                "forbidden_fields": ["gender", "audience", "age", "color", "brand", "season", "material", "composition"],
                "use_only_supported_attributes": True,
                "subject_priorities": {
                    "Брюки/Джинсы": ["model", "silhouette", "rise", "detail"],
                    "Шорты": ["model", "silhouette", "rise", "detail"],
                    "Юбки": ["length", "silhouette", "pleats_or_wrap_or_slit"],
                    "Платья": ["length", "silhouette", "sleeve_or_construction"],
                    "Рубашки": ["fit", "sleeve", "collar_or_buttons_or_pockets"],
                    "Куртки": ["construction", "length", "hood_or_collar_or_zipper_or_belt"],
                },
            },
            "description_blueprint": build_description_prompt_context(subject.get("subjectName")),
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
                    {
                        "role": "system",
                        "content": f"{SYSTEM_PROMPT}\n\n{TITLE_GENERATION_PROMPT}\n\n{DESCRIPTION_GENERATION_PROMPT}",
                    },
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, separators=(",", ":"))},
                ],
                temperature=0.2,
            )
            raw = json.loads(response.choices[0].message.content or "[]")
            raw = self._enrich_openai_output(raw, user_input, analysis, subject, intent, charcs)
            return [CardUploadGroup.model_validate(item) for item in raw]
        except Exception:
            return self._generate_fallback(user_input, analysis, subject, charcs, intent)

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
    ) -> Any:
        if not isinstance(raw, list):
            return raw
        for group in raw:
            if not isinstance(group, dict):
                continue
            for variant in group.get("variants", []) or []:
                if not isinstance(variant, dict):
                    continue
                variant.setdefault("vendorCode", self._vendor_base(user_input, intent))
                variant["brand"] = self._brand(user_input)
                subject_name = str(subject.get("subjectName") or analysis.category or user_input.category or "Товар")
                raw_candidates = variant.pop("titleCandidates", variant.pop("title_candidates", []))
                if not isinstance(raw_candidates, list):
                    raw_candidates = []
                candidates = [str(item) for item in raw_candidates if str(item).strip()]
                if variant.get("title"):
                    candidates.insert(0, str(variant["title"]))
                variant["title"] = select_best_ai_title(
                    subject_name,
                    candidates,
                    analysis,
                    user_input,
                    brand=self._brand(user_input),
                ) or build_product_title(subject_name, analysis, user_input)
                variant["description"] = finalize_product_description(
                    subject_name,
                    variant.get("description"),
                    analysis,
                    user_input,
                )
                variant.setdefault("dimensions", self._dimensions(user_input, intent))
                if not variant.get("sizes"):
                    variant["sizes"] = [size.model_dump(mode="json", exclude_none=True) for size in self._sizes(user_input, intent)]
        self._apply_intent_to_raw(raw, user_input, intent, charcs)
        return raw

    def _generate_fallback(
        self,
        user_input: ProductInput,
        analysis: ImageAnalysis,
        subject: dict[str, Any],
        charcs: list[dict[str, Any]],
        intent: ProductIntent,
    ) -> list[CardUploadGroup]:
        subject_id = int(subject["subjectID"])
        default_category = subject.get("subjectName") or "Товар"
        title = self._title(user_input, analysis, default_category)
        variant = Variant(
            vendorCode=self._vendor_base(user_input, intent),
            title=title,
            description=self._description(analysis, title, default_category, user_input),
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
    def _title(user_input: ProductInput, analysis: ImageAnalysis, default_category: str) -> str:
        return build_product_title(default_category, analysis, user_input)

    @staticmethod
    def _description(
        analysis: ImageAnalysis,
        title: str,
        subject_name: str | None = None,
        user_input: ProductInput | None = None,
    ) -> str:
        return build_product_description(subject_name or analysis.category or title, analysis, user_input or ProductInput())

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
                    variant["vendorCode"] = f"{vendor_base}/{color.value}"
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
