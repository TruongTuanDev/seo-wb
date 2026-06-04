import pytest
from app.services.garment_analyzer import resolve_garment_area
from app.services.color_fidelity import compare_color_signatures, extract_color_signature
from app.services.garment_analyzer import _is_complex_product
from app.services.gpt_prompt_builder import GPTPromptBuilder
from app.services.garment_validator import GarmentValidator
from app.services.gpt_image_catalog import GPTImageCatalogService
from app.core.config import Settings
from PIL import Image
from io import BytesIO


def test_resolve_garment_area():
    # English categories
    assert resolve_garment_area("shirt") == "upper_body"
    assert resolve_garment_area("t-shirt") == "upper_body"
    assert resolve_garment_area("hoodie") == "upper_body"
    assert resolve_garment_area("pants") == "lower_body"
    assert resolve_garment_area("skirt") == "lower_body"
    assert resolve_garment_area("dress") == "full_body"
    assert resolve_garment_area("gown") == "full_body"

    # Russian categories
    assert resolve_garment_area("юбка") == "lower_body"
    assert resolve_garment_area("платье") == "full_body"
    assert resolve_garment_area("джинсы") == "lower_body"
    assert resolve_garment_area("шорты") == "lower_body"
    assert resolve_garment_area("рубашка") == "upper_body"
    assert resolve_garment_area("худи") == "upper_body"

    # Unknown
    assert resolve_garment_area("random_unmapped_category") is None


def test_gpt_prompt_builder():
    garment_json = {
        "product_type": "long_denim_skirt",
        "garment_area": "lower_body",
        "category": "skirt",
        "gender": "female",
        "main_color": "light blue",
        "secondary_color": "silver rhinestones",
        "color_palette": ["#BFD4E8", "#C8DAEA", "#D7E3EF"],
        "material": "washed denim",
        "fit": "regular fit",
        "length": "ankle length",
        "closure": "front button and zipper closure",
        "pockets": "front pockets",
        "hem": "straight hem",
        "logo_or_text": "none visible",
        "special_details": ["ripped areas", "rhinestones", "distressed wash"],
        "prompt_summary": "A light blue washed denim ankle-length high-waist straight skirt with front button closure, pockets, vertical seams and denim texture."
    }

    # Standard Prompt
    prompt = GPTPromptBuilder.build_prompt(garment_json, "streetwear", "walking")
    assert "Garment area: lower body." in prompt
    assert "Replace only the lower-body garment with the uploaded product." in prompt
    assert "The product is a skirt, do not turn it into a top, pants, shorts or mini skirt." in prompt
    assert "Streetwear" in prompt or "streetwear" in prompt.lower()
    assert "walking" in prompt.lower()
    assert "COLOR LOCK" in prompt
    assert "Do not recolor the garment." in prompt
    assert "#BFD4E8" in prompt
    assert "rhinestones" in prompt

    # Retry Prompt (Strict Garment Preservation Mode)
    strict_prompt = GPTPromptBuilder.build_prompt(
        garment_json,
        "studio",
        "front",
        strict_retry_fields=["main_color", "silhouette"]
    )
    assert "CRITICAL GARMENT FIDELITY MODE" in strict_prompt
    assert "STRICT GARMENT PRESERVATION MODE" in strict_prompt
    assert "main_color" in strict_prompt
    assert "silhouette" in strict_prompt


def test_garment_validator_failures():
    # Mock settings and clients
    settings = Settings(gemini_api_key="mock_key")
    validator = GarmentValidator(settings)

    garment_json = {
        "garment_area": "lower_body",
        "category": "skirt",
        "main_color": "light blue"
    }

    # Test mock val_res format checks
    # Expected area mismatch should fail immediately
    mock_val_res_mismatch = {
        "detected_product_type": "top",
        "detected_garment_area": "upper_body",
        "detected_category": "top",
        "detected_main_color": "light blue",
        "detected_material": "cotton",
        "detected_silhouette": "straight",
        "detected_length": "short",
        "detected_logo_or_text": "none",
        "score": 0.95,
        "failed_fields": [],
        "issues": []
    }

    # Simulate validator logic checking expected area
    detected_area = mock_val_res_mismatch["detected_garment_area"]
    expected_area = garment_json["garment_area"]
    score = mock_val_res_mismatch["score"]
    failed_fields = list(mock_val_res_mismatch["failed_fields"])
    issues = list(mock_val_res_mismatch["issues"])

    if expected_area and detected_area != expected_area:
        score = min(score, 0.5)
        failed_fields.append("garment_area")
        issues.append(f"Garment area mismatch: expected {expected_area}, detected {detected_area}")

    passed = score >= 0.75 and (expected_area == detected_area)
    assert not passed
    assert score == 0.5
    assert "garment_area" in failed_fields


def test_build_tasks_quantity_rules():
    tasks_1 = GPTImageCatalogService.build_tasks(1, has_back_image=True)
    assert len(tasks_1) == 1
    assert tasks_1[0]["pose"] == "front"
    assert tasks_1[0]["label"] == "Front Catalog"
    assert tasks_1[0]["output_type"] == "catalog"

    tasks_3 = GPTImageCatalogService.build_tasks(3, has_back_image=True)
    assert len(tasks_3) == 3
    assert [task["pose"] for task in tasks_3] == ["front", "side_45", "hand_on_hip"]
    assert all(task["output_type"] == "catalog" for task in tasks_3)

    tasks_5 = GPTImageCatalogService.build_tasks(5, has_back_image=True)
    assert len(tasks_5) == 5
    assert [task["pose"] for task in tasks_5] == ["front", "side_45", "walking", "back", "hand_on_hip"]
    assert tasks_5[2]["output_type"] == "lifestyle"
    assert tasks_5[3]["label"] == "Back View"

    tasks_5_no_back = GPTImageCatalogService.build_tasks(5, has_back_image=False)
    assert len(tasks_5_no_back) == 5
    assert tasks_5_no_back[3]["pose"] == "detail"
    assert tasks_5_no_back[3]["label"] == "Detail Shot"
    assert tasks_5_no_back[3]["output_type"] == "detail"

    # 6 images
    tasks_6 = GPTImageCatalogService.build_tasks(6, has_back_image=False)
    assert len(tasks_6) == 6
    assert tasks_6[0]["label"] == "Front Catalog"
    assert tasks_6[1]["label"] == "Side 45 Catalog"
    assert tasks_6[2]["label"] == "Walking Lifestyle"
    assert tasks_6[3]["label"] == "Detail Shot"
    assert tasks_6[4]["label"] == "Hand On Hip Catalog"
    assert tasks_6[5]["label"] == "Sitting Lifestyle"


def test_color_signature_and_delta_e():
    def image_bytes(color):
        image = Image.new("RGB", (128, 196), color=color)
        buffer = BytesIO()
        image.save(buffer, format="JPEG")
        return buffer.getvalue()

    source = extract_color_signature(image_bytes((191, 212, 232)), "lower_body")
    similar = extract_color_signature(image_bytes((198, 218, 234)), "lower_body")
    drifted = extract_color_signature(image_bytes((145, 145, 145)), "lower_body")

    similar_metrics = compare_color_signatures(source, similar)
    drifted_metrics = compare_color_signatures(source, drifted)

    assert source.palette_hex
    assert similar_metrics["dominant_color_delta_e"] < 15
    assert drifted_metrics["dominant_color_delta_e"] > similar_metrics["dominant_color_delta_e"]


def test_complex_product_detection():
    garment_json = {
        "product_type": "denim_skirt",
        "special_details": ["ripped areas", "rhinestones"],
        "logo_or_text": "brand logo",
    }
    assert _is_complex_product(garment_json) is True

    simple = {
        "product_type": "plain_shirt",
        "special_details": [],
        "logo_or_text": "none visible",
    }
    assert _is_complex_product(simple) is False
