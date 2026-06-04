import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db
from app.core.config import Settings, get_settings
from app.core.security import encrypt_secret, hash_password
from app.db.session import Base
from app.main import app
from app.models.card import CardDraft, CardJob
from app.models.store import Store
from app.models.user import User


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
        max_generate_images=2,
        max_upload_image_bytes=16,
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


def _login(test_client: TestClient, SessionLocal, settings: Settings) -> tuple[int, str]:
    with SessionLocal() as db:
        user = User(name="Seller", email="seller@example.com", password_hash=hash_password("password123"))
        db.add(user)
        db.flush()
        store = Store(user_id=user.id, name="Store", wb_api_key_encrypted=encrypt_secret(settings, "x" * 32))
        db.add(store)
        db.commit()
        store_id = store.id

    response = test_client.post("/api/v1/auth/login", json={"email": "seller@example.com", "password": "password123"})
    assert response.status_code == 200
    csrf = test_client.cookies.get(settings.csrf_cookie_name)
    assert csrf
    return store_id, csrf


def test_generate_rejects_too_many_images_before_ai_work(client):
    test_client, SessionLocal, settings = client
    store_id, csrf = _login(test_client, SessionLocal, settings)

    files = [
        ("images", (f"image-{index}.jpg", b"not-an-image", "image/jpeg"))
        for index in range(settings.max_generate_images + 1)
    ]
    response = test_client.post(
        "/api/v1/cards/generate",
        data={"store_id": str(store_id), "product_input_json": json.dumps({"category": "jeans"})},
        files=files,
        headers={"x-csrf-token": csrf},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "too_many_images"


def test_generate_rejects_oversized_image_before_ai_work(client):
    test_client, SessionLocal, settings = client
    store_id, csrf = _login(test_client, SessionLocal, settings)

    response = test_client.post(
        "/api/v1/cards/generate",
        data={"store_id": str(store_id), "product_input_json": json.dumps({"category": "jeans"})},
        files={"images": ("large.jpg", b"x" * (settings.max_upload_image_bytes + 1), "image/jpeg")},
        headers={"x-csrf-token": csrf},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "image_too_large"
