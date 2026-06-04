import pytest
import shutil
from pathlib import Path
from unittest.mock import MagicMock
from io import BytesIO
from PIL import Image

from app.core.config import Settings
from app.services.gpt_image_catalog import GPTImageCatalogService
from app.services.garment_validator import GarmentValidator

def _image_bytes() -> bytes:
    image = Image.new("RGB", (32, 48), color=(240, 240, 240))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()

@pytest.mark.anyio
async def test_gemini_validation_fallback_on_api_error(tmp_path, monkeypatch):
    # Setup test configuration
    settings = Settings(
        app_env="test",
        app_secret_key="test-secret-key",
        openai_api_key="test-openai-key",
        redis_url="redis://localhost:6379/0",
        gemini_api_key="test-gemini-key",
    )
    
    # Mock image directories
    monkeypatch.setattr("app.services.gpt_image_catalog.IMAGE_JOB_STORAGE_DIR", tmp_path)
    
    # Initialize service
    service = GPTImageCatalogService(settings)
    
    job_id = "test-fallback-job"
    job_dir = tmp_path / job_id
    input_dir = job_dir / "input"
    input_dir.mkdir(parents=True)
    
    # Write mock images
    front_path = input_dir / "front.jpg"
    front_path.write_bytes(_image_bytes())
    
    model_path = input_dir / "model.jpg"
    model_path.write_bytes(_image_bytes())
    
    # Mock OpenAI generation method to return mock image bytes without hitting API
    async def mock_openai_retry(*args, **kwargs):
        return _image_bytes()
    monkeypatch.setattr(service, "_generate_with_openai_retry", mock_openai_retry)
    
    # Mock GarmentValidator.validate_image to raise simulated Gemini 503 error
    def mock_validate_image_exception(*args, **kwargs):
        raise Exception("Simulated Gemini 503 error - high demand")
    monkeypatch.setattr(GarmentValidator, "validate_image", mock_validate_image_exception)
    
    # Setup state
    state = {
        "status": "queued",
        "total": 1,
        "metadata": {
            "style": "studio",
            "model": "gpt-image-2",
            "override_tasks": [
                {"pose": "front", "type": "catalog", "label": "Front Catalog", "output_type": "catalog", "validation_pose": "front"}
            ],
            "runtime_config": {
                "validation_failure_behavior": "block" # even with block behavior, Gemini failure should NOT fail the job
            }
        }
    }
    
    saved_states = []
    async def mock_save_state(jid, s):
        saved_states.append(s.copy())
        
    def mock_attach_draft(db, s, images):
        pass
        
    # Execute job
    result = await service.run_gpt_image_job(
        job_id=job_id,
        db=None,
        state=state,
        save_state_fn=mock_save_state,
        attach_draft_fn=mock_attach_draft,
        use_openai=True
    )
    
    # Assertions
    assert result["status"] == "completed_with_warnings"
    assert result["progress"] == 1
    assert result["error"] == "Gemini tạm thời không khả dụng, vui lòng tự duyệt ảnh."
    
    # Inspect generated image details
    generated_img = result["images"][0]
    val_res = generated_img["validation_result"]
    
    assert val_res["passed"] is True
    assert val_res["validation_score"] == 70
    assert val_res["realism_score"] == 80
    assert any("Gemini tạm thời không khả dụng, vui lòng tự duyệt ảnh (Lỗi: Simulated Gemini 503 error - high demand)" in w for w in val_res["warnings"])
