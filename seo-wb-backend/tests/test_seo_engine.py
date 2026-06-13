from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db
from app.core.config import Settings
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import Base
from app.main import app
from app.models.admin import AdminAiSettings
from app.models.card import CardDraft, CardJob
from app.models.store import Store
from app.models.user import User
from app.schemas.card import CardUploadGroup, ImageAnalysis, ProductInput, SeoInputs, Variant
from app.services.card_flow import CardFlowService
from app.services.card_payload_enricher import CardPayloadEnricher
from app.services.product_copy_policy import build_seo_title, cleanup_title
from app.services.seo_content_validator import SeoContentValidator
from app.services.seo_keyword_planner import SeoKeywordPlanner


def test_keyword_plan_generation():
    plan = SeoKeywordPlanner.build_plan(
        category="Джинсы",
        subject_name="Джинсы",
        brand=None,
        gender="женские",
        analysis=ImageAnalysis(category="Джинсы", material="хлопок", color="голубой", fit_type="широкие"),
        user_input=ProductInput(
            seo_inputs=SeoInputs(
                fit="широкие",
                color="голубой",
                primary_keyword_override="женские джинсы широкие",
                secondary_keywords=["джинсы с высокой посадкой", "широкие джинсы"],
            )
        ),
        confirmed_attributes={"color": "голубой", "fit": "широкие"},
        wb_characteristics=[{"name": "Цвет"}],
        product_family_policy={"family": "bottoms"},
    )

    assert plan["primary_keyword"] == "женские джинсы широкие"
    assert "широкие джинсы" in [item.casefold() for item in plan["secondary_keywords"]]
    assert "женские" in [token.casefold() for token in plan["must_have_entities"]]


def test_title_formula_includes_product_type_and_primary_keyword():
    title_payload = build_seo_title(
        "Джинсы",
        "женские",
        {"fit": "широкие", "color": "голубые", "season": "летние"},
        {"primary_keyword": "джинсы женские широкие", "secondary_keywords": ["голубые джинсы"]},
    )

    assert "Джинсы" in title_payload["title"]
    assert title_payload["used_primary_keyword"] is True


def test_duplicate_title_word_cleanup():
    cleaned = cleanup_title("Джинсы джинсы женские широкие широкие голубые", "Джинсы", None, None)
    assert cleaned.casefold().count("джинсы") == 1
    assert cleaned.casefold().count("широкие") == 1


def test_description_below_600_chars_fails_validation():
    result = SeoContentValidator.validate(
        title="Джинсы женские широкие",
        description="Короткое описание про джинсы.",
        seo_keyword_plan={
            "primary_keyword": "джинсы женские широкие",
            "secondary_keywords": ["голубые джинсы", "джинсы с высокой посадкой", "широкие джинсы"],
            "long_tail_keywords": [],
            "forbidden_claims": [],
        },
        confirmed_attributes={"composition": "хлопок", "fit": "широкие", "purpose": "повседневная"},
        inferred_attributes={},
        min_chars=600,
        max_chars=900,
        auto_fix=False,
    )

    assert result["valid"] is False
    assert any("shorter than 600" in issue for issue in result["issues"])


def test_forbidden_claims_are_detected():
    result = SeoContentValidator.validate(
        title="Оригинал джинсы женские",
        description="Это оригинал и 100% гарантия качества для каждой покупки." + " текст" * 120,
        seo_keyword_plan={
            "primary_keyword": "джинсы женские",
            "secondary_keywords": ["голубые джинсы", "широкие джинсы", "джинсы на каждый день"],
            "long_tail_keywords": [],
            "forbidden_claims": ["оригинал", "100% гарантия"],
        },
        confirmed_attributes={"composition": "хлопок"},
        inferred_attributes={},
        auto_fix=False,
    )

    assert any("Forbidden claim detected" in issue for issue in result["issues"])


def test_missing_primary_keyword_lowers_score():
    result = SeoContentValidator.validate(
        title="Широкие голубые брюки",
        description=("Голубые брюки для повседневной носки, прогулок и удобного образа. " * 20).strip(),
        seo_keyword_plan={
            "primary_keyword": "джинсы женские широкие",
            "secondary_keywords": ["голубые джинсы", "джинсы с высокой посадкой", "широкие джинсы"],
            "long_tail_keywords": [],
            "forbidden_claims": [],
        },
        confirmed_attributes={"composition": "хлопок", "fit": "широкие", "purpose": "повседневная"},
        inferred_attributes={},
        auto_fix=False,
    )
    scorecard = SeoContentValidator.build_scorecard(
        title="Широкие голубые брюки",
        description=("Голубые брюки для повседневной носки, прогулок и удобного образа. " * 20).strip(),
        seo_keyword_plan={
            "primary_keyword": "джинсы женские широкие",
            "secondary_keywords": ["голубые джинсы", "джинсы с высокой посадкой", "широкие джинсы"],
        },
        validator_result=result,
        confirmed_attributes={"composition": "хлопок"},
        inferred_attributes={},
    )

    assert scorecard["seo_score"] < 85


def test_attribute_confidence_separates_confirmed_and_low_confidence():
    enricher = CardPayloadEnricher(
        [
            {"charcID": 1, "name": "Состав", "maxCount": 1},
            {"charcID": 2, "name": "Цвет", "maxCount": 1},
            {"charcID": 3, "name": "Сезон", "maxCount": 1},
        ]
    )
    confidence = enricher.build_attribute_confidence(
        subject_id=11,
        user_input=ProductInput(seo_inputs=SeoInputs(material="хлопок")),
        analysis=ImageAnalysis(material="хлопок", color="синий", season="лето"),
    )

    assert confidence["confirmed_attributes"]["composition"] == "хлопок"
    assert "color" in confidence["low_confidence_attributes"]
    assert "season" in confidence["low_confidence_attributes"]


def test_existing_generation_schema_works_without_seo_inputs():
    payload = ProductInput(category="Джинсы", note="базовая модель")
    assert payload.seo_inputs is None


def test_apply_seo_validation_returns_score_and_issues():
    service = CardFlowService.__new__(CardFlowService)
    result = service._apply_seo_validation(
        [{"variants": [{"title": "Джинсы женские широкие", "description": "Короткое описание", "vendorCode": "A"}]}],
        seo_keyword_plan={
            "primary_keyword": "джинсы женские широкие",
            "secondary_keywords": ["голубые джинсы", "джинсы с высокой посадкой", "широкие джинсы"],
            "long_tail_keywords": [],
            "forbidden_claims": [],
        },
        attribute_confidence={"confirmed_attributes": {"composition": "хлопок"}, "inferred_attributes": {}},
        runtime_settings=type("Runtime", (), {"description_min_chars": 600, "description_max_chars": 900})(),
    )

    assert result["seo_score"] >= 0
    assert result["issues"]


@pytest.fixture()
def seo_client(tmp_path):
    _ = (Store, CardDraft, CardJob, AdminAiSettings)
    engine = create_engine(f"sqlite:///{tmp_path / 'seo-test.db'}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    settings = Settings(
        app_env="test",
        app_secret_key="test-secret-key",
        database_url=f"sqlite:///{tmp_path / 'seo-test.db'}",
        cookie_secure=False,
        auth_rate_limit_requests=100,
        global_rate_limit_requests=1000,
    )

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_settings():
        return settings

    @asynccontextmanager
    async def no_lifespan(_: object):
        yield

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = no_lifespan
    with TestClient(app, headers={"user-agent": "pytest-browser"}) as client:
        yield client, SessionLocal, settings
    app.router.lifespan_context = original_lifespan
    app.dependency_overrides.clear()


def _login_seo_client(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return client.cookies.get("seller_wb_csrf") or ""


def _seed_draft(SessionLocal, *, seo_enabled: bool = True) -> int:
    with SessionLocal() as db:
        user = User(name="Seller", email="seller@example.com", password_hash=hash_password("password123"))
        db.add(user)
        db.flush()
        store = Store(user_id=user.id, name="Demo Store", wb_api_key_encrypted="x")
        db.add(store)
        db.flush()
        db.add(
            AdminAiSettings(
                id=1,
                seo_engine_enabled=seo_enabled,
                seo_min_score=70,
                description_min_chars=600,
                description_max_chars=900,
                seo_repair_max_attempts=1,
                require_primary_keyword_in_title=True,
                warn_low_confidence_attributes=True,
            )
        )
        draft = CardDraft(
            user_id=user.id,
            store_id=store.id,
            status="draft",
            subject_id=12,
            vendor_code="SKU-1",
            analysis={
                "category": "Джинсы",
                "product_name": "Джинсы женские",
                "material": "хлопок",
                "color": "голубой",
                "gender": "женские",
                "fit_type": "широкие",
                "product_input": {"category": "Джинсы", "brand": None, "seo_inputs": {"material": "хлопок"}},
                "seo_keyword_plan": {
                    "primary_keyword": "джинсы женские широкие",
                    "secondary_keywords": ["голубые джинсы", "джинсы с высокой посадкой", "широкие джинсы"],
                    "long_tail_keywords": [],
                    "forbidden_claims": [],
                },
                "seo_score": {"seo_score": 42, "issues": ["Description shorter than 600 characters"]},
                "seo_issues": ["Description shorter than 600 characters"],
                "attribute_confidence": {
                    "confirmed_attributes": {"purpose": "повседневная"},
                    "inferred_attributes": {"season": "лето", "pattern": "принт"},
                    "missing_attributes": [],
                    "low_confidence_attributes": ["season", "pattern"],
                },
            },
            card_payload=[
                {
                    "subjectID": 12,
                    "variants": [
                        {
                            "vendorCode": "SKU-1",
                            "title": "Короткий заголовок",
                            "description": "Короткое описание",
                            "brand": "Нет бренда",
                            "dimensions": {"length": 30, "width": 20, "height": 5, "weightBrutto": 0.5},
                            "characteristics": [{"id": 1, "value": ["хлопок"]}],
                            "sizes": [{"techSize": "S", "wbSize": "42", "skus": []}],
                            "media": {"cover": "/cards/media/1/cover.jpg", "local_files": [{"url": "/cards/media/1/cover.jpg", "photoNumber": 1}]},
                        }
                    ],
                }
            ],
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)
        return draft.id


def test_improve_seo_endpoint_raises_score_and_keeps_media(seo_client, monkeypatch):
    client, SessionLocal, _ = seo_client
    draft_id = _seed_draft(SessionLocal)
    csrf = _login_seo_client(client, "seller@example.com", "password123")

    async def fake_charcs(*args, **kwargs):
        return [{"charcID": 1, "name": "Состав", "required": True, "popular": True, "maxCount": 1}]

    monkeypatch.setattr("app.api.routes.cards._draft_charcs", fake_charcs)
    response = client.post(f"/api/v1/cards/drafts/{draft_id}/seo/improve", headers={"x-csrf-token": csrf})

    assert response.status_code == 200
    body = response.json()
    assert body["seo_score"]["seo_score"] >= 70
    assert body["card_payload"][0]["variants"][0]["media"]["cover"] == "/cards/media/1/cover.jpg"


def test_regenerate_copy_changes_text_but_not_images(seo_client, monkeypatch):
    client, SessionLocal, _ = seo_client
    draft_id = _seed_draft(SessionLocal)
    csrf = _login_seo_client(client, "seller@example.com", "password123")

    async def fake_charcs(*args, **kwargs):
        return [{"charcID": 1, "name": "Состав", "required": True, "popular": True, "maxCount": 1}]

    monkeypatch.setattr("app.api.routes.cards._draft_charcs", fake_charcs)
    before = client.get(f"/api/v1/cards/drafts/{draft_id}").json()
    response = client.post(f"/api/v1/cards/drafts/{draft_id}/seo/regenerate-copy", headers={"x-csrf-token": csrf})

    assert response.status_code == 200
    after = response.json()
    assert after["card_payload"][0]["variants"][0]["title"] != before["card_payload"][0]["variants"][0]["title"]
    assert after["card_payload"][0]["variants"][0]["media"] == before["card_payload"][0]["variants"][0]["media"]


def test_accept_low_confidence_attributes_moves_fields_correctly(seo_client, monkeypatch):
    client, SessionLocal, _ = seo_client
    draft_id = _seed_draft(SessionLocal)
    csrf = _login_seo_client(client, "seller@example.com", "password123")

    async def fake_charcs(*args, **kwargs):
        return [
            {"charcID": 1, "name": "Состав", "required": True, "popular": True, "maxCount": 1},
            {"charcID": 2, "name": "Сезон", "required": False, "popular": True, "maxCount": 1},
        ]

    monkeypatch.setattr("app.api.routes.cards._draft_charcs", fake_charcs)
    response = client.post(
        f"/api/v1/cards/drafts/{draft_id}/seo/accept-low-confidence-attributes",
        headers={"x-csrf-token": csrf},
        json={"attribute_keys": ["season"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert "season" not in body["attribute_confidence"]["low_confidence_attributes"]
    assert body["analysis"]["accepted_low_confidence_attributes"] == ["season"]


def test_endpoints_are_backward_compatible_without_seo_inputs(seo_client, monkeypatch):
    client, SessionLocal, _ = seo_client
    draft_id = _seed_draft(SessionLocal)
    with SessionLocal() as db:
        draft = db.get(CardDraft, draft_id)
        draft.analysis["product_input"] = {"category": "Джинсы"}
        db.commit()
    csrf = _login_seo_client(client, "seller@example.com", "password123")

    async def fake_charcs(*args, **kwargs):
        return [{"charcID": 1, "name": "Состав", "required": True, "popular": True, "maxCount": 1}]

    monkeypatch.setattr("app.api.routes.cards._draft_charcs", fake_charcs)
    response = client.post(f"/api/v1/cards/drafts/{draft_id}/seo/improve", headers={"x-csrf-token": csrf})
    assert response.status_code == 200


def test_admin_settings_respected_when_seo_disabled(seo_client):
    client, SessionLocal, _ = seo_client
    draft_id = _seed_draft(SessionLocal, seo_enabled=False)
    csrf = _login_seo_client(client, "seller@example.com", "password123")
    response = client.post(f"/api/v1/cards/drafts/{draft_id}/seo/improve", headers={"x-csrf-token": csrf})
    assert response.status_code == 403


@pytest.mark.anyio
async def test_generate_draft_stores_seo_score_in_analysis(monkeypatch):
    from app.services import card_flow as card_flow_module

    class FakeGeminiAnalyzer:
        def __init__(self, settings):
            pass

        def analyze(self, image_bytes, user_input):
            return ImageAnalysis(
                category="Джинсы",
                product_name="Джинсы женские",
                material="хлопок",
                color="голубой",
                gender="женские",
                fit_type="широкие",
            )

    class FakeGarmentAnalyzer:
        def __init__(self, settings):
            pass

        def analyze(self, *args, **kwargs):
            return {"garment_area": "lower_body"}

    class FakeCardGenerator:
        def __init__(self, settings):
            pass

        def generate(self, *args, **kwargs):
            return [
                CardUploadGroup(
                    subjectID=12,
                    variants=[
                        Variant(
                            vendorCode="SKU-1",
                            title="Джинсы женские широкие",
                            description="Удобные джинсы для повседневной носки." + " текст" * 120,
                            brand="Нет бренда",
                            dimensions={"length": 30, "width": 20, "height": 5, "weightBrutto": 0.5},
                            characteristics=[{"id": 1, "value": ["хлопок"]}],
                            sizes=[{"techSize": "S", "wbSize": "42", "skus": []}],
                        )
                    ],
                )
            ]

    class FakeWb:
        async def get_subject_charcs(self, subject_id, locale="ru"):
            return [{"charcID": 1, "name": "Состав", "required": True, "popular": True, "maxCount": 1}]

        async def get_seasons(self, locale="ru"):
            return ["лето", "зима"]

        async def get_tnved(self, subject_id, locale="ru"):
            return []

    class FakeDb:
        def __init__(self):
            self.saved = None

        def add(self, item):
            self.saved = item

        def commit(self):
            return None

        def refresh(self, item):
            item.id = 1

    async def fake_run_ai_limited(settings, fn):
        return await fn()

    async def fake_run_in_threadpool(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(card_flow_module, "GeminiAnalyzer", FakeGeminiAnalyzer)
    monkeypatch.setattr(card_flow_module, "GarmentAnalyzer", FakeGarmentAnalyzer)
    monkeypatch.setattr(card_flow_module, "CardGenerator", FakeCardGenerator)
    monkeypatch.setattr(card_flow_module, "run_ai_limited", fake_run_ai_limited)
    monkeypatch.setattr(card_flow_module, "run_in_threadpool", fake_run_in_threadpool)
    monkeypatch.setattr(card_flow_module, "get_effective_ai_runtime_settings", lambda db, settings: type("Runtime", (), {
        "description_min_chars": 600,
        "description_max_chars": 900,
    })())

    service = CardFlowService.__new__(CardFlowService)
    service._settings = Settings(app_env="test", app_secret_key="test-secret-key")
    service._db = FakeDb()
    service._user = type("User", (), {"id": 7})()
    service._store = type("Store", (), {"id": 3})()
    service._wb = FakeWb()

    async def fake_resolve_subject(user_input, analysis):
        return {"subjectID": 12, "subjectName": "Джинсы"}

    service._resolve_subject = fake_resolve_subject

    draft = await service.generate_draft([b"img"], ProductInput(category="Джинсы"))

    assert draft.analysis["seo_score"]["seo_score"] >= 0
    assert "seo_keyword_plan" in draft.analysis
