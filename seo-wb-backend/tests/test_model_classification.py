import pytest
from sqlalchemy.orm import Session
from app.models.admin import ModelTemplate
from app.services.admin_runtime import list_public_model_templates
from app.core.config import Settings

@pytest.mark.anyio
async def test_list_public_models_filter_by_garment_type(monkeypatch):
    # Standard settings
    settings = Settings(
        app_env="production",  # avoid built-in fallback trigger
        app_secret_key="test-secret",
        openai_api_key="test-key",
        redis_url="redis://localhost:6379/0",
    )
    
    # We will mock the database query to return predefined model templates
    models = [
        ModelTemplate(
            id="m_dress",
            name="Model Dress",
            gender="female",
            body_type="slim",
            status="active",
            quality_status="approved",
            garment_type="dress"
        ),
        ModelTemplate(
            id="m_pants",
            name="Model Pants",
            gender="female",
            body_type="slim",
            status="active",
            quality_status="approved",
            garment_type="pants"
        ),
        ModelTemplate(
            id="m_shirt",
            name="Model Shirt",
            gender="male",
            body_type="average",
            status="active",
            quality_status="approved",
            garment_type="shirt"
        ),
    ]
    
    class FakeScalars:
        def __init__(self, data):
            self.data = data
        def all(self):
            return self.data
            
    class FakeSession:
        def scalars(self, select_statement):
            # Inspect the compiled query parameters for garment_type
            params = select_statement.compile().params
            # Extract key that ends with 'garment_type_1' or matches garment_type
            g_type = None
            for k, v in params.items():
                if "garment_type" in k:
                    g_type = v
                    break
            
            filtered = models
            if g_type:
                filtered = [m for m in models if m.garment_type == g_type]
            return FakeScalars(filtered)

    db = FakeSession()
    
    # 1. Retrieve all active models without filter
    res_all = list_public_model_templates(db, settings)
    assert len(res_all) == 3
    assert res_all[0]["garmentType"] == "dress"
    assert res_all[1]["garmentType"] == "pants"
    assert res_all[2]["garmentType"] == "shirt"
    
    # 2. Retrieve models filtered by garment_type='dress'
    res_dress = list_public_model_templates(db, settings, garment_type="dress")
    assert len(res_dress) == 1
    assert res_dress[0]["id"] == "m_dress"
    assert res_dress[0]["garmentType"] == "dress"
    
    # 3. Retrieve models filtered by garment_type='pants'
    res_pants = list_public_model_templates(db, settings, garment_type="pants")
    assert len(res_pants) == 1
    assert res_pants[0]["id"] == "m_pants"
    assert res_pants[0]["garmentType"] == "pants"
