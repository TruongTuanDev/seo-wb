from io import BytesIO
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db
from app.core.config import Settings, get_settings
from app.core.security import hash_password
from app.db.session import Base
from app.main import app
from app.models.admin import AdminAiSettings, AdminAuditLog, GeneratedImageJob, ModelTemplate, UsageRecord
from app.models.billing import CreditTransaction, PaymentTransaction, PlatformAuditLog, SubscriptionPlan, UserSubscription
from app.models.card import CardDraft, CardJob
from app.models.store import Store
from app.models.user import User
from app.services.billing_foundation import IMAGE_JOB_QUEUE_HIGH, IMAGE_JOB_QUEUE_LOW
from app.services.usage_plans import apply_plan_defaults
from app.services.usage_reset_scheduler import run_monthly_usage_reset_cycle


class FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.queue: list[tuple[str, str]] = []

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


def _image_bytes() -> bytes:
    image = Image.new("RGB", (32, 48), color=(240, 240, 240))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture()
def client(tmp_path):
    _ = (
        Store,
        CardDraft,
        CardJob,
        ModelTemplate,
        GeneratedImageJob,
        UsageRecord,
        AdminAiSettings,
        AdminAuditLog,
        CreditTransaction,
        PaymentTransaction,
        PlatformAuditLog,
        SubscriptionPlan,
        UserSubscription,
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'admin-integration.db'}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    settings = Settings(
        app_env="test",
        app_secret_key="test-secret-key",
        database_url=f"sqlite:///{tmp_path / 'admin-integration.db'}",
        cookie_secure=False,
        auth_rate_limit_requests=100,
        global_rate_limit_requests=1000,
        openai_api_key="test-openai-key",
        redis_url="redis://localhost:6379/0",
    )

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_settings():
        return settings

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings
    with TestClient(app, headers={"user-agent": "pytest-browser"}) as test_client:
        yield test_client, SessionLocal, settings
    app.dependency_overrides.clear()


def _login(client: TestClient, email: str, password: str, endpoint: str = "/api/v1/auth/login") -> dict[str, str]:
    response = client.post(endpoint, json={"email": email, "password": password})
    assert response.status_code == 200
    csrf_cookie_name = "seller_wb_admin_csrf" if endpoint.startswith("/api/v1/admin/") else "seller_wb_csrf"
    csrf = client.cookies.get(csrf_cookie_name)
    return {"x-csrf-token": csrf} if csrf else {}


def _seed_user(
    db,
    *,
    email: str,
    role: str = "user",
    plan_type: str = "free",
    monthly_quota: int = 100,
    used_quota: int = 0,
    monthly_cost_limit: float | None = None,
    used_cost: float = 0.0,
    quota_reset_at: datetime | None = None,
    last_quota_reset_at: datetime | None = None,
) -> User:
    user = User(
        name=email.split("@")[0].title(),
        email=email,
        password_hash=hash_password("password123"),
        role=role,
        used_quota=used_quota,
        used_cost=used_cost,
    )
    apply_plan_defaults(user, plan_type)
    user.monthly_quota = monthly_quota
    if monthly_cost_limit is not None:
        user.monthly_cost_limit = monthly_cost_limit
    user.quota_reset_at = quota_reset_at or user.quota_reset_at
    user.last_quota_reset_at = last_quota_reset_at or user.last_quota_reset_at
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seed_store_and_draft(db, user_id: int) -> tuple[int, int]:
    store = Store(user_id=user_id, name="Demo Store", wb_api_key_encrypted="encrypted")
    db.add(store)
    db.commit()
    db.refresh(store)
    draft = CardDraft(
        user_id=user_id,
        store_id=store.id,
        status="draft",
        subject_id=1,
        vendor_code="SKU-1",
        analysis={"category": "dress"},
        card_payload=[],
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return store.id, draft.id


def test_normal_user_cannot_access_admin_apis(client):
    test_client, SessionLocal, _ = client
    with SessionLocal() as db:
        _seed_user(db, email="seller@example.com", role="user")

    _login(test_client, "seller@example.com", "password123")
    response = test_client.get("/api/v1/admin/users")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "admin_forbidden"


def test_admin_can_crud_model_templates(client):
    test_client, SessionLocal, _ = client
    with SessionLocal() as db:
        _seed_user(db, email="admin@example.com", role="admin")

    headers = _login(test_client, "admin@example.com", "password123", endpoint="/api/v1/admin/login")
    payload_json = (
        '{"id":"model_live","name":"Live Model","gender":"female","body_type":"average",'
        '"height_cm":170,"weight_kg":60,"is_ai_generated":false,"status":"active","quality_status":"draft","poses":{"front":"/front.png"}}'
    )

    create = test_client.post("/api/v1/admin/models", data={"payload_json": payload_json}, headers=headers)
    assert create.status_code == 200
    assert create.json()["id"] == "model_live"

    items = test_client.get("/api/v1/admin/models").json()
    assert any(item["id"] == "model_live" for item in items)

    update_json = (
        '{"id":"model_live","name":"Updated Model","gender":"female","body_type":"athletic",'
        '"height_cm":171,"weight_kg":61,"is_ai_generated":true,"status":"inactive","quality_status":"approved","poses":{"front":"/front.png"}}'
    )
    update = test_client.put("/api/v1/admin/models/model_live", data={"payload_json": update_json}, headers=headers)
    assert update.status_code == 200
    assert update.json()["name"] == "Updated Model"
    assert update.json()["status"] == "inactive"

    delete = test_client.delete("/api/v1/admin/models/model_live", headers=headers)
    assert delete.status_code == 204


def test_inactive_model_is_hidden_from_public_model_selector(client):
    test_client, SessionLocal, _ = client
    with SessionLocal() as db:
        db.add(
            ModelTemplate(
                id="model_active",
                name="Active Model",
                gender="female",
                body_type="average",
                status="active",
                quality_status="approved",
                reference_image_url="/storage/admin_models/model_active/reference.png",
                poses={"front": "/storage/admin_models/model_active/front.png"},
            )
        )
        db.add(
            ModelTemplate(
                id="model_inactive",
                name="Inactive Model",
                gender="female",
                body_type="average",
                status="inactive",
                quality_status="approved",
                reference_image_url="/storage/admin_models/model_inactive/reference.png",
                poses={"front": "/storage/admin_models/model_inactive/front.png"},
            )
        )
        db.commit()

    response = test_client.get("/api/v1/models")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert "model_active" in ids
    assert "model_inactive" not in ids


def test_rejected_model_is_hidden_from_public_model_selector(client):
    test_client, SessionLocal, _ = client
    with SessionLocal() as db:
        db.add(
            ModelTemplate(
                id="model_rejected",
                name="Rejected Model",
                gender="female",
                body_type="average",
                status="active",
                quality_status="rejected",
                reference_image_url="/storage/admin_models/model_rejected/reference.png",
                poses={"front": "/storage/admin_models/model_rejected/front.png"},
            )
        )
        db.commit()

    response = test_client.get("/api/v1/models")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert "model_rejected" not in ids


def test_soft_deleted_records_are_hidden_from_list_apis(client):
    test_client, SessionLocal, _ = client
    with SessionLocal() as db:
        _seed_user(db, email="admin-soft@example.com", role="admin")
        user = _seed_user(db, email="deleted-user@example.com", role="user")
        user_id = user.id
        model = ModelTemplate(
            id="soft_model",
            name="Soft Model",
            gender="female",
            body_type="average",
            status="active",
            quality_status="approved",
            reference_image_url="/storage/admin_models/soft_model/reference.png",
            poses={"front": "/storage/admin_models/soft_model/front.png"},
        )
        db.add(model)
        db.add(
            GeneratedImageJob(
                id="soft-job",
                user_id=user.id,
                store_id=None,
                draft_id=None,
                job_type="gpt_image",
                status="completed",
                step="completed",
                model_id=model.id,
                ai_model="gpt-image-2",
                quantity=1,
                garment_json={},
                validation_result={},
                metadata_json={},
                images=[],
                estimated_cost=0.05,
            )
        )
        db.commit()

    headers = _login(test_client, "admin-soft@example.com", "password123", endpoint="/api/v1/admin/login")
    assert test_client.delete(f"/api/v1/admin/users/{user_id}", headers=headers).status_code == 204
    assert test_client.delete("/api/v1/admin/models/soft_model", headers=headers).status_code == 204
    assert test_client.delete("/api/v1/admin/jobs/soft-job", headers=headers).status_code == 204

    users = test_client.get("/api/v1/admin/users").json()
    models = test_client.get("/api/v1/admin/models").json()
    jobs = test_client.get("/api/v1/admin/jobs").json()

    assert all(item["email"] != "deleted-user@example.com" for item in users)
    assert all(item["id"] != "soft_model" for item in models)
    assert all(item["id"] != "soft-job" for item in jobs)


def test_quota_exceeded_blocks_generation(client):
    test_client, SessionLocal, _ = client
    fake_redis = FakeRedis()
    with SessionLocal() as db:
        user = _seed_user(db, email="quota@example.com", role="user", monthly_quota=1, used_quota=1)
        store_id, draft_id = _seed_store_and_draft(db, user.id)

    from app.api.routes import cards as cards_route_module
    original_require_redis = cards_route_module.require_redis
    cards_route_module.require_redis = lambda settings: fake_redis
    headers = _login(test_client, "quota@example.com", "password123")
    files = {
        "front_image": ("front.jpg", _image_bytes(), "image/jpeg"),
        "back_image": ("back.jpg", _image_bytes(), "image/jpeg"),
    }
    try:
        response = test_client.post(
            f"/api/v1/cards/drafts/{draft_id}/image-generation/jobs",
            data={
                "store_id": str(store_id),
                "variant_id": "variant-1",
                "variant_index": "0",
                "quantity": "1",
                "metadata_json": "{}",
            },
            files=files,
            headers=headers,
        )
    finally:
        cards_route_module.require_redis = original_require_redis

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "quota_exceeded"


def test_admin_ai_settings_override_env_defaults(client, monkeypatch):
    test_client, SessionLocal, _ = client
    fake_redis = FakeRedis()
    monkeypatch.setattr("app.api.routes.cards.require_redis", lambda settings: fake_redis)

    with SessionLocal() as db:
        user = _seed_user(db, email="runtime@example.com", role="user", monthly_quota=10, used_quota=0)
        store_id, draft_id = _seed_store_and_draft(db, user.id)
        db.add(
            AdminAiSettings(
                id=1,
                default_image_model="db-default-model",
                gemini_model="gemini-2.5-flash",
                max_retry=4,
                default_quantity=3,
                realism_threshold=77,
                validation_threshold=91,
                allow_legacy_vton=True,
            )
        )
        db.commit()

    headers = _login(test_client, "runtime@example.com", "password123")
    files = {
        "front_image": ("front.jpg", _image_bytes(), "image/jpeg"),
        "back_image": ("back.jpg", _image_bytes(), "image/jpeg"),
    }
    response = test_client.post(
        f"/api/v1/cards/drafts/{draft_id}/image-generation/jobs",
        data={
            "store_id": str(store_id),
            "variant_id": "variant-1",
            "variant_index": "0",
            "quantity": "0",
            "metadata_json": "{}",
        },
        files=files,
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["total"] == 3

    with SessionLocal() as db:
        job = db.get(GeneratedImageJob, response.json()["id"])
        assert job is not None
        assert job.quantity == 3
        assert job.ai_model == "db-default-model"
        assert job.metadata_json["runtime_config"]["max_retry"] == 4
        assert job.metadata_json["runtime_config"]["validation_threshold"] == 91


def test_generation_is_blocked_when_cost_limit_is_exceeded(client):
    test_client, SessionLocal, _ = client
    fake_redis = FakeRedis()
    with SessionLocal() as db:
        user = _seed_user(
            db,
            email="cost@example.com",
            role="user",
            monthly_quota=10,
            used_quota=0,
            monthly_cost_limit=0.04,
            used_cost=0.02,
        )
        store_id, draft_id = _seed_store_and_draft(db, user.id)

    from app.api.routes import cards as cards_route_module
    original_require_redis = cards_route_module.require_redis
    cards_route_module.require_redis = lambda settings: fake_redis
    headers = _login(test_client, "cost@example.com", "password123")
    files = {
        "front_image": ("front.jpg", _image_bytes(), "image/jpeg"),
        "back_image": ("back.jpg", _image_bytes(), "image/jpeg"),
    }
    try:
        response = test_client.post(
            f"/api/v1/cards/drafts/{draft_id}/image-generation/jobs",
            data={
                "store_id": str(store_id),
                "variant_id": "variant-1",
                "variant_index": "0",
                "quantity": "1",
                "metadata_json": "{}",
            },
            files=files,
            headers=headers,
        )
    finally:
        cards_route_module.require_redis = original_require_redis

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "cost_limit_exceeded"


def test_admin_job_detail_returns_prompt_validation_and_image_urls(client):
    test_client, SessionLocal, _ = client
    with SessionLocal() as db:
        admin = _seed_user(db, email="jobadmin@example.com", role="admin")
        user = _seed_user(db, email="jobuser@example.com", role="user")
        job = GeneratedImageJob(
            id="detail-job",
            user_id=user.id,
            store_id=None,
            draft_id=None,
            job_type="gpt_image",
            status="completed",
            step="completed",
            model_id="model_demo",
            ai_model="gpt-image-2",
            quantity=2,
            garment_json={"category": "dress"},
            validation_result={"failed_validations": [], "quality_report": {"catalog_score": 95}},
            prompt="Use the same garment.",
            retry_count=1,
            metadata_json={"selected_model_image_url": "/storage/admin_models/model_demo/reference.png"},
            images=[{"url": "/cards/image-jobs/detail-job/media/generated-01.jpg"}],
            estimated_cost=0.1,
        )
        db.add(job)
        db.add(
            UsageRecord(
                id="usage-detail",
                user_id=user.id,
                job_id=job.id,
                provider="openai",
                model="gpt-image-2",
                operation="image_generation",
                quantity=2,
                estimated_cost=0.1,
            )
        )
        db.commit()

    _login(test_client, "jobadmin@example.com", "password123", endpoint="/api/v1/admin/login")
    response = test_client.get("/api/v1/admin/jobs/detail-job")
    assert response.status_code == 200
    data = response.json()
    assert data["prompt"] == "Use the same garment."
    assert data["garment_json"]["category"] == "dress"
    assert "quality_report" in data["validation_result"]
    assert data["images"][0]["url"].endswith("generated-01.jpg")
    assert data["selected_model_image"]["url"].endswith("reference.png")
    assert any(item["label"] == "front" for item in data["input_images"])
    assert data["usage_records"][0]["estimated_cost"] == 0.1


def test_free_user_cannot_generate_more_than_four_images_per_job(client):
    test_client, SessionLocal, _ = client
    fake_redis = FakeRedis()
    with SessionLocal() as db:
        user = _seed_user(db, email="free-limit@example.com", role="user", plan_type="free", monthly_quota=30, monthly_cost_limit=5.0)
        store_id, draft_id = _seed_store_and_draft(db, user.id)

    from app.api.routes import cards as cards_route_module
    original_require_redis = cards_route_module.require_redis
    cards_route_module.require_redis = lambda settings: fake_redis
    headers = _login(test_client, "free-limit@example.com", "password123")
    files = {
        "front_image": ("front.jpg", _image_bytes(), "image/jpeg"),
        "back_image": ("back.jpg", _image_bytes(), "image/jpeg"),
    }
    try:
        response = test_client.post(
            f"/api/v1/cards/drafts/{draft_id}/image-generation/jobs",
            data={
                "store_id": str(store_id),
                "variant_id": "variant-1",
                "variant_index": "0",
                "quantity": "5",
                "metadata_json": "{}",
            },
            files=files,
            headers=headers,
        )
    finally:
        cards_route_module.require_redis = original_require_redis

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "plan_job_limit_exceeded"


def test_quota_resets_monthly(client):
    test_client, SessionLocal, _ = client
    past_reset = datetime.now(timezone.utc) - timedelta(days=1)
    with SessionLocal() as db:
        _seed_user(
            db,
            email="quota-reset@example.com",
            role="user",
            plan_type="pro",
            monthly_quota=500,
            used_quota=123,
            monthly_cost_limit=50.0,
            used_cost=12.5,
            quota_reset_at=past_reset,
            last_quota_reset_at=past_reset - timedelta(days=30),
        )

    _login(test_client, "quota-reset@example.com", "password123")
    response = test_client.get("/api/v1/auth/usage")
    assert response.status_code == 200
    data = response.json()
    assert data["used_quota"] == 0
    assert data["remaining_quota"] == data["monthly_quota"]
    assert data["quota_reset_at"] is not None

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "quota-reset@example.com").one()
        assert user.used_quota == 0
        assert user.last_quota_reset_at is not None
        assert user.quota_reset_at is not None
        assert user.quota_reset_at is not None


def test_cost_resets_monthly(client):
    test_client, SessionLocal, _ = client
    past_reset = datetime.now(timezone.utc) - timedelta(days=1)
    with SessionLocal() as db:
        _seed_user(
            db,
            email="cost-reset@example.com",
            role="user",
            plan_type="pro",
            monthly_quota=500,
            used_quota=12,
            monthly_cost_limit=50.0,
            used_cost=19.75,
            quota_reset_at=past_reset,
            last_quota_reset_at=past_reset - timedelta(days=30),
        )

    _login(test_client, "cost-reset@example.com", "password123")
    response = test_client.get("/api/v1/auth/usage")
    assert response.status_code == 200
    data = response.json()
    assert data["used_cost"] == 0
    assert data["remaining_cost"] == data["monthly_cost_limit"]

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "cost-reset@example.com").one()
        assert user.used_cost == 0.0
        assert user.quota_reset_at is not None
        assert user.quota_reset_at is not None


def test_plan_assignment_updates_user_limits(client):
    test_client, SessionLocal, _ = client
    with SessionLocal() as db:
        _seed_user(db, email="plan-admin@example.com", role="admin", plan_type="agency", monthly_quota=3000, monthly_cost_limit=300.0)
        user = _seed_user(db, email="plan-user@example.com", role="user", plan_type="free", monthly_quota=30, monthly_cost_limit=5.0)
        user_id = user.id

    headers = _login(test_client, "plan-admin@example.com", "password123", endpoint="/api/v1/admin/login")
    response = test_client.put(f"/api/v1/admin/users/{user_id}", json={"plan_type": "pro"}, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["plan_type"] == "pro"
    assert data["monthly_quota"] == 500
    assert data["monthly_cost_limit"] == 50.0
    assert data["max_images_per_job"] == 8
    assert data["allow_gpt_image"] is True


def test_plan_disallows_disabled_job_type(client):
    test_client, SessionLocal, _ = client
    with SessionLocal() as db:
        user = _seed_user(db, email="free-plan@example.com", role="user", plan_type="free", monthly_quota=30, monthly_cost_limit=5.0)
        store_id, draft_id = _seed_store_and_draft(db, user.id)
        db.add(
            ModelTemplate(
                id="model_plan_blocked",
                name="Plan Blocked Model",
                gender="female",
                body_type="average",
                status="active",
                quality_status="approved",
                reference_image_url="/storage/admin_models/model_plan_blocked/reference.png",
                poses={"front": "/storage/admin_models/model_plan_blocked/front.png"},
            )
        )
        db.commit()

    headers = _login(test_client, "free-plan@example.com", "password123")
    files = {
        "productFrontImage": ("front.jpg", _image_bytes(), "image/jpeg"),
        "productBackImage": ("back.jpg", _image_bytes(), "image/jpeg"),
    }
    response = test_client.post(
        f"/api/v1/cards/drafts/{draft_id}/try-on/jobs",
        data={
            "store_id": str(store_id),
            "variant_id": "variant-1",
            "variant_index": "0",
            "selectedModelId": "model_plan_blocked",
            "selectedModelImageUrl": "/storage/admin_models/model_plan_blocked/reference.png",
            "selectedModelGender": "female",
            "selectedModelBodyType": "average",
            "quantity": "1",
        },
        files=files,
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "plan_job_type_forbidden"


def test_scheduler_resets_users_whose_quota_reset_at_has_passed(client):
    _, SessionLocal, _ = client
    past_reset = datetime.now(timezone.utc) - timedelta(days=1)
    with SessionLocal() as db:
        _seed_user(
            db,
            email="scheduler-due@example.com",
            role="user",
            plan_type="pro",
            monthly_quota=500,
            used_quota=44,
            monthly_cost_limit=50.0,
            used_cost=7.5,
            quota_reset_at=past_reset,
            last_quota_reset_at=past_reset - timedelta(days=30),
        )

    with SessionLocal() as db:
        reset_count = run_monthly_usage_reset_cycle(db)
        assert reset_count == 1
        user = db.query(User).filter(User.email == "scheduler-due@example.com").one()
        assert user.used_quota == 0
        assert user.used_cost == 0.0
        assert user.credit_balance == 500
        assert db.query(CreditTransaction).filter(CreditTransaction.user_id == user.id, CreditTransaction.transaction_type == "monthly_reset").count() == 1
        assert db.query(PlatformAuditLog).filter(PlatformAuditLog.target_id == str(user.id), PlatformAuditLog.action == "MONTHLY_USAGE_RESET").count() == 1


def test_scheduler_does_not_reset_users_before_quota_reset_at(client):
    _, SessionLocal, _ = client
    future_reset = datetime.now(timezone.utc) + timedelta(days=5)
    with SessionLocal() as db:
        _seed_user(
            db,
            email="scheduler-future@example.com",
            role="user",
            plan_type="pro",
            monthly_quota=500,
            used_quota=12,
            monthly_cost_limit=50.0,
            used_cost=1.2,
            quota_reset_at=future_reset,
        )

    with SessionLocal() as db:
        reset_count = run_monthly_usage_reset_cycle(db)
        assert reset_count == 0
        user = db.query(User).filter(User.email == "scheduler-future@example.com").one()
        assert user.used_quota == 12
        assert user.used_cost == 1.2


def test_agency_job_goes_to_high_priority_queue(client, monkeypatch):
    test_client, SessionLocal, _ = client
    fake_redis = FakeRedis()
    monkeypatch.setattr("app.api.routes.cards.require_redis", lambda settings: fake_redis)

    with SessionLocal() as db:
        user = _seed_user(db, email="agency-queue@example.com", role="user", plan_type="agency", monthly_quota=3000, monthly_cost_limit=300.0)
        store_id, draft_id = _seed_store_and_draft(db, user.id)

    headers = _login(test_client, "agency-queue@example.com", "password123")
    files = {
        "front_image": ("front.jpg", _image_bytes(), "image/jpeg"),
        "back_image": ("back.jpg", _image_bytes(), "image/jpeg"),
    }
    response = test_client.post(
        f"/api/v1/cards/drafts/{draft_id}/image-generation/jobs",
        data={"store_id": str(store_id), "variant_id": "variant-1", "variant_index": "0", "quantity": "1", "metadata_json": "{}"},
        files=files,
        headers=headers,
    )
    assert response.status_code == 200
    assert fake_redis.queue[0][0] == IMAGE_JOB_QUEUE_HIGH


def test_free_job_goes_to_low_priority_queue(client, monkeypatch):
    test_client, SessionLocal, _ = client
    fake_redis = FakeRedis()
    monkeypatch.setattr("app.api.routes.cards.require_redis", lambda settings: fake_redis)

    with SessionLocal() as db:
        user = _seed_user(db, email="free-queue@example.com", role="user", plan_type="free", monthly_quota=30, monthly_cost_limit=5.0)
        user.credit_balance = 30
        store_id, draft_id = _seed_store_and_draft(db, user.id)
        db.commit()

    headers = _login(test_client, "free-queue@example.com", "password123")
    files = {
        "front_image": ("front.jpg", _image_bytes(), "image/jpeg"),
        "back_image": ("back.jpg", _image_bytes(), "image/jpeg"),
    }
    response = test_client.post(
        f"/api/v1/cards/drafts/{draft_id}/image-generation/jobs",
        data={"store_id": str(store_id), "variant_id": "variant-1", "variant_index": "0", "quantity": "1", "metadata_json": "{}"},
        files=files,
        headers=headers,
    )
    assert response.status_code == 200
    assert fake_redis.queue[0][0] == IMAGE_JOB_QUEUE_LOW


def test_quota_warning_threshold_works(client):
    test_client, SessionLocal, _ = client
    with SessionLocal() as db:
        _seed_user(db, email="warning@example.com", role="user", plan_type="pro", monthly_quota=100, used_quota=80, monthly_cost_limit=10.0, used_cost=8.0)

    _login(test_client, "warning@example.com", "password123")
    response = test_client.get("/api/v1/auth/usage")
    assert response.status_code == 200
    data = response.json()
    assert data["quota_percent"] == 80.0
    assert data["cost_percent"] == 80.0


def test_credit_check_blocks_insufficient_credits(client, monkeypatch):
    test_client, SessionLocal, _ = client
    fake_redis = FakeRedis()
    monkeypatch.setattr("app.api.routes.cards.require_redis", lambda settings: fake_redis)

    with SessionLocal() as db:
        user = _seed_user(db, email="credits-block@example.com", role="user", plan_type="pro", monthly_quota=500, monthly_cost_limit=50.0)
        user.credit_balance = 0
        db.commit()
        store_id, draft_id = _seed_store_and_draft(db, user.id)

    headers = _login(test_client, "credits-block@example.com", "password123")
    files = {
        "front_image": ("front.jpg", _image_bytes(), "image/jpeg"),
        "back_image": ("back.jpg", _image_bytes(), "image/jpeg"),
    }
    response = test_client.post(
        f"/api/v1/cards/drafts/{draft_id}/image-generation/jobs",
        data={"store_id": str(store_id), "variant_id": "variant-1", "variant_index": "0", "quantity": "1", "metadata_json": "{}"},
        files=files,
        headers=headers,
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_credits"


def test_failed_job_does_not_consume_credits(client, monkeypatch):
    test_client, SessionLocal, _ = client
    fake_redis = FakeRedis()
    monkeypatch.setattr("app.api.routes.cards.require_redis", lambda settings: fake_redis)
    monkeypatch.setattr("app.services.product_image_generator.ProductImageGenerator._generate_one", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr("app.services.product_image_generator.ProductImageGenerator._attach_to_draft", lambda *args, **kwargs: None)

    with SessionLocal() as db:
        user = _seed_user(db, email="credits-fail@example.com", role="user", plan_type="pro", monthly_quota=500, monthly_cost_limit=50.0)
        starting_balance = user.credit_balance
        store_id, draft_id = _seed_store_and_draft(db, user.id)

    headers = _login(test_client, "credits-fail@example.com", "password123")
    files = {
        "front_image": ("front.jpg", _image_bytes(), "image/jpeg"),
        "back_image": ("back.jpg", _image_bytes(), "image/jpeg"),
    }
    response = test_client.post(
        f"/api/v1/cards/drafts/{draft_id}/image-generation/jobs",
        data={"store_id": str(store_id), "variant_id": "variant-1", "variant_index": "0", "quantity": "1", "metadata_json": "{}"},
        files=files,
        headers=headers,
    )
    assert response.status_code == 200
    job_id = response.json()["id"]

    from app.services.product_image_generator import ProductImageGenerator
    with SessionLocal() as db:
        generator = ProductImageGenerator(get_settings(), fake_redis)
        with pytest.raises(RuntimeError):
            import asyncio
            asyncio.run(generator.run_job(job_id, db))

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "credits-fail@example.com").one()
        assert user.credit_balance == starting_balance
        assert db.query(CreditTransaction).filter(CreditTransaction.job_id == job_id, CreditTransaction.transaction_type == "consume").count() == 0


def test_successful_job_consumes_credits(client, monkeypatch):
    test_client, SessionLocal, _ = client
    fake_redis = FakeRedis()
    monkeypatch.setattr("app.api.routes.cards.require_redis", lambda settings: fake_redis)
    monkeypatch.setattr("app.services.product_image_generator.ProductImageGenerator._generate_one", lambda *args, **kwargs: _image_bytes())
    monkeypatch.setattr("app.services.product_image_generator.ProductImageGenerator._attach_to_draft", lambda *args, **kwargs: None)

    with SessionLocal() as db:
        user = _seed_user(db, email="credits-success@example.com", role="user", plan_type="pro", monthly_quota=500, monthly_cost_limit=50.0)
        starting_balance = user.credit_balance
        store_id, draft_id = _seed_store_and_draft(db, user.id)

    headers = _login(test_client, "credits-success@example.com", "password123")
    files = {
        "front_image": ("front.jpg", _image_bytes(), "image/jpeg"),
        "back_image": ("back.jpg", _image_bytes(), "image/jpeg"),
    }
    response = test_client.post(
        f"/api/v1/cards/drafts/{draft_id}/image-generation/jobs",
        data={"store_id": str(store_id), "variant_id": "variant-1", "variant_index": "0", "quantity": "1", "metadata_json": "{}"},
        files=files,
        headers=headers,
    )
    assert response.status_code == 200
    job_id = response.json()["id"]

    from app.services.product_image_generator import ProductImageGenerator
    import asyncio
    with SessionLocal() as db:
        generator = ProductImageGenerator(get_settings(), fake_redis)
        result = asyncio.run(generator.run_job(job_id, db))
        assert result["status"] == "completed"

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "credits-success@example.com").one()
        assert user.credit_balance == starting_balance - 1
        assert db.query(CreditTransaction).filter(CreditTransaction.job_id == job_id, CreditTransaction.transaction_type == "consume").count() == 1


def test_billing_schema_tables_exist(client):
    _, SessionLocal, _ = client
    with SessionLocal() as db:
        table_names = set(inspect(db.bind).get_table_names())
    assert "subscription_plans" in table_names
    assert "user_subscriptions" in table_names
    assert "payment_transactions" in table_names
    assert "credit_transactions" in table_names
