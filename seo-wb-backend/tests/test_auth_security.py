import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db
from app.core.config import Settings, get_settings
from app.core.security import create_access_token, hash_password
from app.db.session import Base
from app.main import app
from app.models.card import CardDraft, CardJob
from app.models.store import Store
from app.models.user import User
from app.services.store_bootstrap_service import StoreBootstrapSyncService


@pytest.fixture()
def client(tmp_path):
    _ = (Store, CardDraft, CardJob)
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    settings = Settings(
        app_env="test",
        app_secret_key="test-secret-key",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        cookie_secure=False,
        auth_rate_limit_requests=100,
        global_rate_limit_requests=1000,
    )

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_settings():
        return settings

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings
    with TestClient(app, headers={"user-agent": "pytest-browser"}) as test_client:
        yield test_client, TestingSessionLocal, settings
    app.dependency_overrides.clear()


def test_login_sets_httponly_cookie_and_hides_access_token(client):
    test_client, SessionLocal, settings = client
    with SessionLocal() as db:
        db.add(User(name="Seller", email="seller@example.com", password_hash=hash_password("password123")))
        db.commit()

    response = test_client.post("/api/v1/auth/login", json={"email": "seller@example.com", "password": "password123"})

    assert response.status_code == 200
    assert response.json()["access_token"] is None
    assert response.json()["user"]["email"] == "seller@example.com"
    assert settings.auth_cookie_name in response.cookies
    assert "httponly" in response.headers["set-cookie"].lower()
    assert settings.csrf_cookie_name in response.cookies
    assert settings.admin_auth_cookie_name not in response.cookies


def test_cookie_auth_requires_csrf_for_mutating_requests(client, monkeypatch):
    test_client, SessionLocal, settings = client
    with SessionLocal() as db:
        db.add(User(name="Seller", email="seller@example.com", password_hash=hash_password("password123")))
        db.commit()
    login = test_client.post("/api/v1/auth/login", json={"email": "seller@example.com", "password": "password123"})
    assert login.status_code == 200

    triggered_store_ids: list[int] = []

    def fake_sync(self, store_id: int) -> None:
        triggered_store_ids.append(store_id)

    monkeypatch.setattr(StoreBootstrapSyncService, "enqueue_store_bootstrap", fake_sync)

    payload = {"name": "Demo Store", "wb_api_key": "x" * 32}
    missing_csrf = test_client.post("/api/v1/stores", json=payload)
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["error"]["code"] == "csrf_required"

    csrf = test_client.cookies.get(settings.csrf_cookie_name)
    with_csrf = test_client.post("/api/v1/stores", json=payload, headers={"x-csrf-token": csrf})
    assert with_csrf.status_code == 200
    assert with_csrf.json()["name"] == "Demo Store"
    assert triggered_store_ids == [with_csrf.json()["id"]]


def test_copied_bearer_token_fails_with_different_user_agent(client):
    test_client, SessionLocal, settings = client
    with SessionLocal() as db:
        user = User(name="Seller", email="seller@example.com", password_hash=hash_password("password123"))
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token(
        settings,
        "1",
        {"fp": hashlib.sha256(f"{settings.app_secret_key}:pytest-browser".encode("utf-8")).hexdigest()},
    )

    response = test_client.get(
        "/api/v1/auth/me",
        headers={"authorization": f"Bearer {token}", "user-agent": "postman-runtime"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token_fingerprint"
