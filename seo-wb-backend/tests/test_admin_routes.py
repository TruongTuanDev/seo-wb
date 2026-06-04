import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db
from app.core.config import Settings, get_settings
from app.core.security import hash_password
from app.db.session import Base
from app.main import app
from app.models.admin import AdminAiSettings, AdminAuditLog, GeneratedImageJob, ModelTemplate, UsageRecord
from app.models.card import CardDraft, CardJob
from app.models.store import Store
from app.models.user import User


@pytest.fixture()
def client(tmp_path):
    _ = (Store, CardDraft, CardJob, ModelTemplate, GeneratedImageJob, UsageRecord, AdminAiSettings, AdminAuditLog)
    engine = create_engine(f"sqlite:///{tmp_path / 'admin-test.db'}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    settings = Settings(
        app_env="test",
        app_secret_key="test-secret-key",
        database_url=f"sqlite:///{tmp_path / 'admin-test.db'}",
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

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings
    with TestClient(app, headers={"user-agent": "pytest-browser"}) as test_client:
        yield test_client, SessionLocal
    app.dependency_overrides.clear()


def test_admin_login_requires_admin_role(client):
    test_client, SessionLocal = client
    with SessionLocal() as db:
        db.add(User(name="Seller", email="seller@example.com", password_hash=hash_password("password123"), role="user"))
        db.commit()

    response = test_client.post("/api/v1/admin/login", json={"email": "seller@example.com", "password": "password123"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_admin_credentials"


def test_admin_dashboard_requires_admin_role(client):
    test_client, SessionLocal = client
    with SessionLocal() as db:
        db.add(User(name="Admin", email="admin@example.com", password_hash=hash_password("password123"), role="admin"))
        db.add(User(name="Seller", email="seller@example.com", password_hash=hash_password("password123"), role="user"))
        db.commit()

    login = test_client.post("/api/v1/admin/login", json={"email": "admin@example.com", "password": "password123"})
    assert login.status_code == 200

    response = test_client.get("/api/v1/admin")
    assert response.status_code == 200
    assert response.json()["total_users"] == 2


def test_admin_login_uses_separate_cookie_scope(client):
    test_client, SessionLocal = client
    with SessionLocal() as db:
        db.add(User(name="Admin", email="admin@example.com", password_hash=hash_password("password123"), role="admin"))
        db.commit()

    login = test_client.post("/api/v1/admin/login", json={"email": "admin@example.com", "password": "password123"})

    assert login.status_code == 200
    assert "seller_wb_admin_access" in login.cookies
    assert "seller_wb_admin_csrf" in login.cookies
    assert "seller_wb_access" not in login.cookies


def test_admin_ai_settings_default_and_update_validation_failure_behavior(client):
    test_client, SessionLocal = client
    with SessionLocal() as db:
      db.add(User(name="Admin", email="admin@example.com", password_hash=hash_password("password123"), role="admin"))
      db.commit()

    login = test_client.post("/api/v1/admin/login", json={"email": "admin@example.com", "password": "password123"})
    assert login.status_code == 200

    response = test_client.get("/api/v1/admin/settings/ai")
    assert response.status_code == 200
    assert response.json()["validation_failure_behavior"] == "warn"

    csrf_token = login.cookies.get("seller_wb_admin_csrf") or ""
    update = test_client.put(
        "/api/v1/admin/settings/ai",
        json={
            "default_image_model": "gpt-image-2",
            "fallback_image_model": None,
            "gemini_model": "gemini-2.5-flash",
            "max_retry": 1,
            "default_quantity": 6,
            "realism_threshold": 80,
            "validation_threshold": 85,
            "validation_failure_behavior": "block",
            "allow_legacy_vton": True,
        },
        headers={"x-csrf-token": csrf_token},
    )
    assert update.status_code == 200
    assert update.json()["validation_failure_behavior"] == "block"
