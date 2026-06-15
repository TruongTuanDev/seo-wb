import json
import logging
import os
import time
from io import BytesIO
from typing import Any
from PIL import Image, UnidentifiedImageError
from google import genai
from google.genai import types

from app.core.config import Settings
from app.core.errors import AppError
from app.services.color_fidelity import extract_color_signature

logger = logging.getLogger(__name__)

CATEGORY_TO_GARMENT_AREA = {
    "shirt": "upper_body",
    "t-shirt": "upper_body",
    "tee": "upper_body",
    "hoodie": "upper_body",
    "sweatshirt": "upper_body",
    "jacket": "upper_body",
    "coat": "upper_body",

    "pants": "lower_body",
    "jeans": "lower_body",
    "shorts": "lower_body",
    "skirt": "lower_body",

    "dress": "full_body",
    "gown": "full_body",
    "sarafan": "full_body",
    "set": "full_body",
    "jumpsuit": "full_body",

    "брюки": "lower_body",
    "джинсы": "lower_body",
    "шорты": "lower_body",
    "юбка": "lower_body",
    "платье": "full_body",
    "сарафан": "full_body",
    "худи": "upper_body",
    "свитшот": "upper_body",
    "рубашка": "upper_body",
    "футболка": "upper_body",
    "куртка": "upper_body"
}

GARMENT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "product_type": {"type": "STRING"},
        "garment_area": {"type": "STRING"},
        "category": {"type": "STRING"},
        "gender": {"type": "STRING"},
        "main_color": {"type": "STRING"},
        "secondary_color": {"type": "STRING"},
        "secondary_colors": {"type": "ARRAY", "items": {"type": "STRING"}},
        "color_palette": {"type": "ARRAY", "items": {"type": "STRING"}},
        "material": {"type": "STRING"},
        "fabric_texture": {"type": "STRING"},
        "silhouette": {"type": "STRING"},
        "fit": {"type": "STRING"},
        "length": {"type": "STRING"},
        "waist": {"type": "STRING", "nullable": True},
        "neckline": {"type": "STRING", "nullable": True},
        "sleeves": {"type": "STRING", "nullable": True},
        "closure": {"type": "STRING"},
        "pockets": {"type": "STRING"},
        "hem": {"type": "STRING"},
        "logo_or_text": {"type": "STRING"},
        "front_view": {
            "type": "OBJECT",
            "properties": {
                "description": {"type": "STRING"},
                "key_details": {"type": "ARRAY", "items": {"type": "STRING"}}
            },
            "required": ["description", "key_details"]
        },
        "back_view": {
            "type": "OBJECT",
            "properties": {
                "description": {"type": "STRING"},
                "key_details": {"type": "ARRAY", "items": {"type": "STRING"}}
            },
            "required": ["description", "key_details"]
        },
        "special_details": {"type": "ARRAY", "items": {"type": "STRING"}},
        "complex_product_mode": {"type": "BOOLEAN"},
        "must_preserve": {"type": "ARRAY", "items": {"type": "STRING"}},
        "must_not_change": {"type": "ARRAY", "items": {"type": "STRING"}},
        "prompt_summary": {"type": "STRING"}
    },
    "required": [
        "product_type", "garment_area", "category", "gender", "main_color",
        "secondary_colors", "material", "fabric_texture", "silhouette", "fit",
        "length", "waist", "neckline", "sleeves", "closure", "pockets", "hem",
        "logo_or_text", "front_view", "back_view", "must_preserve", "must_not_change",
        "prompt_summary"
    ]
}


def resolve_garment_area(category: str) -> str | None:
    if not category:
        return None
    cat = str(category).lower().strip()
    
    # Priority exact and substring match
    for k, v in CATEGORY_TO_GARMENT_AREA.items():
        if k == cat:
            return v
            
    # Check Russian and English roots
    if any(x in cat for x in ["юбк", "skirt"]):
        return "lower_body"
    if any(x in cat for x in ["плать", "сарафан", "dress", "gown", "set", "jumpsuit"]):
        return "full_body"
    if any(x in cat for x in ["брюк", "штан", "леггинс", "тайтс", "джоггер", "джинс", "шорт", "pants", "jeans", "shorts"]):
        return "lower_body"
    if any(x in cat for x in ["худи", "свитшот", "толстовк", "джемпер", "свитер", "пуловер", "кардиган", "рубаш", "блуз", "футболк", "майк", "топ", "куртк", "пальто", "пиджак", "жилет", "ветровк", "бомбер", "shirt", "t-shirt", "tee", "hoodie", "sweatshirt", "jacket", "coat"]):
        return "upper_body"

    # Fallback to direct substring search in the dict keys
    for k, v in CATEGORY_TO_GARMENT_AREA.items():
        if k in cat or cat in k:
            return v

    return None


class GarmentAnalyzer:
    def __init__(self, settings: Settings):
        if not settings.gemini_api_key:
            raise AppError("missing_gemini_key", "GEMINI_API_KEY is missing.", 500)
        self._settings = settings
        self._model = os.getenv("GEMINI_MODEL") or settings.gemini_model
        self._client = genai.Client(api_key=settings.gemini_api_key)

    def analyze(
        self,
        front_image_bytes: bytes,
        back_image_bytes: bytes | None = None,
        title: str | None = None,
        description: str | None = None,
        category: str | None = None,
        gender: str | None = None,
    ) -> dict[str, Any]:
        images = []
        try:
            front_img = self._load_image(front_image_bytes)
            images.append(front_img)
        except Exception as exc:
            raise AppError("invalid_front_image", "Front product image is invalid.", 400) from exc

        if back_image_bytes:
            try:
                back_img = self._load_image(back_image_bytes)
                images.append(back_img)
            except Exception as exc:
                logger.warning("Optional back image is invalid: %s", exc)

        # Pre-resolve expected area
        resolved_area = resolve_garment_area(category)

        prompt = self._build_prompt(
            title=title,
            description=description,
            category=category,
            gender=gender,
            resolved_area=resolved_area,
            has_back_image=bool(back_image_bytes)
        )

        last_exc: Exception | None = None
        response_text = ""
        use_fallback = False
        for attempt in range(1, 4):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=[prompt, *images],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=GARMENT_SCHEMA,
                        temperature=0.1,
                    ),
                )
                response_text = response.text
                break
            except Exception as exc:
                last_exc = exc
                logger.warning("Gemini analyze attempt %d failed: %s", attempt, exc)
                if attempt < 3:
                    time.sleep(1.5 * attempt)
        else:
            logger.error("Gemini garment analysis failed after all attempts. Falling back. Error: %s", last_exc)
            use_fallback = True

        garment_json = {}
        if not use_fallback:
            try:
                garment_json = json.loads(response_text or "{}")
            except Exception as exc:
                logger.warning("Gemini returned invalid garment JSON. Falling back. Error: %s", exc)
                use_fallback = True

        if use_fallback:
            fallback_category = category or "clothing"
            fallback_area = resolved_area or "full_body"
            fallback_gender = gender or "female"
            
            english_cat = fallback_category
            from app.services.virtual_try_on import resolve_english_category
            try:
                english_cat = resolve_english_category(fallback_category)
            except Exception:
                pass

            garment_json = {
                "product_type": title or english_cat,
                "garment_area": fallback_area,
                "category": english_cat,
                "gender": fallback_gender,
                "main_color": "unknown",
                "secondary_color": "",
                "secondary_colors": [],
                "color_palette": [],
                "material": "fabric",
                "fabric_texture": "smooth",
                "silhouette": "regular",
                "fit": "regular",
                "length": "regular",
                "waist": "regular",
                "neckline": "regular",
                "sleeves": "regular",
                "closure": "none",
                "pockets": "none",
                "hem": "regular",
                "logo_or_text": "none",
                "front_view": {
                    "description": title or f"A professional photograph of {english_cat}.",
                    "key_details": []
                },
                "back_view": {
                    "description": "No back view details available",
                    "key_details": []
                },
                "special_details": [],
                "complex_product_mode": False,
                "must_preserve": [],
                "must_not_change": [],
                "prompt_summary": f"A high-quality catalog photo of {title or english_cat}.",
                "warnings": ["Gemini garment analysis failed, using local fallback analysis (Lỗi: " + str(last_exc)[:200] + ")"]
            }

        return self.normalize_analysis(
            garment_json,
            front_image_bytes=front_image_bytes,
            title=title,
            description=description,
            category=category,
            gender=gender,
        )

    @staticmethod
    def normalize_analysis(
        garment_json: dict[str, Any],
        *,
        front_image_bytes: bytes,
        title: str | None = None,
        description: str | None = None,
        category: str | None = None,
        gender: str | None = None,
    ) -> dict[str, Any]:
        garment_json = dict(garment_json or {})
        resolved_area = resolve_garment_area(category)

        # User-selected category is authoritative and determines the garment area.
        if category:
            garment_json["category"] = category
        if resolved_area:
            garment_json["garment_area"] = resolved_area
        else:
            # If no product category was selected, infer area from the AI-guessed category
            inferred_area = resolve_garment_area(garment_json.get("category"))
            if inferred_area:
                garment_json["garment_area"] = inferred_area
            else:
                garment_json.setdefault("garment_area", "upper_body")

        if gender:
            garment_json["gender"] = gender

        # Ensure schema structure
        garment_json.setdefault("secondary_colors", [])
        garment_json.setdefault("secondary_color", "")
        garment_json.setdefault("color_palette", [])
        garment_json.setdefault("special_details", [])
        garment_json.setdefault("complex_product_mode", False)
        garment_json.setdefault("must_preserve", [])
        garment_json.setdefault("must_not_change", [])

        signature = extract_color_signature(front_image_bytes, garment_json.get("garment_area"))
        garment_json["color_palette"] = signature.palette_hex
        if not garment_json.get("main_color") or str(garment_json.get("main_color")).strip().lower() in {"unknown", "n/a", "none"}:
            garment_json["main_color"] = signature.dominant_name
        if not garment_json.get("secondary_color"):
            garment_json["secondary_color"] = (
                garment_json["secondary_colors"][0]
                if garment_json.get("secondary_colors")
                else (signature.palette_hex[1] if len(signature.palette_hex) > 1 else "")
            )
        garment_json["special_details"] = _derive_special_details(garment_json)
        garment_json["complex_product_mode"] = _is_complex_product(garment_json)
        garment_json["must_preserve"] = _merge_rules(
            garment_json.get("must_preserve", []),
            [
                "exact color palette",
                "denim wash pattern",
                "fabric texture",
                "stitching",
                "pockets",
                "seams",
                "logos and branding",
                *garment_json["special_details"],
            ],
        )
        garment_json["must_not_change"] = _merge_rules(
            garment_json.get("must_not_change", []),
            [
                "do not recolor the garment",
                "do not change denim wash",
                "do not modify distressing",
                "do not move rhinestones or embellishments",
                "do not remove embroidery or logos",
                "do not redesign the garment",
            ],
        )
        garment_json["source_title"] = title or ""
        garment_json["source_description"] = description or ""
        garment_json["source_category"] = category or garment_json.get("category") or ""
        garment_json["model_profile"] = _recommend_model_profile(
            garment_json=garment_json,
            title=title,
            description=description,
            category=category,
            gender=gender,
        )

        return garment_json

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
    def _build_prompt(
        title: str | None,
        description: str | None,
        category: str | None,
        gender: str | None,
        resolved_area: str | None,
        has_back_image: bool
    ) -> str:
        context = []
        if title:
            context.append(f"Title: {title}")
        if description:
            context.append(f"Description: {description}")
        if category:
            context.append(f"Category: {category}")
        if gender:
            context.append(f"Gender: {gender}")
        if resolved_area:
            context.append(f"Expected garment area: {resolved_area}")

        context_str = "\n".join(context) if context else "No metadata available."

        return f"""
Analyze the uploaded product image(s) to fill out the garment JSON schema.
We have:
- Front image (always present)
- Back image ({"present" if has_back_image else "missing"})

Metadata Context:
{context_str}

Rules:
1. Identify product type, category, gender, color, material, texture, silhouette, closures, pockets, hems, and details.
2. Fill out must_preserve and must_not_change fields carefully:
   - must_preserve lists fields from the garment that should remain exactly consistent in catalog photos (e.g. category, area, silhouette, pocket shape).
   - must_not_change lists rules for what the generator should avoid doing (e.g., "do not turn skirt into pants", "do not change color").
3. Set the 'prompt_summary' to a concise, descriptive English prompt describing all key details of the garment for image generation.
4. If back image is missing, back_view.description should state "No back view provided" and back_view.key_details should be empty. Do not invent the back design.
5. All values must be in English.
""".strip()


def _derive_special_details(garment_json: dict[str, Any]) -> list[str]:
    details = []
    front_details = garment_json.get("front_view", {}).get("key_details", []) or []
    back_details = garment_json.get("back_view", {}).get("key_details", []) or []
    extra_fields = [
        garment_json.get("logo_or_text", ""),
        garment_json.get("fabric_texture", ""),
        garment_json.get("closure", ""),
        garment_json.get("pockets", ""),
        garment_json.get("hem", ""),
    ]
    combined = [*front_details, *back_details, *extra_fields]
    for item in combined:
        text = str(item or "").strip()
        if not text:
            continue
        lowered = text.lower()
        if any(keyword in lowered for keyword in ("ripped", "distress", "rhinestone", "embroid", "logo", "print", "stud", "crystal", "seam", "pocket", "wash")):
            if text not in details:
                details.append(text)
    return details[:8]


def _merge_rules(existing: list[str], additions: list[str]) -> list[str]:
    merged: list[str] = []
    for item in [*(existing or []), *additions]:
        text = str(item or "").strip()
        if text and text not in merged:
            merged.append(text)
    return merged


def _is_complex_product(garment_json: dict[str, Any]) -> bool:
    keywords = (
        "rhinestone",
        "crystal",
        "stud",
        "embellishment",
        "ripped",
        "distressed",
        "wash",
        "embroidery",
        "logo",
        "printed text",
    )
    def has_keyword(v):
        if isinstance(v, str):
            return any(k in v.lower() for k in keywords)
        if isinstance(v, list):
            return any(has_keyword(x) for x in v)
        if isinstance(v, dict):
            return any(has_keyword(x) for x in v.values())
        return False
    return any(has_keyword(val) for key, val in garment_json.items())


def _recommend_model_profile(
    garment_json: dict[str, Any],
    title: str | None,
    description: str | None,
    category: str | None,
    gender: str | None,
) -> dict[str, str]:
    text = " ".join(
        [
            str(title or ""),
            str(description or ""),
            str(category or garment_json.get("category") or ""),
            str(garment_json.get("fit") or ""),
            str(garment_json.get("silhouette") or ""),
            str(garment_json.get("prompt_summary") or ""),
        ]
    ).lower()

    model_gender = "female"
    normalized_gender = str(gender or garment_json.get("gender") or "").lower()
    if any(token in normalized_gender for token in ("male", "man", "men", "boy", "муж")):
        model_gender = "male"

    age_group = "adult"
    if any(token in text for token in ("teen", "youth", "student", "young", "молод")):
        age_group = "young_adult"
    elif any(token in text for token in ("kids", "child", "детск", "baby")):
        age_group = "teen"

    body_type = "average"
    if any(token in text for token in ("plus size", "oversize", "oversized", "baggy", "xxl", "3xl", "4xl")):
        body_type = "plus_size"
    elif any(token in text for token in ("athletic", "sport", "gym", "muscular")):
        body_type = "athletic"
    elif any(token in text for token in ("slim", "skinny", "tailored", "fitted", "xs", "petite")):
        body_type = "slim"

    aesthetic = "clean russian ecommerce model"
    if any(token in text for token in ("luxury", "premium", "boutique", "elegant")):
        aesthetic = "elegant russian fashion ecommerce model"
    elif any(token in text for token in ("street", "urban", "hoodie", "cargo", "denim")):
        aesthetic = "modern russian streetwear ecommerce model"
    elif any(token in text for token in ("sport", "fitness", "gym")):
        aesthetic = "athletic russian ecommerce model"

    styling_notes = []
    if garment_json.get("garment_area") == "lower_body":
        styling_notes.append("keep the upper-body styling simple so the lower-body garment remains the hero product")
    elif garment_json.get("garment_area") == "upper_body":
        styling_notes.append("keep the lower-body styling simple so the upper-body garment remains the hero product")
    else:
        styling_notes.append("keep the whole look balanced and suitable for ecommerce catalog photography")

    return {
        "ethnicity": "russian",
        "gender": model_gender,
        "age_group": age_group,
        "body_type": body_type,
        "aesthetic": aesthetic,
        "styling_notes": "; ".join(styling_notes),
    }
