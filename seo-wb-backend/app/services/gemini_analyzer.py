import json
import logging
import random
import time
from io import BytesIO

from google import genai
from google.genai import types
from PIL import Image, UnidentifiedImageError

from app.core.config import Settings
from app.core.errors import AppError
from app.schemas.card import ImageAnalysis, ProductInput
from app.services.garment_analyzer import GARMENT_SCHEMA, GarmentAnalyzer
from app.services.product_intent_parser import ProductIntentParser


logger = logging.getLogger(__name__)


ANALYSIS_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "category": {"type": "STRING"},
        "product_name": {"type": "STRING"},
        "material": {"type": "STRING"},
        "color": {"type": "STRING"},
        "gender": {"type": "STRING"},
        "season": {"type": "STRING"},
        "fit_type": {"type": "STRING"},
        "features": {"type": "ARRAY", "items": {"type": "STRING"}},
        "attributes": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "value": {"type": "STRING"},
                },
            },
        },
        "confidence": {"type": "NUMBER"},
        "warnings": {"type": "ARRAY", "items": {"type": "STRING"}},
        "variant_colors": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "value": {"type": "STRING"},
                    "code": {"type": "STRING"},
                },
            },
        },
        "sizes": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "techSize": {"type": "STRING"},
                    "wbSize": {"type": "STRING"},
                },
            },
        },
        "package": {
            "type": "OBJECT",
            "properties": {
                "length": {"type": "NUMBER"},
                "width": {"type": "NUMBER"},
                "height": {"type": "NUMBER"},
                "weightBrutto": {"type": "NUMBER"},
            },
        },
        "vendor_code_base": {"type": "STRING"},
        "garment_analysis": GARMENT_SCHEMA,
    },
}


class GeminiAnalyzer:
    def __init__(self, settings: Settings):
        if not settings.gemini_api_key:
            raise AppError("missing_gemini_key", "GEMINI_API_KEY is missing.", 500)
        self._model = settings.gemini_model
        self._fallback_model = settings.gemini_fallback_model
        self._retry_attempts = max(1, settings.gemini_analysis_retry_attempts)
        self._retry_backoff = max(0.1, settings.gemini_retry_backoff_seconds)
        self._retry_max_backoff = max(self._retry_backoff, settings.gemini_retry_max_backoff_seconds)
        self._client = genai.Client(api_key=settings.gemini_api_key)

    def analyze(self, image_bytes_list: list[bytes], user_input: ProductInput) -> ImageAnalysis:
        if not image_bytes_list:
            raise AppError("empty_images", "At least one product image is required.", 400)

        images = [self._load_image(image_bytes) for image_bytes in image_bytes_list]
        prompt = self._build_prompt(user_input)
        response, used_model = self._generate_with_failover(prompt, images)

        try:
            raw = json.loads(response.text or "{}")
            raw = self._normalize_analysis(raw, image_bytes_list[0], user_input)
            raw["source_image_count"] = len(images)
            raw["garment_json"]["analysis_model"] = used_model
            raw["garment_json"]["analysis_fallback_used"] = used_model != self._model
            from app.services.studio_recommender import recommend_for_product
            raw["recommendations"] = recommend_for_product(raw, user_input)
            return ImageAnalysis.model_validate(raw)
        except Exception as exc:
            raise AppError(
                "gemini_invalid_json",
                "Gemini returned invalid analysis JSON.",
                502,
                {"raw": (response.text or "")[:1000]},
            ) from exc

    def _generate_with_failover(self, prompt: str, images: list[Image.Image]):
        models = [self._model]
        if self._fallback_model and self._fallback_model not in models:
            models.append(self._fallback_model)

        last_exc: Exception | None = None
        for model_index, model in enumerate(models):
            for attempt in range(self._retry_attempts):
                try:
                    response = self._client.models.generate_content(
                        model=model,
                        contents=[prompt, *images],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=ANALYSIS_SCHEMA,
                            temperature=0.1,
                        ),
                    )
                    if model_index:
                        logger.warning("Gemini analysis recovered with fallback model %s.", model)
                    return response, model
                except Exception as exc:
                    last_exc = exc
                    retryable = self._is_retryable_error(exc)
                    has_next_attempt = attempt < self._retry_attempts - 1
                    logger.warning(
                        "Gemini analysis failed. model=%s attempt=%s/%s retryable=%s error=%s",
                        model,
                        attempt + 1,
                        self._retry_attempts,
                        retryable,
                        str(exc)[:300],
                    )
                    if not retryable or not has_next_attempt:
                        break
                    delay = min(self._retry_backoff * (2**attempt), self._retry_max_backoff)
                    time.sleep(delay + random.uniform(0, min(0.75, delay * 0.25)))

        raise AppError(
            "image_analysis_temporarily_unavailable",
            "AI image analysis is temporarily busy. The system already retried automatically; please try again shortly.",
            503,
        ) from last_exc

    @staticmethod
    def _is_retryable_error(exc: Exception) -> bool:
        text = str(exc).casefold()
        transient_markers = (
            "429",
            "500",
            "502",
            "503",
            "504",
            "resource_exhausted",
            "unavailable",
            "high demand",
            "temporarily",
            "timeout",
            "timed out",
            "connection",
        )
        return any(marker in text for marker in transient_markers)

    @staticmethod
    def _normalize_analysis(raw: dict, front_image_bytes: bytes, user_input: ProductInput) -> dict:
        attributes = raw.get("attributes")
        if isinstance(attributes, list):
            normalized = {}
            for item in attributes:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                value = item.get("value")
                if name and value:
                    normalized[str(name)] = str(value)
            raw["attributes"] = normalized
        elif not isinstance(attributes, dict):
            raw["attributes"] = {}
        raw.setdefault("features", [])
        raw.setdefault("warnings", [])
        raw.setdefault("confidence", 0)
        raw["variant_colors"] = GeminiAnalyzer._normalize_variant_colors(raw.get("variant_colors"))
        raw["sizes"] = GeminiAnalyzer._normalize_sizes(raw.get("sizes"))
        raw["package"] = GeminiAnalyzer._normalize_package(raw.get("package"))
        if raw.get("vendor_code_base") is not None:
            raw["vendor_code_base"] = str(raw["vendor_code_base"]).strip() or None
        garment_json = raw.pop("garment_analysis", None)
        used_garment_fallback = not isinstance(garment_json, dict)
        if used_garment_fallback:
            garment_json = GeminiAnalyzer._garment_fallback_from_analysis(raw)
        raw["garment_json"] = GarmentAnalyzer.normalize_analysis(
            garment_json,
            front_image_bytes=front_image_bytes,
            title=raw.get("product_name"),
            category=user_input.category or raw.get("category"),
            gender=user_input.gender or raw.get("gender"),
        )
        raw["garment_json"]["analysis_source"] = "primary_product_vision"
        raw["garment_json"]["analysis_version"] = 1
        raw["garment_json"]["provider_garment_fallback_used"] = used_garment_fallback
        return raw

    @staticmethod
    def _garment_fallback_from_analysis(raw: dict) -> dict:
        features = [str(item).strip() for item in raw.get("features", []) if str(item).strip()]
        product_name = str(raw.get("product_name") or raw.get("category") or "garment")
        return {
            "product_type": product_name,
            "category": raw.get("category") or "clothing",
            "gender": raw.get("gender") or "female",
            "main_color": raw.get("color") or "unknown",
            "secondary_colors": [],
            "material": raw.get("material") or "fabric",
            "fabric_texture": "unknown",
            "silhouette": raw.get("fit_type") or "regular",
            "fit": raw.get("fit_type") or "regular",
            "length": "regular",
            "waist": "unknown",
            "neckline": "unknown",
            "sleeves": "unknown",
            "closure": "unknown",
            "pockets": "unknown",
            "hem": "unknown",
            "logo_or_text": "none",
            "front_view": {"description": product_name, "key_details": features},
            "back_view": {"description": "Back view from uploaded reference", "key_details": []},
            "special_details": features,
            "must_preserve": features,
            "must_not_change": [],
            "prompt_summary": product_name,
        }

    @staticmethod
    def _normalize_variant_colors(raw: object) -> list[dict[str, str]]:
        if not isinstance(raw, list):
            return []
        normalized = []
        seen = set()
        for item in raw:
            if not isinstance(item, dict):
                continue
            value = str(item.get("value") or "").strip()
            code = str(item.get("code") or "").strip().upper()
            if not value:
                continue
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            normalized.append({"value": value, "code": ProductIntentParser.vendor_suffix_from_color(value)})
        return normalized[:30]

    @staticmethod
    def _normalize_sizes(raw: object) -> list[dict[str, str]]:
        if not isinstance(raw, list):
            return []
        normalized = []
        seen = set()
        for item in raw:
            if not isinstance(item, dict):
                continue
            tech_size = str(item.get("techSize") or item.get("tech_size") or "").strip().upper()
            wb_size = str(item.get("wbSize") or item.get("wb_size") or tech_size).strip().upper()
            if not tech_size:
                continue
            key = (tech_size, wb_size)
            if key in seen:
                continue
            seen.add(key)
            normalized.append({"techSize": tech_size, "wbSize": wb_size})
        return normalized[:30]

    @staticmethod
    def _normalize_package(raw: object) -> dict[str, float | int]:
        if not isinstance(raw, dict):
            return {}
        result = {}
        for key in ("length", "width", "height", "weightBrutto"):
            try:
                value = float(raw.get(key))
            except (TypeError, ValueError):
                continue
            if key == "weightBrutto" and value > 20:
                value = value / 1000
            if value > 0:
                result[key] = int(value) if value.is_integer() else value
        return result

    @staticmethod
    def _fallback_color_code(value: str) -> str:
        return ProductIntentParser.vendor_suffix_from_color(value)

    @staticmethod
    def _load_image(image_bytes: bytes) -> Image.Image:
        try:
            image = Image.open(BytesIO(image_bytes))
            image.load()
            image = image.convert("RGB")
            max_side = 1280
            if max(image.size) > max_side:
                image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            return image
        except UnidentifiedImageError as exc:
            raise AppError("invalid_image", "Uploaded file is not a valid image.", 400) from exc

    @staticmethod
    def _build_prompt(user_input: ProductInput) -> str:
        hints = []
        if user_input.category:
            hints.append(f"Category hint: {user_input.category}")
        if user_input.subject_id is not None:
            hints.append(f"SubjectID hint: {user_input.subject_id}")
        if user_input.brand:
            hints.append(f"Brand hint: {user_input.brand}")
        if user_input.vendor_code:
            hints.append(f"VendorCode hint: {user_input.vendor_code}")
        if user_input.note:
            hints.append(f"User note: {user_input.note}")
        if user_input.attributes:
            hints.append(f"Known attributes: {json.dumps(user_input.attributes, ensure_ascii=False)}")

        hints_text = "\n".join(hints) if hints else "No user hints."
        return f"""
You are a Wildberries fashion product analyst.
Analyze the product image and return only valid JSON matching the schema.

Rules:
- You may receive multiple images of the same product, for example front, back, label, fabric close-up, or detail shots.
- Combine evidence from all images into one product analysis.
- If images disagree, trust explicit user hints first, then the clearest image, and add a warning.
- Use Russian attribute names and Russian values when possible.
- Treat user hints as higher priority than image guesses.
- Do not invent brand, vendor code, or exact composition if not visible or not provided.
- Extract user-intended color variants into variant_colors. Use Russian color values and short Latin/Vietnamese-safe uppercase code suffixes.
- Extract sizes into sizes. For S-42, return techSize=S and wbSize=42. For single size S, return techSize=S and wbSize=S.
- Extract package dimensions into package using length, width, height, weightBrutto.
- Extract base seller article/vendor code into vendor_code_base, without color suffix.
- Return garment_analysis in the same response. It will be reused for image generation, so describe the exact construction, front/back details, fabric texture, silhouette, fit, length, closures, pockets, hem, logos, decorations, and details that must not change.
- garment_analysis must describe only visible or user-confirmed facts. Use "unknown" for details that cannot be verified.
- Put every distinctive detail that image generation must preserve into garment_analysis.must_preserve.
- For category, return the closest Wildberries clothes subject name in Russian plural form, for example:
  Брюки, Шорты, Джинсы, Футболки, Майки, Рубашки, Блузки, Платья, Юбки, Костюмы.
- If user hints and image disagree on category, trust user hints and add a warning.
- If uncertain, add a short warning and lower confidence.
- Extract only factual product attributes useful for a Wildberries card.
- Keep fit_type for the product silhouette or cut, for example: широкие, прямые, зауженные, свободные, облегающие, оверсайз.
- Do not put rise values such as высокая, средняя, низкая into fit_type. Store them in attributes under the Russian key "Тип посадки".
- For trousers, jeans, shorts and skirts, identify the visible model/silhouette separately from the rise whenever possible.

User hints:
{hints_text}
""".strip()
