import json
from app.core.config import Settings
from app.services.garment_validator import GarmentValidator

settings = Settings(
    app_env="test",
    app_secret_key="test-secret-key",
    openai_api_key="test-openai-key",
    redis_url="redis://localhost:6379/0",
    gemini_api_key="test-gemini-key",
)
validator = GarmentValidator(settings)

mock_response_val = {
    "detected_product_type": "skirt",
    "detected_garment_area": "upper_body",
    "detected_category": "t-shirt",
    "detected_pose": "front",
    "failed_fields": ["garment_area", "category", "pose"],
    "issues": ["Area mismatch", "Category mismatch"],
    "warnings": [],
    "realism_issues": ["unrealistic face", "skin smoothing", "cgi look"],
    "realism_score": 45,
    "garment_preservation_score": 0.5,
    "critical_details_score": 0.9,
    "pose_accuracy_score": 0.2,
}

class MockResponse:
    text = json.dumps(mock_response_val)
    
validator._load_image = lambda bytes: None
validator._client = type("MockClient", (), {
    "models": type("MockModels", (), {
        "generate_content": lambda *args, **kwargs: MockResponse()
    })
})()

res = validator.validate_image(
    generated_image_bytes=b"dummy",
    garment_json={"category": "skirt", "garment_area": "lower_body"},
    pose="fabric_detail"
)

print(json.dumps(res, indent=2))
