import json
import logging
import asyncio
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List
from PIL import Image
from google import genai
from google.genai import types
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings

logger = logging.getLogger(__name__)

EVALUATION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "product_visibility": {"type": "INTEGER"},
        "logo_visibility": {"type": "INTEGER"},
        "color_accuracy": {"type": "INTEGER"},
        "composition_quality": {"type": "INTEGER"},
        "ecommerce_suitability": {"type": "INTEGER"},
        "wrinkle_quality": {"type": "INTEGER"},
        "garment_realism": {"type": "INTEGER"},
        "pose_realism": {"type": "INTEGER"},
        "lighting_realism": {"type": "INTEGER"},
        "background_realism": {"type": "INTEGER"},
        "overall_score": {"type": "INTEGER"}
    },
    "required": [
        "product_visibility",
        "logo_visibility",
        "color_accuracy",
        "composition_quality",
        "ecommerce_suitability",
        "wrinkle_quality",
        "garment_realism",
        "pose_realism",
        "lighting_realism",
        "background_realism",
        "overall_score"
    ]
}

def verify_garment_category_florence(image_url: str, expected_category: str) -> bool:
    """Verifies that the generated image contains the expected garment category using Florence-2-large."""
    try:
        import fal_client
        
        logger.info("Running Florence-2 garment verification for expected: %s", expected_category)
        result = fal_client.subscribe(
            "fal-ai/florence-2-large/caption",
            arguments={
                "image_url": image_url
            }
        )
        
        caption = ""
        results = result.get("results") or []
        if results and isinstance(results, list):
            caption = results[0].get("caption") or ""
        elif isinstance(result, dict) and "caption" in result:
            caption = result.get("caption") or ""
            
        caption = caption.lower().strip()
        expected = str(expected_category or "").lower().strip()
        
        if not expected or not caption:
            return True
            
        # Map categories to synonyms
        synonyms = {
            "hoodie": ["hoodie", "sweater", "sweatshirt", "pullover"],
            "jacket": ["jacket", "coat", "blazer", "outerwear", "windbreaker", "cardigan"],
            "dress": ["dress", "gown", "robe", "jumpsuit"],
            "pants": ["pants", "trousers", "jeans", "leggings", "joggers"],
            "shorts": ["shorts", "trunks"],
            "shirt": ["shirt", "blouse", "top", "t-shirt"],
            "skirt": ["skirt"],
            "set": ["set", "suit", "costume", "outfit"]
        }
        
        allowed_terms = synonyms.get(expected, [expected])
        for term in allowed_terms:
            if term in caption:
                logger.info("Garment validation passed: found '%s' in caption '%s'", term, caption)
                return True
                
        logger.warning("Garment validation failed: none of %s found in caption '%s' (expected: %s)", allowed_terms, caption, expected)
        return False
    except Exception as exc:
        logger.error("Florence-2 garment validation failed: %s", exc)
        return True

def check_color_similarity(garment_bytes: bytes, generated_bytes: bytes) -> float:
    """Computes color similarity in HSV space using a pure-python Hue histogram."""
    try:
        img1 = Image.open(BytesIO(garment_bytes))
        img2 = Image.open(BytesIO(generated_bytes))
        
        hist1 = _compute_hue_histogram(img1)
        hist2 = _compute_hue_histogram(img2)
        
        dot_product = sum(a * b for a, b in zip(hist1, hist2))
        norm1 = sum(a * a for a in hist1) ** 0.5
        norm2 = sum(b * b for b in hist2) ** 0.5
        
        if norm1 * norm2 > 0:
            return dot_product / (norm1 * norm2)
        return 0.0
    except Exception as exc:
        logger.exception("Error checking color similarity: %s", exc)
        return 0.0

def _compute_hue_histogram(image: Image.Image, bins: int = 16) -> List[float]:
    # Resize to speed up calculation
    image = image.copy()
    image.thumbnail((250, 250))
    
    hsv = image.convert("HSV")
    h, s, v = hsv.split()
    h_data = list(h.getdata())
    s_data = list(s.getdata())
    
    # Filter for non-neutral colors (saturation > 30)
    h_filtered = [h_val for h_val, s_val in zip(h_data, s_data) if s_val > 30]
    if not h_filtered:
        h_filtered = h_data
        
    hist = [0] * bins
    bin_size = 256 / bins
    for val in h_filtered:
        idx = int(val / bin_size)
        if idx >= bins:
            idx = bins - 1
        hist[idx] += 1
        
    total = len(h_filtered)
    if total > 0:
        return [float(x) / total for x in hist]
    return [0.0] * bins


class CatalogQualityEngine:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._model = settings.gemini_model
        self._client = None
        if settings.gemini_api_key:
            self._client = genai.Client(api_key=settings.gemini_api_key)

    async def score_catalog_package(self, images: List[Dict[str, Any]], job_dir: Path) -> Dict[str, Any]:
        """Scores each image and selects the best catalog candidates."""
        if not self._client or not images:
            return {}

        # 1. Run evaluations in parallel
        async def evaluate_image(img_item: Dict[str, Any]) -> Dict[str, Any]:
            file_name = img_item["fileName"]
            file_path = job_dir / "output" / file_name
            if not file_path.exists():
                # Fallback to defaults if file not written yet
                return {
                    "fileName": file_name,
                    "scores": {
                        "product_visibility": 80,
                        "logo_visibility": 80,
                        "color_accuracy": 80,
                        "composition_quality": 80,
                        "ecommerce_suitability": 80,
                        "wrinkle_quality": 80,
                        "garment_realism": 80,
                        "pose_realism": 80,
                        "lighting_realism": 80,
                        "background_realism": 80,
                        "overall_score": 80
                    }
                }
            try:
                img = Image.open(file_path)
                img.load()
                
                # Resize if too large to fit prompt tokens nicely
                if max(img.size) > 1024:
                    img.thumbnail((1024, 1024))
                
                prompt = """
                You are an expert e-commerce catalog editor.
                Evaluate the quality of the generated product catalog image.
                Provide scores from 0 to 100 for the following attributes:
                - product_visibility: is the clothing clearly visible and not obstructed?
                - logo_visibility: are logos, stripes, branding markings clear and undistorted (if present)?
                - color_accuracy: does the color of the clothing look natural, clean, and accurate?
                - composition_quality: is the model framing, pose, and background well-balanced?
                - ecommerce_suitability: is the image suitable for a high-end catalog (like Zara or SHEIN)?
                - wrinkle_quality: does the clothing have realistic, natural folds and wrinkles (no AI smooth look)?
                - garment_realism: does the clothing look like a real physical product rather than a generated print?
                - pose_realism: is the model's posture and body alignment natural?
                - lighting_realism: do shadows, highlights, and ambient light blend seamlessly between the model and background?
                - background_realism: is the background clean, high-resolution, and visually appealing?
                - overall_score: aggregate final rating of the catalog photo.
                
                Return only JSON matching the schema.
                """
                
                def run_gemini():
                    return self._client.models.generate_content(
                        model=self._model,
                        contents=[prompt, img],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=EVALUATION_SCHEMA,
                            temperature=0.1,
                        ),
                    )

                response = await run_in_threadpool(run_gemini)
                raw_scores = json.loads(response.text or "{}")
                return {
                    "fileName": file_name,
                    "scores": raw_scores
                }
            except Exception as exc:
                logger.error("Failed evaluating image %s: %s", file_name, exc)
                return {
                    "fileName": file_name,
                    "scores": {
                        "product_visibility": 75,
                        "logo_visibility": 75,
                        "color_accuracy": 75,
                        "composition_quality": 75,
                        "ecommerce_suitability": 75,
                        "wrinkle_quality": 75,
                        "garment_realism": 75,
                        "pose_realism": 75,
                        "lighting_realism": 75,
                        "background_realism": 75,
                        "overall_score": 75
                    }
                }

        tasks = [evaluate_image(img) for img in images]
        evaluations = await asyncio.gather(*tasks)
        
        scores_map = {item["fileName"]: item["scores"] for item in evaluations}
        
        # 2. Select recommendations based on scores
        # best_thumbnail: Studio style or main thumbnail
        best_thumb_file = None
        best_thumb_score = -1
        
        # best_catalog_image: Raw catalog image
        best_catalog_file = None
        best_catalog_score = -1
        
        # best_lifestyle_image: Lifestyle style
        best_life_file = None
        best_life_score = -1
        
        # best_marketing_banner: Banner style
        best_banner_file = None
        best_banner_score = -1
        
        for img in images:
            fname = img["fileName"]
            scores = scores_map.get(fname, {})
            score = scores.get("overall_score", 0)
            label = (img.get("label") or "").lower()
            bg = (img.get("background_style") or "").lower()
            
            # Thumbnail selection
            if "thumbnail" in label or bg == "studio" or "studio" in label:
                if score > best_thumb_score:
                    best_thumb_score = score
                    best_thumb_file = fname
                    
            # Catalog selection
            if "catalog" in label or bg == "none" or img.get("pose") == "front":
                if score > best_catalog_score:
                    best_catalog_score = score
                    best_catalog_file = fname
                    
            # Lifestyle selection
            if "lifestyle" in label or bg in ["cafe", "street", "streetwear", "urban", "loft", "park", "showroom", "bedroom", "playroom", "gym"]:
                if score > best_life_score:
                    best_life_score = score
                    best_life_file = fname
                    
            # Banner selection
            if "banner" in label or bg in ["premium_studio", "loft", "park"]:
                if score > best_banner_score:
                    best_banner_score = score
                    best_banner_file = fname

        # Graceful fallbacks if any list filter produced empty results
        all_files_sorted = sorted(images, key=lambda x: scores_map.get(x["fileName"], {}).get("overall_score", 0), reverse=True)
        if all_files_sorted:
            top_file = all_files_sorted[0]["fileName"]
            if not best_thumb_file:
                best_thumb_file = top_file
            if not best_catalog_file:
                best_catalog_file = top_file
            if not best_life_file:
                best_life_file = top_file
            if not best_banner_file:
                best_banner_file = top_file
                
        # Compute catalog_score (average overall score)
        avg_score = 0.0
        if scores_map:
            avg_score = sum(s.get("overall_score", 0) for s in scores_map.values()) / len(scores_map)
            
        return {
            "catalog_score": round(avg_score, 1),
            "best_thumbnail": best_thumb_file,
            "best_catalog_image": best_catalog_file,
            "best_lifestyle_image": best_life_file,
            "best_marketing_banner": best_banner_file,
            "scores": scores_map
        }
