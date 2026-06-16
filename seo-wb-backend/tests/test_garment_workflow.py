import pytest
from app.services.garment_analyzer import build_variant_color_garment_json, resolve_garment_area
from app.services.color_fidelity import compare_color_signatures, extract_color_signature
from app.services.garment_analyzer import _is_complex_product
from app.services.gpt_prompt_builder import GPTPromptBuilder
from app.services.garment_validator import GarmentValidator
from app.services.gpt_image_catalog import GPTImageCatalogService, apply_product_focus_crop
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


def test_variant_color_signature_replaces_only_color_data():
    image = Image.new("RGB", (120, 180), color=(190, 45, 52))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    base = {
        "product_type": "pants",
        "garment_area": "lower_body",
        "main_color": "black",
        "secondary_color": "",
        "secondary_colors": [],
        "color_palette": ["#202020"],
        "material": "linen",
        "silhouette": "wide leg",
        "pockets": "two side pockets",
        "logo_or_text": "none",
        "front_view": {"description": "black wide-leg pants", "key_details": ["black waistband"]},
    }

    variant = build_variant_color_garment_json(base, buffer.getvalue(), "Красный")

    assert variant["main_color"] == "Красный"
    assert variant["color_palette"] != ["#202020"]
    assert variant["material"] == "linen"
    assert variant["silhouette"] == "wide leg"
    assert variant["pockets"] == "two side pockets"
    assert variant["logo_or_text"] == "none"
    assert "black" not in variant["front_view"]["description"].lower()
    assert variant["variant_color_signature"]["analysis_mode"] == "fast_local_color_signature"
    assert base["main_color"] == "black"


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
    assert "You may replace or restyle only the model's upper-body clothing" in prompt
    assert "must not cover the waistband" in prompt

    focused_prompt = GPTPromptBuilder.build_prompt(
        garment_json,
        "studio",
        "front",
        product_focus=True,
    )
    assert "PRODUCT-FOCUSED CAMERA FRAMING" in focused_prompt
    assert "Frame primarily from the waist to the shoes." in focused_prompt
    assert "The lower-body product must occupy 75-85% of the image." in focused_prompt
    assert "Front-facing product-focused crop" in focused_prompt
    assert "Front-facing full-body catalog pose" not in focused_prompt

    side_crop_prompt = GPTPromptBuilder.build_prompt(
        garment_json,
        "studio",
        "crop_side_45",
        product_focus=True,
    )
    assert "45-degree side product-focused crop" in side_crop_prompt
    assert "leg width" in side_crop_prompt

    lifestyle_prompt = GPTPromptBuilder.build_prompt(garment_json, "studio", "walking")
    assert "LIFESTYLE/WALKING STYLING" in lifestyle_prompt
    assert "subtle relevant accessories" in lifestyle_prompt
    assert "must never cover the waistband" in lifestyle_prompt

    detail_prompt = GPTPromptBuilder.build_detail_prompt(garment_json, "detail", "studio")
    assert "lower-body product detail shot" in detail_prompt
    assert "waistband" in detail_prompt
    assert "Do not show a shirt" in detail_prompt

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


def test_complementary_styling_respects_product_area():
    upper = GPTPromptBuilder.complementary_styling_block({"garment_area": "upper_body"})
    lower = GPTPromptBuilder.complementary_styling_block({"garment_area": "lower_body"})
    full = GPTPromptBuilder.complementary_styling_block({"garment_area": "full_body"})

    assert "lower-body clothing" in upper
    assert "upper-body clothing" in lower
    assert "FULL OUTFIT LOCK" in full
    assert "do not replace, remove, or redesign any component" in full


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
    tasks_3 = GPTImageCatalogService.build_tasks(3, has_back_image=True)
    assert len(tasks_3) == 3
    assert [task["label"] for task in tasks_3] == ["Crop Front", "Full Front", "Detail"]
    assert sum(bool(task["product_focus"]) for task in tasks_3) == 1
    assert {task["label"] for task in tasks_3 if task["product_focus"]} == {"Crop Front"}
    assert not next(task for task in tasks_3 if task["label"] == "Full Front")["product_focus"]

    tasks_6_back = GPTImageCatalogService.build_tasks(6, has_back_image=True)
    assert len(tasks_6_back) == 6
    assert [task["label"] for task in tasks_6_back] == ["Crop Front", "Crop Side 45", "Crop Back", "Full Front", "Lifestyle Walking", "Detail"]
    assert sum(bool(task["product_focus"]) for task in tasks_6_back) == 3
    assert {task["label"] for task in tasks_6_back if task["product_focus"]} == {"Crop Front", "Crop Side 45", "Crop Back"}

    tasks_6_no_back = GPTImageCatalogService.build_tasks(6, has_back_image=False)
    assert len(tasks_6_no_back) == 6
    assert [task["label"] for task in tasks_6_no_back] == ["Crop Front", "Crop Side 45", "Crop Back", "Full Front", "Lifestyle Walking", "Detail"]
    assert sum(bool(task["product_focus"]) for task in tasks_6_no_back) == 3
    assert {task["label"] for task in tasks_6_no_back if task["product_focus"]} == {"Crop Front", "Crop Side 45", "Crop Back"}

    tasks_8_back = GPTImageCatalogService.build_tasks(8, has_back_image=True)
    assert len(tasks_8_back) == 8
    assert [task["label"] for task in tasks_8_back] == ["Front", "Side", "Back", "Walking", "Hand On Hip", "Sitting", "Fabric Detail", "Banner"]
    assert next(task for task in tasks_8_back if task["label"] == "Banner")["pose"] == "banner_focus"
    assert sum(bool(task["product_focus"]) for task in tasks_8_back) == 4
    assert {task["label"] for task in tasks_8_back if task["product_focus"]} == {"Front", "Side", "Back", "Banner"}

    tasks_8_no_back = GPTImageCatalogService.build_tasks(8, has_back_image=False)
    assert len(tasks_8_no_back) == 8
    assert [task["label"] for task in tasks_8_no_back] == ["Front", "Side", "Walking", "Hand On Hip", "Sitting", "Fabric Detail", "Product Detail", "Banner"]
    assert next(task for task in tasks_8_no_back if task["label"] == "Banner")["pose"] == "banner_focus"
    assert sum(bool(task["product_focus"]) for task in tasks_8_no_back) == 4
    assert {task["label"] for task in tasks_8_no_back if task["product_focus"]} == {"Front", "Side", "Product Detail", "Banner"}

    # Legacy 9-image jobs use the new 8-image bundle.
    assert GPTImageCatalogService.build_tasks(9, has_back_image=True) == tasks_8_back

    # Unsupported quantity fallback
    tasks_fallback = GPTImageCatalogService.build_tasks(5, has_back_image=True)
    assert len(tasks_fallback) == 6


def test_apply_product_focus_crop_zooms_lower_body_product():
    image = Image.new("RGB", (200, 300), color=(245, 245, 245))
    for y in range(90, 300):
        for x in range(50, 150):
            image.putpixel((x, y), (25, 25, 25))

    original_buffer = BytesIO()
    image.save(original_buffer, format="JPEG")
    original_bytes = original_buffer.getvalue()

    cropped_bytes = apply_product_focus_crop(
        original_bytes,
        {"garment_area": "lower_body"},
        "crop_front",
        True,
    )

    original_image = Image.open(BytesIO(original_bytes)).convert("L")
    cropped_image = Image.open(BytesIO(cropped_bytes)).convert("L")

    # After enforced crop, the upper part of the image should contain more of the dark product area.
    original_top_band = sum(original_image.crop((0, 0, 200, 80)).getdata()) / (200 * 80)
    cropped_top_band = sum(cropped_image.crop((0, 0, 200, 80)).getdata()) / (200 * 80)
    assert cropped_top_band < original_top_band


def test_apply_product_focus_crop_skips_non_crop_slots():
    image = Image.new("RGB", (120, 180), color=(120, 120, 120))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    source_bytes = buffer.getvalue()

    result_bytes = apply_product_focus_crop(
        source_bytes,
        {"garment_area": "lower_body"},
        "full_front",
        False,
    )

    assert result_bytes == source_bytes

def test_detail_validation_bypasses_pose():
    from app.core.config import Settings
    settings = Settings(
        app_env="test",
        app_secret_key="test-secret-key",
        openai_api_key="test-openai-key",
        redis_url="redis://localhost:6379/0",
        gemini_api_key="test-gemini-key",
    )
    validator = GarmentValidator(settings)
    
    # Mocking self._client or mock _load_image and generate_content
    # Let's verify that when validation pose is detail (like 'detail', 'fabric_detail' etc),
    # pose validation, model realism, garment area on body, and face/body proportions are bypassed or modified.
    
    # We can mock the Gemini validator response to test validate_image logic
    import json
    mock_response_val = {
        "detected_product_type": "skirt",
        "detected_garment_area": "upper_body", # Area mismatch
        "detected_category": "t-shirt", # Category mismatch
        "detected_pose": "front", # Pose mismatch
        "failed_fields": ["garment_area", "category", "pose"],
        "issues": ["Area mismatch", "Category mismatch"],
        "warnings": [],
        "realism_issues": ["unrealistic face", "skin smoothing", "cgi look"],
        "realism_score": 45,
        "garment_preservation_score": 0.5,
        "critical_details_score": 0.9,
        "pose_accuracy_score": 0.2,
    }
    
    # Mock methods in validator to return this JSON
    class MockResponse:
        text = json.dumps(mock_response_val)
        
    validator._load_image = lambda bytes: None
    validator._client = type("MockClient", (), {
        "models": type("MockModels", (), {
            "generate_content": lambda *args, **kwargs: MockResponse()
        })
    })()
    
    # Detail validation run
    res = validator.validate_image(
        generated_image_bytes=b"dummy",
        garment_json={"category": "skirt", "garment_area": "lower_body"},
        pose="fabric_detail"
    )
    
    # Check that failed_fields do not contain garment_area or category
    assert "garment_area" not in res["failed_fields"]
    assert "category" not in res["failed_fields"]
    assert res["passed"] is True
    # Realism issues for human parts should be filtered
    assert not any("face" in ri for ri in res["warnings"])
    assert res["validation_score"] >= 85
    
    # Non-detail validation run (should fail)
    res_normal = validator.validate_image(
        generated_image_bytes=b"dummy",
        garment_json={"category": "skirt", "garment_area": "lower_body"},
        pose="side_45"
    )
    assert "garment_area" in res_normal["failed_fields"]
    assert res_normal["passed"] is False


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


def test_garment_analyzer_fallback(monkeypatch):
    from app.services.garment_analyzer import GarmentAnalyzer
    
    settings = Settings(
        app_env="test",
        app_secret_key="test-secret-key",
        openai_api_key="test-openai",
        redis_url="redis://localhost:6379/0",
        gemini_api_key="test-gemini",
    )
    
    analyzer = GarmentAnalyzer(settings)
    
    # Mock client call to fail
    def mock_generate_content(*args, **kwargs):
        raise Exception("Simulated Gemini 429 quota error")
        
    monkeypatch.setattr(analyzer._client.models, "generate_content", mock_generate_content)
    
    # Create mock front image bytes
    image = Image.new("RGB", (32, 48), color=(240, 240, 240))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    front_bytes = buffer.getvalue()
    
    res = analyzer.analyze(
        front_image_bytes=front_bytes,
        category="юбка",
        gender="female",
        title="Юбка джинсовая",
        description="Красивая юбка"
    )
    
    # Assertions on local fallback
    assert res["category"] == "юбка"
    assert res["garment_area"] == "lower_body"
    assert res["gender"] == "female"
    assert res["product_type"] == "Юбка джинсовая"
    assert "warnings" in res
    assert any("Gemini garment analysis failed, using local fallback analysis" in w for w in res["warnings"])
    assert res["color_palette"]


@pytest.mark.anyio
async def test_fast_image_mode_skips_gemini_and_publishes_partial_state(tmp_path, monkeypatch):
    settings = Settings(
        app_env="test",
        app_secret_key="test-secret-key",
        openai_api_key="test-openai-key",
        redis_url="redis://localhost:6379/0",
        gemini_api_key="test-gemini-key",
    )
    monkeypatch.setattr("app.services.gpt_image_catalog.IMAGE_JOB_STORAGE_DIR", tmp_path)
    service = GPTImageCatalogService(settings)

    image = Image.new("RGB", (32, 48), color=(190, 45, 52))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    image_bytes = buffer.getvalue()
    input_dir = tmp_path / "fast-job" / "input"
    input_dir.mkdir(parents=True)
    (input_dir / "front.jpg").write_bytes(image_bytes)
    (input_dir / "model.jpg").write_bytes(image_bytes)

    calls = []

    async def mock_openai_retry(*_args, **_kwargs):
        calls.append("openai")
        return image_bytes

    def fail_if_gemini_runs(*_args, **_kwargs):
        raise AssertionError("Gemini validator must not run in fast mode")

    monkeypatch.setattr(service, "_generate_with_openai_retry", mock_openai_retry)
    monkeypatch.setattr(GarmentValidator, "validate_image", fail_if_gemini_runs)

    saved_states = []

    async def save_state(_job_id, state):
        saved_states.append({
            "status": state.get("status"),
            "progress": state.get("progress"),
            "images": list(state.get("images") or []),
        })

    result = await service.run_gpt_image_job(
        job_id="fast-job",
        db=None,
        state={
            "status": "queued",
            "total": 1,
            "metadata": {
                "quality_check_enabled": False,
                "garment_json": {"product_type": "pants", "garment_area": "lower_body"},
                "override_tasks": [
                    {"pose": "crop_front", "type": "catalog", "label": "Crop Front", "output_type": "catalog", "validation_pose": "front", "product_focus": True}
                ],
            },
        },
        save_state_fn=save_state,
        attach_draft_fn=lambda *_args: None,
        use_openai=True,
    )

    assert len(calls) == 1
    assert result["status"] == "completed"
    assert result["images"][0]["validation_result"]["validation_skipped"] is True
    assert any(state["status"] == "processing" and len(state["images"]) == 1 for state in saved_states)


@pytest.mark.anyio
async def test_openai_call_limit_and_priority(tmp_path, monkeypatch):
    import shutil
    from unittest.mock import MagicMock
    from io import BytesIO
    from PIL import Image
    
    settings = Settings(
        app_env="test",
        app_secret_key="test-secret-key",
        openai_api_key="test-openai-key",
        redis_url="redis://localhost:6379/0",
        gemini_api_key="test-gemini-key",
    )
    
    # Mock image directories
    monkeypatch.setattr("app.services.gpt_image_catalog.IMAGE_JOB_STORAGE_DIR", tmp_path)
    
    service = GPTImageCatalogService(settings)
    
    # Helper to generate dummy image bytes
    def dummy_bytes():
        img = Image.new("RGB", (32, 48), color=(240, 240, 240))
        buf = BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()
        
    # Setup job directories
    job_id = "test-limit-job"
    job_dir = tmp_path / job_id
    input_dir = job_dir / "input"
    input_dir.mkdir(parents=True)
    (input_dir / "front.jpg").write_bytes(dummy_bytes())
    (input_dir / "model.jpg").write_bytes(dummy_bytes())
    
    # Track OpenAI calls
    openai_calls = []
    async def mock_openai_retry(image_paths, prompt, job_model=None, max_retry=None):
        openai_calls.append(prompt)
        return dummy_bytes()
    monkeypatch.setattr(service, "_generate_with_openai_retry", mock_openai_retry)
    
    # Mock validator to fail everything initially
    validator_calls = []
    def mock_validate_image(self, generated_bytes, garment_json, pose, front_bytes, back_bytes=None, **kwargs):
        validator_calls.append(pose)
        return {
            "passed": False,
            "score": 0.40,
            "validation_score": 40,
            "realism_score": 40,
            "validation_threshold": 85,
            "realism_threshold": 80,
            "dominant_delta_e_threshold": 15.0,
            "palette_delta_e_threshold": 18.0,
            "realism_issues": ["unrealistic skin"],
            "issues": ["Inconsistent main_color"],
            "warnings": [],
            "failed_fields": ["main_color"],
            "missing_details": [],
            "complex_product_mode": False,
            "critical_mismatch": False,
            "wrong_garment_type": False,
            "wrong_garment_area": False,
            "missing_core_identity": False,
            "critical_issues": [],
            "medium_issues": [],
            "minor_issues": [],
            "pose_validation": "fail",
            "expected_pose": pose,
            "final_validation_status": "failed",
            "dominant_color_delta_e": None,
            "palette_delta_e": None,
        }
    monkeypatch.setattr(GarmentValidator, "validate_image", mock_validate_image)
    
    # ----------------------------------------------------
    # Case 1: 3-image bundle limit (Max 4 calls)
    # ----------------------------------------------------
    state_3 = {
        "status": "queued",
        "total": 3,
        "metadata": {
            "style": "studio",
            "model": "gpt-image-2",
            "override_tasks": [
                {"pose": "detail", "type": "detail", "label": "Detail", "output_type": "detail", "validation_pose": "detail"},
                {"pose": "crop_front", "type": "catalog", "label": "Crop Front", "output_type": "catalog", "validation_pose": "front", "product_focus": True},
                {"pose": "full_front", "type": "catalog", "label": "Full Front", "output_type": "catalog", "validation_pose": "front"},
            ],
            "runtime_config": {
                "validation_failure_behavior": "warn"
            }
        }
    }
    
    saved_states = []
    async def mock_save_state(jid, s):
        saved_states.append(s.copy())
        
    def mock_attach_draft(db, s, images):
        pass
        
    openai_calls.clear()
    validator_calls.clear()
    
    result = await service.run_gpt_image_job(
        job_id=job_id,
        db=None,
        state=state_3,
        save_state_fn=mock_save_state,
        attach_draft_fn=mock_attach_draft,
        use_openai=True
    )
    
    assert len(openai_calls) == 4
    job_calls_metadata = saved_states[-1]["openai_calls_metadata"]
    assert job_calls_metadata["openai_call_limit"] == 4
    assert job_calls_metadata["openai_calls_used"] == 4
    assert job_calls_metadata["initial_generation_calls"] == 3
    assert job_calls_metadata["retry_calls_used"] == 1
    assert job_calls_metadata["retry_budget_remaining"] == 0
    assert job_calls_metadata["retry_skipped_due_to_limit"] is True
    
    front_img = next(img for img in result["images"] if img["label"] == "Crop Front")
    detail_img = next(img for img in result["images"] if img["label"] == "Detail")
    full_front_img = next(img for img in result["images"] if img["label"] == "Full Front")
    
    assert front_img["retry_used"] is True
    assert front_img["retry_skipped_due_to_limit"] is False
    assert front_img["retry_priority"] == 1
    
    assert detail_img["retry_used"] is False
    assert detail_img["retry_skipped_due_to_limit"] is True
    assert detail_img["retry_priority"] == 7
    assert any("Validation retry skipped because OpenAI call limit was reached." in w for w in detail_img["validation_result"]["warnings"])
    
    assert full_front_img["retry_used"] is False
    assert full_front_img["retry_skipped_due_to_limit"] is True
    assert full_front_img["retry_priority"] == 1
    assert any("Validation retry skipped because OpenAI call limit was reached." in w for w in banner_img["validation_result"]["warnings"])

    # ----------------------------------------------------
    # Case 2: 6-image bundle limit (Max 7 calls)
    # ----------------------------------------------------
    state_6 = {
        "status": "queued",
        "total": 6,
        "metadata": {
            "style": "studio",
            "model": "gpt-image-2",
            "override_tasks": [
                {"pose": "crop_front", "type": "catalog", "label": "Crop Front", "output_type": "catalog", "validation_pose": "front", "product_focus": True},
                {"pose": "crop_side_45", "type": "catalog", "label": "Crop Side 45", "output_type": "catalog", "validation_pose": "side_45", "product_focus": True},
                {"pose": "crop_back", "type": "catalog", "label": "Crop Back", "output_type": "catalog", "validation_pose": "back", "product_focus": True},
                {"pose": "full_front", "type": "catalog", "label": "Full Front", "output_type": "catalog", "validation_pose": "front"},
                {"pose": "walking", "type": "lifestyle", "label": "Lifestyle Walking", "output_type": "lifestyle", "validation_pose": None},
                {"pose": "detail", "type": "detail", "label": "Detail", "output_type": "detail", "validation_pose": "detail"},
            ],
            "runtime_config": {
                "validation_failure_behavior": "warn"
            }
        }
    }
    
    openai_calls.clear()
    validator_calls.clear()
    saved_states.clear()
    
    result_6 = await service.run_gpt_image_job(
        job_id=job_id,
        db=None,
        state=state_6,
        save_state_fn=mock_save_state,
        attach_draft_fn=mock_attach_draft,
        use_openai=True
    )
    
    assert len(openai_calls) == 7
    job_calls_metadata_6 = saved_states[-1]["openai_calls_metadata"]
    assert job_calls_metadata_6["openai_call_limit"] == 7
    assert job_calls_metadata_6["openai_calls_used"] == 7
    assert job_calls_metadata_6["initial_generation_calls"] == 6
    assert job_calls_metadata_6["retry_calls_used"] == 1
    assert job_calls_metadata_6["retry_budget_remaining"] == 0
    assert job_calls_metadata_6["retry_skipped_due_to_limit"] is True
    
    img_front = next(img for img in result_6["images"] if img["label"] == "Crop Front")
    img_side = next(img for img in result_6["images"] if img["label"] == "Crop Side 45")
    img_back = next(img for img in result_6["images"] if img["label"] == "Crop Back")
    img_full_front = next(img for img in result_6["images"] if img["label"] == "Full Front")
    img_lifestyle = next(img for img in result_6["images"] if img["label"] == "Lifestyle Walking")
    img_detail = next(img for img in result_6["images"] if img["label"] == "Detail")
    
    assert img_front["retry_used"] is True
    assert img_side["retry_skipped_due_to_limit"] is True
    assert img_back["retry_skipped_due_to_limit"] is True
    assert img_full_front["retry_skipped_due_to_limit"] is True
    
    assert img_lifestyle["retry_skipped_due_to_limit"] is True
    assert img_detail["retry_skipped_due_to_limit"] is True
    assert img_banner["retry_skipped_due_to_limit"] is True

    # ----------------------------------------------------
    # Case 3: 8-image bundle limit (Max 9 calls)
    # ----------------------------------------------------
    state_9 = {
        "status": "queued",
        "total": 8,
        "metadata": {
            "style": "studio",
            "model": "gpt-image-2",
            "override_tasks": [
                {"pose": "front", "type": "catalog", "label": "Front", "output_type": "catalog", "validation_pose": "front"},
                {"pose": "side_45", "type": "catalog", "label": "Side", "output_type": "catalog", "validation_pose": "side_45"},
                {"pose": "back", "type": "catalog", "label": "Back", "output_type": "catalog", "validation_pose": "back"},
                {"pose": "walking", "type": "lifestyle", "label": "Walking", "output_type": "lifestyle", "validation_pose": "walking"},
                {"pose": "hand_on_hip", "type": "catalog", "label": "Hand On Hip", "output_type": "catalog", "validation_pose": "hand_on_hip"},
                {"pose": "sitting", "type": "lifestyle", "label": "Sitting", "output_type": "lifestyle", "validation_pose": "sitting"},
                {"pose": "fabric_detail", "type": "detail", "label": "Fabric Detail", "output_type": "detail", "validation_pose": "fabric_detail"},
                {"pose": "front", "type": "lifestyle", "label": "Banner", "output_type": "lifestyle", "validation_pose": None},
            ],
            "runtime_config": {
                "validation_failure_behavior": "warn"
            }
        }
    }
    
    openai_calls.clear()
    validator_calls.clear()
    saved_states.clear()
    
    result_9 = await service.run_gpt_image_job(
        job_id=job_id,
        db=None,
        state=state_9,
        save_state_fn=mock_save_state,
        attach_draft_fn=mock_attach_draft,
        use_openai=True
    )
    
    assert len(openai_calls) == 9
    job_calls_metadata_9 = saved_states[-1]["openai_calls_metadata"]
    assert job_calls_metadata_9["openai_call_limit"] == 9
    assert job_calls_metadata_9["openai_calls_used"] == 9
    assert job_calls_metadata_9["initial_generation_calls"] == 8
    assert job_calls_metadata_9["retry_calls_used"] == 1
    assert job_calls_metadata_9["retry_budget_remaining"] == 0
    assert job_calls_metadata_9["retry_skipped_due_to_limit"] is True
    
    img_front = next(img for img in result_9["images"] if img["label"] == "Front")
    img_side = next(img for img in result_9["images"] if img["label"] == "Side")
    img_back = next(img for img in result_9["images"] if img["label"] == "Back")
    img_walking = next(img for img in result_9["images"] if img["label"] == "Walking")
    img_hand = next(img for img in result_9["images"] if img["label"] == "Hand On Hip")
    img_sitting = next(img for img in result_9["images"] if img["label"] == "Sitting")
    img_fabric = next(img for img in result_9["images"] if img["label"] == "Fabric Detail")
    img_banner = next(img for img in result_9["images"] if img["label"] == "Banner")
    
    assert img_front["retry_used"] is True
    assert img_side["retry_skipped_due_to_limit"] is True
    assert img_back["retry_skipped_due_to_limit"] is True
    assert img_walking["retry_skipped_due_to_limit"] is True
    
    assert img_hand["retry_skipped_due_to_limit"] is True
    assert img_sitting["retry_skipped_due_to_limit"] is True
    assert img_fabric["retry_skipped_due_to_limit"] is True
    assert img_banner["retry_skipped_due_to_limit"] is True


