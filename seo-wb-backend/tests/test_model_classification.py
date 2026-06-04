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


@pytest.mark.anyio
async def test_select_auto_model_template():
    from app.api.routes.cards import select_auto_model_template

    # Mock database templates
    models = [
        ModelTemplate(
            id="m_pants_female",
            name="Female Pants Model",
            gender="female",
            body_type="slim",
            status="active",
            quality_status="approved",
            garment_type="pants"
        ),
        ModelTemplate(
            id="m_pants_male",
            name="Male Pants Model",
            gender="male",
            body_type="slim",
            status="active",
            quality_status="approved",
            garment_type="pants"
        ),
        ModelTemplate(
            id="m_dress_female",
            name="Female Dress Model",
            gender="female",
            body_type="slim",
            status="active",
            quality_status="approved",
            garment_type="dress"
        ),
    ]

    class FakeScalars:
        def __init__(self, data):
            self.data = data
        def first(self):
            return self.data[0] if self.data else None

    class FakeSession:
        def scalars(self, select_statement):
            # Inspect the compiled query parameters
            params = select_statement.compile().params
            
            # Simple simulation of query parameters
            # Find gender and garment_type params
            gender_val = "female"
            g_type_val = None
            
            # Iterate and look up parameters
            for k, v in params.items():
                if "gender" in k:
                    gender_val = v
                elif "garment_type" in k:
                    if v != "full_body":
                        g_type_val = v

            # Filter logic matching our select statement behavior
            filtered = [
                m for m in models
                if m.gender == gender_val and (g_type_val is None or m.garment_type == g_type_val or m.garment_type == "full_body")
            ]
            return FakeScalars(filtered)

    db = FakeSession()

    # 1. Pants category, male gender (e.g. from Russian description characteristics)
    garment_json = {"category": "брюки", "gender": "мужской"}
    analysis = {"category": "брюки", "gender": "мужской"}
    res = select_auto_model_template(db, garment_json, analysis, selected_model_gender=None)
    assert res is not None
    assert res.id == "m_pants_male"

    # 2. Dress category, female gender
    garment_json = {"category": "платье", "gender": "женский"}
    analysis = {"category": "платье", "gender": "женский"}
    res = select_auto_model_template(db, garment_json, analysis, selected_model_gender=None)
    assert res is not None
    assert res.id == "m_dress_female"

    # 3. Fallback check: Shoes category (no matching model in list), male gender
    # Should fall back to matching male gender models (m_pants_male)
    garment_json = {"category": "обувь", "gender": "мужской"}
    analysis = {"category": "обувь", "gender": "мужской"}
    res = select_auto_model_template(db, garment_json, analysis, selected_model_gender=None)
    assert res is not None
    assert res.id == "m_pants_male"

