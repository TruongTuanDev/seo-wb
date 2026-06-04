import asyncio
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
import builtins

import pytest
from PIL import Image

import fal_client
from app.core.config import Settings
from app.core.errors import AppError
from app.services.product_image_generator import ProductImageGenerator
from app.services.virtual_try_on import VirtualTryOnService, resolve_garment_type, resolve_english_category
from app.services.studio_recommender import recommend_for_product
from app.services.catalog_quality import check_color_similarity, CatalogQualityEngine
from app.schemas.card import ProductInput


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.queue = []

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def get(self, key):
        return self.values.get(key)

    async def rpush(self, key, value):
        self.queue.append((key, value))
        return len(self.queue)

    async def delete(self, key):
        self.values.pop(key, None)
        return 1


def _settings() -> Settings:
    return Settings(
        app_env="test",
        app_secret_key="test-secret-key",
        fal_key="test-fal-key",
        redis_url="redis://localhost:6379/0",
        cloudinary_cloud_name=None,
        cloudinary_api_key=None,
        cloudinary_api_secret=None,
    )


@pytest.mark.anyio
async def test_resolve_garment_type():
    assert resolve_garment_type("pants") == "lower_body"
    assert resolve_garment_type("брюки)...") == "lower_body" # wait, resolved category will match Russian terms
    assert resolve_garment_type("брюки женские") == "lower_body"
    assert resolve_garment_type("Jeans") == "lower_body"
    assert resolve_garment_type("hoodie") == "upper_body"
    assert resolve_garment_type("мужское худи") == "upper_body"
    assert resolve_garment_type("shirt") == "upper_body"
    assert resolve_garment_type("dress") == "full_body"
    assert resolve_garment_type("летнее платье") == "full_body"
    assert resolve_garment_type("set") == "full_body"


@pytest.mark.anyio
async def test_resolve_english_category():
    assert resolve_english_category("шорты") == "shorts"
    assert resolve_english_category("Shorts") == "shorts"
    assert resolve_english_category("худи") == "hoodie"
    assert resolve_english_category("брюки") == "pants"
    assert resolve_english_category("платье") == "dress"
    assert resolve_english_category("unknown") == "clothing"


@pytest.mark.anyio
async def test_try_on_models_listing():
    service = VirtualTryOnService(_settings(), None)
    models = service.get_models()
    assert len(models) == 10
    assert models[0]["id"] == "model_1"
    assert models[0]["gender"] == "Female"


@pytest.mark.anyio
async def test_studio_recommender():
    # 1. Hoodie -> Streetwear background, male gender
    raw_analysis = {"category": "худи", "gender": "мужской", "product_name": "Nike sports hoodie"}
    user_input = ProductInput(category="худи", gender="мужской", note="Cozy sport hoodie")
    recs = recommend_for_product(raw_analysis, user_input)
    assert recs["garmentType"] == "upper_body"
    assert recs["recommendedBackground"] == "streetwear"
    assert recs["recommendedModelGender"] == "male"
    assert recs["recommendedPosePack"] == "fashion"

    # 2. Dress -> Boutique background, female gender
    raw_analysis2 = {"category": "платье", "gender": "женский", "product_name": "Summer dress"}
    user_input2 = ProductInput(category="платье", gender="женский", note="Light summer dress")
    recs2 = recommend_for_product(raw_analysis2, user_input2)
    assert recs2["garmentType"] == "full_body"
    assert recs2["recommendedBackground"] == "boutique"
    assert recs2["recommendedModelGender"] == "female"


@pytest.mark.anyio
async def test_color_similarity():
    # Create two solid color images: red and blue
    red_img = Image.new("RGB", (100, 100), color="red")
    blue_img = Image.new("RGB", (100, 100), color="blue")
    red_img2 = Image.new("RGB", (100, 100), color="red")
    
    red_bytes = BytesIO()
    red_img.save(red_bytes, format="JPEG")
    red_bytes = red_bytes.getvalue()
    
    blue_bytes = BytesIO()
    blue_img.save(blue_bytes, format="JPEG")
    blue_bytes = blue_bytes.getvalue()

    red2_bytes = BytesIO()
    red_img2.save(red2_bytes, format="JPEG")
    red2_bytes = red2_bytes.getvalue()

    # Red vs Red -> high similarity
    sim_high = check_color_similarity(red_bytes, red2_bytes)
    assert sim_high > 0.9

    # Red vs Blue -> low similarity
    sim_low = check_color_similarity(red_bytes, blue_bytes)
    assert sim_low < 0.2


@pytest.mark.anyio
async def test_brand_aware_prompts(monkeypatch):
    service = VirtualTryOnService(_settings(), None)
    
    # 1. Nike branding prompt
    nike_meta = {"brand": "Nike"}
    # We must patch fal_client run_async to check arguments passed
    async def mock_run_async(model_id, arguments):
        assert "Preserve all Nike logos and branding." in arguments["description"]
        return {"image": {"url": "https://cdn.fal.media/vton.png"}}
    monkeypatch.setattr(fal_client, "run_async", mock_run_async)
    await service._run_vton("h", "g", "upper_body", metadata=nike_meta)

    # 2. Adidas branding prompt
    adidas_meta = {"brand": "Adidas"}
    async def mock_run_async_adidas(model_id, arguments):
        assert "Preserve all Adidas stripes and logos." in arguments["description"]
        return {"image": {"url": "https://cdn.fal.media/vton.png"}}
    monkeypatch.setattr(fal_client, "run_async", mock_run_async_adidas)
    await service._run_vton("h", "g", "upper_body", metadata=adidas_meta)


@pytest.mark.anyio
async def test_catalog_quality_scoring(monkeypatch, tmp_path):
    settings = _settings()
    engine = CatalogQualityEngine(settings)
    
    # Mock Gemini Client generate_content
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"product_visibility": 95, "logo_visibility": 90, "color_accuracy": 95, "composition_quality": 88, "ecommerce_suitability": 92, "overall_score": 92}'
    mock_client.models.generate_content.return_value = mock_response
    engine._client = mock_client
    
    # Create mock files
    job_dir = tmp_path / "job"
    output_dir = job_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    img = Image.new("RGB", (10, 10))
    img.save(output_dir / "generated-01.jpg")
    img.save(output_dir / "generated-02.jpg")
    
    images = [
        {"fileName": "generated-01.jpg", "label": "Main Product Thumbnail", "background_style": "studio", "pose": "front"},
        {"fileName": "generated-02.jpg", "label": "Lifestyle Image", "background_style": "streetwear", "pose": "walking"}
    ]
    
    report = await engine.score_catalog_package(images, job_dir)
    assert report["catalog_score"] == 92.0
    assert report["best_thumbnail"] == "generated-01.jpg"
    assert report["best_lifestyle_image"] == "generated-02.jpg"
    assert "generated-01.jpg" in report["scores"]


@pytest.mark.anyio
async def test_virtual_try_on_missing_pose_templates(monkeypatch, tmp_path):
    settings = _settings()
    
    job_id = "test-try-on-no-pose-templates"
    job_dir = tmp_path / "storage" / "image_jobs" / job_id
    input_dir = job_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    
    (input_dir / "front.jpg").write_bytes(b"front_data")
    
    mock_upload_file = MagicMock(return_value="https://cdn.fal.media/uploaded.jpg")
    monkeypatch.setattr(fal_client, "upload_file", mock_upload_file)
    
    async def mock_run_async(model_id, arguments):
        if model_id == "fal-ai/idm-vton":
            return {"image": {"url": "https://cdn.fal.media/vton.png"}}
        elif model_id == "fal-ai/flux/dev/image-to-image":
            return {"images": [{"url": "https://cdn.fal.media/final.png"}]}
        raise ValueError(f"Unknown mock model: {model_id}")
        
    monkeypatch.setattr(fal_client, "run_async", mock_run_async)
    
    async def mock_download_image(self, url):
        return b"mocked_image_bytes"
        
    monkeypatch.setattr(VirtualTryOnService, "_download_image", mock_download_image)
    monkeypatch.setattr(Path, "is_dir", lambda self: False)
    
    # Mock open and exists
    original_open = builtins.open
    def mock_open_fn(file, mode="r", *args, **kwargs):
        fstr = str(file).replace("\\", "/")
        if any(x in fstr for x in ["model1", "model_1", "front.jpg", "back.jpg"]):
            return BytesIO(b"mock_data")
        return original_open(file, mode, *args, **kwargs)
    monkeypatch.setattr(builtins, "open", mock_open_fn)

    # Mock CatalogQualityEngine
    async def mock_score_catalog_package(self, images, job_dir):
        return {"catalog_score": 85.0, "best_thumbnail": "generated-01.jpg"}
    monkeypatch.setattr(CatalogQualityEngine, "score_catalog_package", mock_score_catalog_package)

    redis = FakeRedis()
    service = VirtualTryOnService(settings, redis)
    
    state = {
        "id": job_id,
        "user_id": 1,
        "store_id": 2,
        "draft_id": 3,
        "variant_id": "var-1",
        "variant_index": 0,
        "total": 3,
        "job_type": "try_on",
        "metadata": {
            "model_id": "model_1",
            "background_style": "none",
            "product_category": "hoodie",
            "garment_type": "upper_body"
        }
    }
    
    state_updates = []
    async def save_state_fn(jid, s):
        state_updates.append(s.copy())
        
    attach_draft_mock = MagicMock()
    
    monkeypatch.setattr(service._storage, "save_generated_image", lambda *args, **kwargs: {
        "url": "https://localhost/local.jpg",
        "storage": "local",
        "storageKey": "key",
        "bytes": 100,
        "width": 100,
        "height": 100
    })
    
    monkeypatch.setattr("app.services.virtual_try_on.IMAGE_JOB_STORAGE_DIR", tmp_path / "storage" / "image_jobs")
    
    result = await service.run_try_on_job(
        job_id=job_id,
        db=None,
        state=state,
        save_state_fn=save_state_fn,
        attach_draft_fn=attach_draft_mock
    )
    
    assert result["status"] == "completed"
    assert len(result["images"]) == 3
    assert result["images"][0]["label"] == "Front Catalog"


@pytest.mark.anyio
async def test_virtual_try_on_existing_pose_templates(monkeypatch, tmp_path):
    settings = _settings()
    
    job_id = "test-try-on-with-poses"
    job_dir = tmp_path / "storage" / "image_jobs" / job_id
    input_dir = job_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    
    (input_dir / "front.jpg").write_bytes(b"front_data")
    (input_dir / "back.jpg").write_bytes(b"back_data")
    
    mock_upload_file = MagicMock(return_value="https://cdn.fal.media/uploaded.jpg")
    monkeypatch.setattr(fal_client, "upload_file", mock_upload_file)
    
    async def mock_run_async(model_id, arguments):
        if model_id == "fal-ai/idm-vton":
            return {"image": {"url": "https://cdn.fal.media/vton.png"}}
        elif model_id == "fal-ai/flux/dev/image-to-image":
            return {"images": [{"url": "https://cdn.fal.media/final.png"}]}
        raise ValueError(f"Unknown mock model: {model_id}")
        
    monkeypatch.setattr(fal_client, "run_async", mock_run_async)
    
    async def mock_download_image(self, url):
        return b"mocked_image_bytes"
        
    monkeypatch.setattr(VirtualTryOnService, "_download_image", mock_download_image)
    
    def mock_is_dir(self):
        path_str = str(self).replace("\\", "/")
        if "model_1" in path_str:
            return True
        return False
        
    def mock_exists(self):
        path_str = str(self).replace("\\", "/")
        if "model_1" in path_str and ("front.png" in path_str or "side_45.png" in path_str or "walking.png" in path_str):
            return True
        if "model1.png" in path_str or "model_1.png" in path_str:
            return True
        if "front.jpg" in path_str or "back.jpg" in path_str:
            return True
        return False

    monkeypatch.setattr(Path, "is_dir", mock_is_dir)
    monkeypatch.setattr(Path, "exists", mock_exists)
    
    original_open = builtins.open
    def mock_open_fn(file, mode="r", *args, **kwargs):
        fstr = str(file).replace("\\", "/")
        if any(x in fstr for x in ["model1", "model_1", "front.jpg", "back.jpg"]):
            return BytesIO(b"mock_data")
        return original_open(file, mode, *args, **kwargs)
    monkeypatch.setattr(builtins, "open", mock_open_fn)

    # Mock CatalogQualityEngine
    async def mock_score_catalog_package(self, images, job_dir):
        return {"catalog_score": 90.0, "best_thumbnail": "generated-01.jpg"}
    monkeypatch.setattr(CatalogQualityEngine, "score_catalog_package", mock_score_catalog_package)

    redis = FakeRedis()
    service = VirtualTryOnService(settings, redis)
    
    state = {
        "id": job_id,
        "user_id": 1,
        "store_id": 2,
        "draft_id": 3,
        "variant_id": "var-1",
        "variant_index": 0,
        "total": 5,
        "job_type": "try_on",
        "metadata": {
            "model_id": "model_1",
            "background_style": "none",
            "product_category": "dress",
            "garment_type": "full_body",
            "posePack": "fashion"
        }
    }
    
    state_updates = []
    async def save_state_fn(jid, s):
        state_updates.append(s.copy())
        
    attach_draft_mock = MagicMock()
    
    monkeypatch.setattr(service._storage, "save_generated_image", lambda *args, **kwargs: {
        "url": "https://localhost/local.jpg",
        "storage": "local",
        "storageKey": "key",
        "bytes": 100,
        "width": 100,
        "height": 100
    })
    
    monkeypatch.setattr("app.services.virtual_try_on.IMAGE_JOB_STORAGE_DIR", tmp_path / "storage" / "image_jobs")
    
    result = await service.run_try_on_job(
        job_id=job_id,
        db=None,
        state=state,
        save_state_fn=save_state_fn,
        attach_draft_fn=attach_draft_mock
    )
    
    assert result["status"] == "completed"
    assert len(result["images"]) == 5
    labels = [img["label"] for img in result["images"]]
    assert "Front Catalog" in labels
    assert "Side Catalog" in labels
    assert "Lifestyle" in labels

@pytest.mark.anyio
async def test_florence_category_verification(monkeypatch):
    from app.services.catalog_quality import verify_garment_category_florence
    
    # Mock fal_client.subscribe to return a caption matching the category
    def mock_subscribe(endpoint, arguments):
        assert endpoint == "fal-ai/florence-2-large/caption"
        return {"results": [{"caption": "a woman posing in cozy hoodie sweatshirt"}]}
        
    monkeypatch.setattr(fal_client, "subscribe", mock_subscribe)
    
    res = verify_garment_category_florence("https://mock.url", "hoodie")
    assert res is True
    
    # Test mismatch
    res_mismatch = verify_garment_category_florence("https://mock.url", "pants")
    assert res_mismatch is False

@pytest.mark.anyio
async def test_occupancy_rescaling():
    from app.services.virtual_try_on import check_and_adjust_occupancy
    
    # Create a transparent RGBA image with very low occupancy
    # We fill only 10% of the image (10x10 square in 100x100 canvas)
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    for x in range(45, 55):
        for y in range(45, 55):
            img.putpixel((x, y), (255, 0, 0, 255))
            
    buf = BytesIO()
    img.save(buf, format="PNG")
    low_occupancy_bytes = buf.getvalue()
    
    adjusted_bytes = check_and_adjust_occupancy(low_occupancy_bytes, target_occupancy=0.75)
    
    # Measure occupancy of adjusted
    adjusted_img = Image.open(BytesIO(adjusted_bytes))
    alpha = adjusted_img.getchannel('A')
    non_trans = sum(1 for a in list(alpha.getdata()) if a > 0)
    new_occupancy = non_trans / (adjusted_img.width * adjusted_img.height)
    
    # It should be close to 0.75
    assert abs(new_occupancy - 0.75) < 0.15

def test_crop_and_resize():
    from app.services.catalog_exporter import CatalogExporter
    
    # Create an arbitrary size image, e.g. 1000 x 500
    img = Image.new("RGB", (1000, 500), color="blue")
    
    exporter = CatalogExporter()
    res = exporter.crop_and_resize(img, (900, 1200), 3/4)
    assert res.size == (900, 1200)

@pytest.mark.anyio
async def test_virtual_try_on_validation_retries(monkeypatch, tmp_path):
    settings = _settings()
    settings.enable_image_validation_retry = True
    
    job_id = "test-try-on-retries"
    job_dir = tmp_path / "storage" / "image_jobs" / job_id
    input_dir = job_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    
    (input_dir / "front.jpg").write_bytes(b"front_data")
    
    mock_upload_file = MagicMock(return_value="https://cdn.fal.media/uploaded.jpg")
    monkeypatch.setattr(fal_client, "upload_file", mock_upload_file)
    
    vton_calls = 0
    async def mock_run_async(model_id, arguments):
        nonlocal vton_calls
        if model_id == "fal-ai/idm-vton":
            vton_calls += 1
            return {"image": {"url": "https://cdn.fal.media/vton.png"}}
        elif model_id == "fal-ai/birefnet/v2":
            return {"image": {"url": "https://cdn.fal.media/segmented.png"}}
        elif model_id == "fal-ai/image-editing/background-change":
            return {"image": {"url": "https://cdn.fal.media/bg.png"}}
        elif model_id == "fal-ai/flux/dev/image-to-image":
            return {"images": [{"url": "https://cdn.fal.media/final.png"}]}
        raise ValueError(f"Unknown mock model: {model_id}")
        
    monkeypatch.setattr(fal_client, "run_async", mock_run_async)
    
    async def mock_download_image(self, url):
        # Return a simple 100x100 transparent image
        img = Image.new("RGBA", (100, 100), (0, 0, 0, 100))
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
        
    monkeypatch.setattr(VirtualTryOnService, "_download_image", mock_download_image)
    monkeypatch.setattr(Path, "is_dir", lambda self: False)
    
    # Mock validation checks: face_sim = 0.85 (failing) then 0.95 (passing)
    face_sim_calls = 0
    def mock_check_face_similarity(template_path, generated_bytes):
        nonlocal face_sim_calls
        face_sim_calls += 1
        return 0.85 if face_sim_calls == 1 else 0.95
        
    monkeypatch.setattr("app.services.virtual_try_on.check_face_similarity", mock_check_face_similarity)
    
    # Mock verify_garment_category_florence to return True
    monkeypatch.setattr("app.services.catalog_quality.verify_garment_category_florence", lambda *args: True)
    
    # Mock check_color_similarity to return 0.90
    monkeypatch.setattr("app.services.catalog_quality.check_color_similarity", lambda *args: 0.90)
    
    # Mock open and exists
    original_open = builtins.open
    def mock_open_fn(file, mode="r", *args, **kwargs):
        fstr = str(file).replace("\\", "/")
        if any(x in fstr for x in ["model1", "model_1", "front.jpg", "back.jpg"]):
            return BytesIO(b"mock_data")
        return original_open(file, mode, *args, **kwargs)
    monkeypatch.setattr(builtins, "open", mock_open_fn)

    # Mock CatalogQualityEngine
    async def mock_score_catalog_package(self, images, job_dir):
        return {"catalog_score": 85.0, "best_thumbnail": "generated-01.jpg"}
    monkeypatch.setattr(CatalogQualityEngine, "score_catalog_package", mock_score_catalog_package)

    redis = FakeRedis()
    service = VirtualTryOnService(settings, redis)
    
    state = {
        "id": job_id,
        "user_id": 1,
        "store_id": 2,
        "draft_id": 3,
        "variant_id": "var-1",
        "variant_index": 0,
        "total": 3,
        "job_type": "try_on",
        "metadata": {
            "model_id": "model_1",
            "background_style": "studio",
            "product_category": "hoodie",
            "garment_type": "upper_body"
        }
    }
    
    state_updates = []
    async def save_state_fn(jid, s):
        state_updates.append(s.copy())
        
    attach_draft_mock = MagicMock()
    
    monkeypatch.setattr(service._storage, "save_generated_image", lambda *args, **kwargs: {
        "url": "https://localhost/local.jpg",
        "storage": "local",
        "storageKey": "key",
        "bytes": 100,
        "width": 100,
        "height": 100
    })
    
    monkeypatch.setattr("app.services.virtual_try_on.IMAGE_JOB_STORAGE_DIR", tmp_path / "storage" / "image_jobs")
    
    result = await service.run_try_on_job(
        job_id=job_id,
        db=None,
        state=state,
        save_state_fn=save_state_fn,
        attach_draft_fn=attach_draft_mock
    )
    
    assert result["status"] == "completed"
    # Should have run VTON exactly twice (first attempt failed face similarity, second attempt succeeded)
    assert vton_calls == 2


@pytest.mark.anyio
async def test_simplified_workflow_quantities(monkeypatch, tmp_path):
    from app.services.virtual_try_on import build_simplified_catalog_tasks
    
    # We will run for quantities 3, 5, 8 and check tasks list
    # Let's mock check_exists/is_dir to return True for side_45 and walking to test no fallback first
    def mock_is_dir(self):
        return True
    def mock_exists(self):
        return True
    monkeypatch.setattr(Path, "is_dir", mock_is_dir)
    monkeypatch.setattr(Path, "exists", mock_exists)
    
    # 1. Test quantity 3
    tasks_3 = build_simplified_catalog_tasks(
        model_id="model_1",
        quantity=3,
        selected_style="studio",
        has_back_image=True,
        front_data_uri="front_uri",
        back_data_uri="back_uri",
        model_metadata={"availablePoses": ["front", "side_45", "walking"]}
    )
    assert len(tasks_3) == 3
    assert tasks_3[0]["label"] == "Front Catalog"
    assert tasks_3[1]["label"] == "Product Detail"
    assert tasks_3[2]["label"] == "Banner"
    
    # 2. Test quantity 5
    tasks_5 = build_simplified_catalog_tasks(
        model_id="model_1",
        quantity=5,
        selected_style="studio",
        has_back_image=True,
        front_data_uri="front_uri",
        back_data_uri="back_uri",
        model_metadata={"availablePoses": ["front", "side_45", "walking"]}
    )
    assert len(tasks_5) == 5
    assert tasks_5[0]["label"] == "Front Catalog"
    assert tasks_5[1]["label"] == "Side Catalog"
    assert tasks_5[1]["pose"] == "side_45"
    assert tasks_5[2]["label"] == "Lifestyle"
    assert tasks_5[2]["pose"] == "walking"
    assert tasks_5[3]["label"] == "Product Detail"
    assert tasks_5[4]["label"] == "Banner"

    # 3. Test quantity 8 with back image
    tasks_8_back = build_simplified_catalog_tasks(
        model_id="model_1",
        quantity=8,
        selected_style="studio",
        has_back_image=True,
        front_data_uri="front_uri",
        back_data_uri="back_uri",
        model_metadata={"availablePoses": ["front", "side_45", "walking"]}
    )
    assert len(tasks_8_back) == 8
    assert tasks_8_back[6]["label"] == "Back Detail"
    assert tasks_8_back[6]["type"] == "back_detail"

    # 4. Test quantity 8 without back image (should fallback to Front Detail)
    tasks_8_no_back = build_simplified_catalog_tasks(
        model_id="model_1",
        quantity=8,
        selected_style="studio",
        has_back_image=False,
        front_data_uri="front_uri",
        back_data_uri=None,
        model_metadata={"availablePoses": ["front", "side_45", "walking"]}
    )
    assert len(tasks_8_no_back) == 8
    assert tasks_8_no_back[6]["label"] == "Front Detail"
    assert tasks_8_no_back[6]["type"] == "front_detail"

    # 5. Test pose fallbacks (model lacking side_45 and walking)
    tasks_fallback = build_simplified_catalog_tasks(
        model_id="model_3",
        quantity=5,
        selected_style="studio",
        has_back_image=True,
        front_data_uri="front_uri",
        back_data_uri="back_uri",
        model_metadata={"availablePoses": ["front"]}
    )
    assert len(tasks_fallback) == 5
    assert tasks_fallback[1]["label"] == "Side Catalog"
    assert tasks_fallback[1]["pose"] == "front" # side_45 falls back to front
    assert tasks_fallback[2]["label"] == "Lifestyle"
    assert tasks_fallback[2]["pose"] == "front" # walking falls back to front

