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
from app.services.color_fidelity import ColorSignature, compare_color_signatures, extract_color_signature

logger = logging.getLogger(__name__)

CRITICAL_WEIGHT = 40
MEDIUM_WEIGHT = 15
MINOR_WEIGHT = 5

VALIDATOR_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "detected_product_type": {"type": "STRING"},
        "detected_garment_area": {"type": "STRING"},
        "detected_category": {"type": "STRING"},
        "detected_main_color": {"type": "STRING"},
        "detected_secondary_color": {"type": "STRING"},
        "detected_material": {"type": "STRING"},
        "detected_silhouette": {"type": "STRING"},
        "detected_length": {"type": "STRING"},
        "detected_logo_or_text": {"type": "STRING"},
        "detected_pockets": {"type": "STRING"},
        "detected_seams": {"type": "STRING"},
        "detected_special_details": {"type": "ARRAY", "items": {"type": "STRING"}},
        "detected_pose": {"type": "STRING"},
        "garment_preservation_score": {"type": "NUMBER"},
        "critical_details_score": {"type": "NUMBER"},
        "pose_accuracy_score": {"type": "NUMBER"},
        "realism_score": {"type": "NUMBER"},
        "rhinestones_present": {"type": "BOOLEAN"},
        "embroidery_present": {"type": "BOOLEAN"},
        "logos_preserved": {"type": "BOOLEAN"},
        "distressing_present": {"type": "BOOLEAN"},
        "failed_fields": {"type": "ARRAY", "items": {"type": "STRING"}},
        "issues": {"type": "ARRAY", "items": {"type": "STRING"}},
        "realism_issues": {"type": "ARRAY", "items": {"type": "STRING"}},
        "warnings": {"type": "ARRAY", "items": {"type": "STRING"}}
    },
    "required": [
        "detected_product_type", "detected_garment_area", "detected_category",
        "detected_main_color", "detected_secondary_color", "detected_material", "detected_silhouette",
        "detected_length", "detected_logo_or_text", "detected_pockets", "detected_seams", "detected_special_details", "detected_pose",
        "garment_preservation_score", "critical_details_score", "pose_accuracy_score",
        "realism_score", "rhinestones_present", "embroidery_present", "logos_preserved", "distressing_present", "failed_fields", "issues",
        "realism_issues", "warnings"
    ]
}


class GarmentValidator:
    def __init__(self, settings: Settings):
        if not settings.gemini_api_key:
            raise AppError("missing_gemini_key", "GEMINI_API_KEY is missing.", 500)
        self._settings = settings
        self._model = os.getenv("GEMINI_MODEL") or settings.gemini_model
        self._client = genai.Client(api_key=settings.gemini_api_key)

    def validate_image(
        self,
        generated_image_bytes: bytes,
        garment_json: dict[str, Any],
        pose: str | None = None,
        source_front_image_bytes: bytes | None = None,
        source_back_image_bytes: bytes | None = None,
        *,
        validation_threshold: int | None = None,
        realism_threshold: int | None = None,
        color_threshold_delta_e: float = 15.0,
    ) -> dict[str, Any]:
        try:
            image = self._load_image(generated_image_bytes)
        except Exception as exc:
            raise AppError("invalid_generated_image", "Generated image is invalid/undecodable.", 400) from exc

        expected_area = garment_json.get("garment_area", "").lower().strip()
        expected_category = garment_json.get("category", "").lower().strip()
        complex_product_mode = bool(garment_json.get("complex_product_mode"))
        dominant_threshold, palette_threshold = self._resolve_color_thresholds(garment_json)

        prompt = self._build_prompt(garment_json, pose)

        last_exc: Exception | None = None
        response_text = ""
        for attempt in range(1, 4):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=[prompt, image],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=VALIDATOR_SCHEMA,
                        temperature=0.1,
                    ),
                )
                response_text = response.text
                break
            except Exception as exc:
                last_exc = exc
                logger.warning("Gemini validate attempt %d failed: %s", attempt, exc)
                if attempt < 3:
                    time.sleep(1.5 * attempt)
        else:
            raise AppError(
                "gemini_failed",
                "Gemini validation failed.",
                502,
                {"reason": str(last_exc)[:500]}
            ) from last_exc

        try:
            val_res = json.loads(response_text or "{}")
        except Exception as exc:
            raise AppError(
                "gemini_invalid_json",
                "Gemini returned invalid validation JSON.",
                502,
                {"raw": response_text[:1000]}
            ) from exc

        # ENFORCEMENT RULES:
        is_detail = pose in {"detail", "fabric_detail", "logo_detail", "extra_detail", "product_detail"}
        detected_area = val_res.get("detected_garment_area", "").lower().strip()
        detected_pose = val_res.get("detected_pose", "").lower().strip()
        failed_fields = list(val_res.get("failed_fields", []))
        issues = list(val_res.get("issues", []))
        warnings = list(val_res.get("warnings", []))
        realism_issues = list(val_res.get("realism_issues", []))

        # Check for strict garment area mismatch
        if expected_area and detected_area != expected_area and not is_detail:
            if "garment_area" not in failed_fields:
                failed_fields.append("garment_area")
            msg = f"Garment area mismatch: expected {expected_area}, detected {detected_area}"
            if msg not in issues:
                issues.append(msg)

        # Check category match
        detected_category = val_res.get("detected_category", "").lower().strip()
        if expected_category and expected_category not in detected_category and detected_category not in expected_category and not is_detail:
            # Let's perform basic Russian/English substring matching checks
            # e.g., if expected "юбка" and detected "skirt" or vice versa
            is_compatible = False
            for r_word, e_word in [("юбк", "skirt"), ("плать", "dress"), ("брюк", "pants"), ("джинс", "jeans"), ("шорт", "shorts"), ("футбол", "t-shirt"), ("рубаш", "shirt"), ("худи", "hoodie"), ("куртк", "jacket")]:
                if (r_word in expected_category or e_word in expected_category) and (r_word in detected_category or e_word in detected_category):
                    is_compatible = True
                    break
            
            if not is_compatible:
                if "category" not in failed_fields:
                    failed_fields.append("category")
                msg = f"Garment category mismatch: expected {expected_category}, detected {detected_category}"
                if msg not in issues:
                    issues.append(msg)

        # Rhinestone detection checking
        rhinestone_keywords = {"rhinestone", "crystal", "embellishment", "studs"}
        garment_str_lower = json.dumps(garment_json, ensure_ascii=False).lower()
        requires_embellishment = any(kw in garment_str_lower for kw in rhinestone_keywords)

        rhinestones_missing = False
        if requires_embellishment and not val_res.get("rhinestones_present", False):
            rhinestones_missing = True
            if "critical_details" not in failed_fields:
                failed_fields.append("critical_details")
            msg = "Missing required embellishments (rhinestones, crystals, studs, or embellishments)."
            if msg not in issues:
                issues.append(msg)

        expected_special_details = [str(item).lower() for item in garment_json.get("special_details", []) if str(item).strip()]
        detected_special_details = [str(item).lower() for item in (val_res.get("detected_special_details") or []) if str(item).strip()]
        missing_details: list[str] = []

        if expected_special_details:
            if any("distress" in detail or "ripped" in detail or "wash" in detail for detail in expected_special_details) and not val_res.get("distressing_present", False):
                if "critical_details" not in failed_fields:
                    failed_fields.append("critical_details")
                issues.append("Missing required distressing or wash pattern details.")
                missing_details.append("distressing/wash pattern")
            if any("embroid" in detail for detail in expected_special_details) and not val_res.get("embroidery_present", False):
                if "critical_details" not in failed_fields:
                    failed_fields.append("critical_details")
                issues.append("Missing required embroidery details.")
                missing_details.append("embroidery")
            if any("logo" in detail or "brand" in detail for detail in expected_special_details) and not val_res.get("logos_preserved", False):
                if "logo_or_text" not in failed_fields:
                    failed_fields.append("logo_or_text")
                issues.append("Missing or distorted logo/branding details.")
                missing_details.append("logo/text")
            for detail in expected_special_details:
                if any(keyword in detail for keyword in ("pocket", "seam")) and not any(keyword in " ".join(detected_special_details) for keyword in detail.split()):
                    field = "pockets" if "pocket" in detail else "seams"
                    if field not in failed_fields:
                        failed_fields.append(field)
                    issues.append(f"Missing required {field} detail: {detail}.")
                    missing_details.append(detail)
            if any("rhinestone" in detail or "crystal" in detail or "stud" in detail or "embellishment" in detail for detail in expected_special_details) and not val_res.get("rhinestones_present", False):
                if "critical_details" not in failed_fields:
                    failed_fields.append("critical_details")
                issues.append("Missing required rhinestones, crystals, studs or embellishments.")
                missing_details.append("rhinestones/crystals/studs")

        expected_pose = (pose or "").lower().strip()
        pose_mismatch = bool(expected_pose and detected_pose and expected_pose != detected_pose) and not is_detail

        source_image_bytes = source_back_image_bytes if pose == "back" and source_back_image_bytes else source_front_image_bytes
        color_metrics = {
            "dominant_color_delta_e": None,
            "palette_delta_e": None,
        }
        major_color_shift = False
        slight_color_variation = False
        denim_family_drift = False
        variant_reference_signature = _variant_color_reference_signature(garment_json)
        if source_image_bytes or variant_reference_signature:
            reference_signature = variant_reference_signature or extract_color_signature(source_image_bytes, garment_json.get("garment_area"))
            generated_signature = extract_color_signature(generated_image_bytes, garment_json.get("garment_area"))
            color_metrics = compare_color_signatures(reference_signature, generated_signature)
            if color_metrics["dominant_color_delta_e"] > dominant_threshold:
                major_color_shift = True
                color_target = "target variant color" if variant_reference_signature else "source product"
                msg = f"Dominant garment color drift from {color_target} is too high (DeltaE {color_metrics['dominant_color_delta_e']}, threshold {dominant_threshold})."
                if msg not in issues:
                    issues.append(msg)
            elif color_metrics["dominant_color_delta_e"] > max(dominant_threshold * 0.7, dominant_threshold - 6):
                slight_color_variation = True
            if color_metrics["palette_delta_e"] > palette_threshold:
                major_color_shift = True
                color_target = "target variant color" if variant_reference_signature else "source product"
                msg = f"Garment palette drift from {color_target} is too high (DeltaE {color_metrics['palette_delta_e']}, threshold {palette_threshold})."
                if msg not in issues:
                    issues.append(msg)
            elif color_metrics["palette_delta_e"] > max(palette_threshold * 0.7, palette_threshold - 6):
                slight_color_variation = True
            if _is_denim_reference(garment_json):
                source_name = reference_signature.dominant_name.lower()
                generated_name = generated_signature.dominant_name.lower()
                if ("blue" in source_name and "grey" in generated_name) or ("light blue" in source_name and generated_signature.palette_rgb and _is_dark_palette(generated_signature.palette_rgb)):
                    denim_family_drift = True
                    major_color_shift = True
                    if "Denim color family drift detected: blue/light denim changed into grey or dark denim." not in issues:
                        issues.append("Denim color family drift detected: blue/light denim changed into grey or dark denim.")
                    missing_details.append("denim color family")
                if any("wash" in item for item in expected_special_details) and color_metrics["palette_delta_e"] > max(12.0, palette_threshold - 5):
                    if "Denim wash pattern changed too much and no longer matches the source." not in issues:
                        issues.append("Denim wash pattern changed too much and no longer matches the source.")
                    missing_details.append("wash pattern")

        # Realism checks
        realism_score = float(val_res.get("realism_score", 100))
        effective_realism_threshold = max(0, min(100, int(realism_threshold if realism_threshold is not None else 80)))
        
        if is_detail:
            realism_issues = []
            realism_score = 100

        realism_artifact_issue = realism_score < max(55, effective_realism_threshold - 20)
        moderate_realism_issue = realism_score < effective_realism_threshold and not realism_artifact_issue
        realism_notes: list[str] = []
        for ri in realism_issues:
            normalized = str(ri).strip()
            if not normalized:
                continue
            note = normalized.lower()
            if any(keyword in note for keyword in {"cgi", "distorted", "malformed", "artifact", "anatom", "hands"}):
                moderate_realism_issue = True
                realism_notes.append(normalized)
            else:
                realism_notes.append(normalized)

        garment_preservation = float(val_res.get("garment_preservation_score", 1.0))
        critical_details = float(val_res.get("critical_details_score", 1.0))
        pose_accuracy = float(val_res.get("pose_accuracy_score", 1.0))
        if is_detail:
            pose_accuracy = 1.0
            failed_fields = [f for f in failed_fields if f not in {"garment_area", "category", "silhouette", "length"}]

        wrong_garment_area = "garment_area" in failed_fields
        wrong_garment_type = "category" in failed_fields
        major_silhouette_change = ("silhouette" in failed_fields) and garment_preservation < 0.65
        wrong_garment_length = ("length" in failed_fields) and garment_preservation < 0.75
        missing_major_logo = "logo_or_text" in failed_fields
        missing_core_identity = bool(
            rhinestones_missing
            or missing_details
            or wrong_garment_length
            or major_silhouette_change
            or missing_major_logo
        )
        critical_mismatch = wrong_garment_area or wrong_garment_type or major_color_shift or missing_core_identity

        critical_issues: list[str] = []
        medium_issues: list[str] = []
        minor_issues: list[str] = []

        if wrong_garment_type:
            critical_issues.append("Wrong product type.")
        if wrong_garment_area:
            critical_issues.append("Wrong garment area.")
        if major_color_shift:
            critical_issues.append(
                "Major color shift from target variant color."
                if variant_reference_signature
                else "Major color shift from source product."
            )
        if major_silhouette_change:
            critical_issues.append("Major silhouette change from source garment.")
        if wrong_garment_length:
            critical_issues.append("Garment length does not match the source.")
        if missing_major_logo:
            critical_issues.append("Major logo or branding detail is missing.")
        for detail in list(dict.fromkeys(missing_details)):
            critical_issues.append(f"Missing core detail: {detail}.")

        if pose_mismatch:
            medium_issues.append(f"Pose mismatch: expected {expected_pose}, detected {detected_pose or 'unknown'}.")
        if slight_color_variation and not major_color_shift:
            medium_issues.append("Slight garment color variation from the source.")
        if ("silhouette" in failed_fields and not major_silhouette_change) or pose_accuracy < 0.8:
            medium_issues.append("Minor silhouette or pose presentation variation.")
        if any("wash" in item for item in expected_special_details) and "wash pattern" in missing_details and not denim_family_drift:
            medium_issues.append("Moderate denim wash variation.")
        if moderate_realism_issue:
            medium_issues.append("Moderate realism issue detected.")

        for note in realism_notes:
            lower_note = note.lower()
            if any(keyword in lower_note for keyword in {"smooth skin", "skin smoothing", "beauty retouch", "lighting", "studio lighting", "hair", "expression", "background", "wrinkle"}):
                minor_issues.append(note)
            elif note not in medium_issues:
                minor_issues.append(note)
        for warning in warnings:
            if warning not in minor_issues and warning not in medium_issues and warning not in critical_issues:
                minor_issues.append(warning)
        if realism_score >= effective_realism_threshold and realism_issues:
            for ri in realism_issues:
                if ri not in minor_issues:
                    minor_issues.append(ri)

        effective_validation_threshold = max(0, min(100, int(validation_threshold if validation_threshold is not None else 85)))
        validation_score = max(
            0,
            100 - (len(critical_issues) * CRITICAL_WEIGHT) - (len(list(dict.fromkeys(medium_issues))) * MEDIUM_WEIGHT) - (len(list(dict.fromkeys(minor_issues))) * MINOR_WEIGHT),
        )
        passed = validation_score >= effective_validation_threshold and not critical_mismatch
        final_validation_status = "passed" if passed else "failed_validation"

        combined_warnings = list(dict.fromkeys([*medium_issues, *minor_issues]))
        pose_validation = "pass" if not pose_mismatch else "warning"

        return {
            "passed": passed,
            "score": validation_score / 100.0,
            "validation_score": validation_score,
            "realism_score": realism_score,
            "validation_threshold": effective_validation_threshold,
            "realism_threshold": effective_realism_threshold,
            "dominant_delta_e_threshold": dominant_threshold,
            "palette_delta_e_threshold": palette_threshold,
            "realism_issues": realism_notes,
            "issues": list(dict.fromkeys(critical_issues)),
            "warnings": combined_warnings,
            "failed_fields": list(dict.fromkeys([field for field in failed_fields if field in {"category", "garment_area", "main_color", "color_palette", "length", "critical_details", "logo_or_text", "silhouette"}])),
            "missing_details": list(dict.fromkeys(missing_details)),
            "complex_product_mode": complex_product_mode,
            "critical_mismatch": critical_mismatch,
            "wrong_garment_type": wrong_garment_type,
            "wrong_garment_area": wrong_garment_area,
            "missing_core_identity": missing_core_identity,
            "critical_issues": list(dict.fromkeys(critical_issues)),
            "medium_issues": list(dict.fromkeys(medium_issues)),
            "minor_issues": list(dict.fromkeys(minor_issues)),
            "pose_validation": pose_validation,
            "expected_pose": expected_pose or None,
            "final_validation_status": final_validation_status,
            "detected_product_type": val_res.get("detected_product_type"),
            "detected_garment_area": val_res.get("detected_garment_area"),
            "detected_category": val_res.get("detected_category"),
            "detected_main_color": val_res.get("detected_main_color"),
            "detected_material": val_res.get("detected_material"),
            "detected_silhouette": val_res.get("detected_silhouette"),
            "detected_length": val_res.get("detected_length"),
            "detected_logo_or_text": val_res.get("detected_logo_or_text"),
            "detected_secondary_color": val_res.get("detected_secondary_color"),
            "detected_pockets": val_res.get("detected_pockets"),
            "detected_seams": val_res.get("detected_seams"),
            "detected_special_details": val_res.get("detected_special_details") or [],
            "detected_pose": val_res.get("detected_pose"),
            "dominant_color_delta_e": color_metrics["dominant_color_delta_e"],
            "palette_delta_e": color_metrics["palette_delta_e"],
        }

    @staticmethod
    def _resolve_color_thresholds(garment_json: dict[str, Any]) -> tuple[float, float]:
        if _is_denim_reference(garment_json):
            return 22.0, 25.0
        return 15.0, 18.0

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
    def _build_prompt(garment_json: dict[str, Any], pose: str | None = None) -> str:
        ref_json_str = json.dumps(garment_json, ensure_ascii=False, indent=2)
        variant_color_signature = garment_json.get("variant_color_signature") or {}
        variant_color_instruction = ""
        if isinstance(variant_color_signature, dict) and variant_color_signature:
            variant_color_instruction = (
                "\nVariant color validation mode:\n"
                "- The source product reference may be an older colorway.\n"
                "- Validate generated color against garment_json.main_color and garment_json.variant_color_signature, not against the old source image color.\n"
                "- Do not mark color as failed merely because it differs from the source reference image.\n"
            )

        # Visibility-aware instructions
        pose_instruction = ""
        is_detail = pose in {"detail", "fabric_detail", "logo_detail", "extra_detail", "product_detail"}
        if is_detail:
            pose_instruction = (
                f"The generated image is a product-only close-up detail shot ('{pose}').\n"
                "- There is NO model, face, or body in the image.\n"
                "- DO NOT validate or require garment_area on body, pose accuracy, model realism, face, or body proportions.\n"
                "- Set detected_pose to match the expected pose exactly, and pose_accuracy_score to 1.0.\n"
                "- Evaluate ONLY the product attributes visible in the close-up (color, material, texture, logo/text, embroidery, rhinestones, distressing, seams, pockets, closures).\n"
            )
        elif pose:
            pose_instruction = f"The generated image depicts the model in the '{pose}' pose.\n"
            if pose in {"front", "side_45", "walking", "hand_on_hip", "sitting"}:
                pose_instruction += (
                    "- Only validate details visible from the front or side.\n"
                    "- DO NOT require or validate back-only attributes (e.g., back pocket, rear patch, back logo, back zipper/seam).\n"
                    "- If back details are missing or not visible, do NOT count it as a failure.\n"
                )
            elif pose in {"back"}:
                pose_instruction += (
                    "- Only validate details visible from the back.\n"
                    "- DO NOT require or validate front-only attributes (e.g., front pocket, chest logo, front prints/zippers) if they are not visible from the back.\n"
                )

        # Rhinestone detection instruction
        rhinestone_keywords = {"rhinestone", "crystal", "embellishment", "studs"}
        garment_str_lower = json.dumps(garment_json, ensure_ascii=False).lower()
        requires_embellishment = any(kw in garment_str_lower for kw in rhinestone_keywords)

        embellishment_instruction = ""
        if requires_embellishment:
            embellishment_instruction = (
                "CRITICAL: The reference garment specification requires embellishments (rhinestones, crystals, embellishments, or studs).\n"
                "- You MUST check if these rhinestones, crystals, studs, or embellishments are visible on the garment.\n"
                "- Set 'rhinestones_present' to true if they are visible, and false otherwise.\n"
                "- If they are missing (e.g., embellished denim becomes plain denim), this is a critical detail mismatch.\n"
            )
        else:
            embellishment_instruction = (
                "- Set 'rhinestones_present' to false unless the image unexpectedly contains them.\n"
            )

        return f"""
You are a strict fashion QA catalog image validator.
Analyze the uploaded generated catalog image and compare it to the reference garment JSON:

Reference Garment Specification:
{ref_json_str}

{variant_color_instruction}
{pose_instruction}
{embellishment_instruction}

Tasks:
1. Examine the model wearing the garment in the image.
2. Determine:
   - detected_product_type (e.g. "long_denim_skirt")
   - detected_garment_area (must be exactly: "upper_body", "lower_body", or "full_body")
   - detected_category (e.g. "skirt")
   - detected_main_color
   - detected_material
   - detected_silhouette
   - detected_length
   - detected_logo_or_text
   - detected_pose (the pose of the model in the image, e.g. "front", "back", "side_45", etc.)
3. Compare the image with the reference specification:
   - Identify critical failed fields: category, garment_area, main_color, color_palette, material, silhouette, length, pockets, seams, logo_or_text, critical_details (e.g. rhinestones, embroidery, distressing). Append these to 'failed_fields' if there is a mismatch.
   - Note: Silhouette, minor seam variations, and subtle fit differences are warning-only. Do NOT add them to 'failed_fields' or 'issues'. Instead, add them to 'warnings'.
   - List explanations/mismatch details for critical fields in 'issues'.
   - List explanations for warning-only fields in 'warnings'.
   - Explicitly compare main color, secondary color, material, silhouette, length, pockets, seams, distressing, rhinestones, embroidery and logos.
4. Score the following dimensions from 0.0 (completely incorrect) to 1.0 (perfect):
   - garment_preservation_score: how well the main attributes (category, garment_area, main_color, length) are preserved.
   - critical_details_score: how well critical details (logos, patterns, rhinestones if applicable) are preserved.
   - pose_accuracy_score: whether the model pose matches the requested pose '{pose or "any"}'.
5. Evaluate image realism and assign a realism_score between 0 and 100 (where 100 is completely realistic and 0 is entirely CGI/cartoon).
   - Detect CGI-like face, cartoon skin, over-smoothed model, unrealistic body proportions, or artificial lighting.
   - Deduct heavily (20-30 points) for each realism issue found.
   - List all detected realism issues in 'realism_issues'.
6. Return the JSON object matching the schema.
""".strip()


def _is_denim_reference(garment_json: dict[str, Any]) -> bool:
    payload = json.dumps(garment_json, ensure_ascii=False).lower()
    return "denim" in payload or "jeans" in payload or "джин" in payload


def _is_dark_palette(palette: list[tuple[int, int, int]]) -> bool:
    if not palette:
        return False
    brightness = sum((r + g + b) / 3 for r, g, b in palette) / len(palette)
    return brightness < 120


def _variant_color_reference_signature(garment_json: dict[str, Any]) -> ColorSignature | None:
    signature = garment_json.get("variant_color_signature") or {}
    if not isinstance(signature, dict):
        return None

    palette_hex = [str(item).strip() for item in signature.get("palette_hex") or [] if str(item).strip()]
    dominant_hex = str(signature.get("dominant_hex") or "").strip()
    if dominant_hex and dominant_hex not in palette_hex:
        palette_hex.insert(0, dominant_hex)
    if not palette_hex:
        return None

    palette_rgb: list[tuple[int, int, int]] = []
    normalized_hex: list[str] = []
    for item in palette_hex:
        rgb = _parse_hex_color(item)
        if rgb is None:
            continue
        normalized_hex.append("#{:02X}{:02X}{:02X}".format(*rgb))
        palette_rgb.append(rgb)

    if not palette_rgb:
        return None

    return ColorSignature(
        dominant_hex=normalized_hex[0],
        dominant_name=str(signature.get("dominant_name") or garment_json.get("main_color") or "variant color"),
        palette_hex=normalized_hex,
        palette_rgb=palette_rgb,
    )


def _parse_hex_color(value: str) -> tuple[int, int, int] | None:
    text = str(value or "").strip().lstrip("#")
    if len(text) != 6:
        return None
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except ValueError:
        return None
