import base64
import json
import time
from io import BytesIO

from google import genai
from google.genai import types
from openai import OpenAI
from PIL import Image, UnidentifiedImageError

from app.core.config import Settings
from app.core.errors import AppError
from app.schemas.card import ImageAnalysis, ProductInput
from app.services.product_intent_parser import ProductIntentParser


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
    },
}


class GeminiAnalyzer:
    def __init__(self, settings: Settings):
        if not settings.gemini_api_key and not (settings.openai_api_key and settings.openai_card_model):
            raise AppError("missing_analysis_provider", "Gemini or OpenAI vision configuration is required.", 500)
        self._model = settings.gemini_model
        self._client = genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else None
        self._openai_model = settings.openai_card_model
        self._openai_client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key and settings.openai_card_model else None

    def analyze(self, image_bytes_list: list[bytes], user_input: ProductInput) -> ImageAnalysis:
        if not image_bytes_list:
            raise AppError("empty_images", "At least one product image is required.", 400)

        images = [self._load_image(image_bytes) for image_bytes in image_bytes_list]
        prompt = self._build_prompt(user_input)
        last_exc: Exception | None = None
        response_text: str | None = None
        if self._client:
            for attempt in range(1, 4):
                try:
                    response = self._client.models.generate_content(
                        model=self._model,
                        contents=[prompt, *images],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=ANALYSIS_SCHEMA,
                            temperature=0.1,
                        ),
                    )
                    response_text = response.text
                    break
                except Exception as exc:
                    last_exc = exc
                    if self._is_non_retryable_quota_error(exc):
                        break
                    if attempt < 3:
                        time.sleep(1.5 * attempt)

        if response_text is None and self._openai_client:
            try:
                response_text = self._analyze_with_openai(image_bytes_list, prompt)
            except Exception as exc:
                last_exc = exc

        if response_text is None:
            raise AppError(
                "image_analysis_failed",
                "Image analysis providers are unavailable.",
                503,
                {"reason": str(last_exc)[:500]},
            ) from last_exc

        try:
            raw = json.loads(response_text or "{}")
            raw = self._normalize_analysis(raw)
            if last_exc is not None:
                raw["warnings"].append("Gemini unavailable; image analysis used OpenAI fallback.")
            raw["source_image_count"] = len(images)
            from app.services.studio_recommender import recommend_for_product
            raw["recommendations"] = recommend_for_product(raw, user_input)
            return ImageAnalysis.model_validate(raw)
        except Exception as exc:
            raise AppError(
                "gemini_invalid_json",
                "Image analysis provider returned invalid JSON.",
                502,
                {"raw": (response_text or "")[:1000]},
            ) from exc

    def _analyze_with_openai(self, image_bytes_list: list[bytes], prompt: str) -> str:
        content: list[dict] = [{"type": "text", "text": prompt}]
        for image_bytes in image_bytes_list:
            encoded = base64.b64encode(image_bytes).decode("ascii")
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}})
        response = self._openai_client.chat.completions.create(
            model=self._openai_model,
            messages=[
                {"role": "system", "content": "Analyze fashion product images and return JSON only."},
                {"role": "user", "content": content},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        return response.choices[0].message.content or "{}"

    @staticmethod
    def _is_non_retryable_quota_error(exc: Exception) -> bool:
        message = str(exc).casefold()
        return any(marker in message for marker in ("resource_exhausted", "prepayment credits are depleted", "billing"))

    @staticmethod
    def _normalize_analysis(raw: dict) -> dict:
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
        return raw

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
- For category, return the closest Wildberries clothes subject name in Russian plural form, for example:
  Брюки, Шорты, Джинсы, Футболки, Майки, Рубашки, Блузки, Платья, Юбки, Костюмы.
- If user hints and image disagree on category, trust user hints and add a warning.
- If uncertain, add a short warning and lower confidence.
- Extract only factual product attributes useful for a Wildberries card.

User hints:
{hints_text}
""".strip()
