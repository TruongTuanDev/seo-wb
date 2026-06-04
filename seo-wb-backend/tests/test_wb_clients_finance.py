from datetime import date

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.session import Base
from app.models.finance import ApiDiagnosticLog
from app.models.seller import Seller
from app.models.store import Store
from app.models.user import User
from app.services.wb_base_client import WbRateLimitError
from app.services import wb_base_client
from app.services.wb_finance_client import WbFinanceClient


@pytest.mark.anyio
async def test_wb_finance_client_logs_rate_limit_without_exposing_token(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    _ = (User, Store, Seller, ApiDiagnosticLog)
    Base.metadata.create_all(bind=engine)
    settings = Settings(app_env="test", app_secret_key="test-secret-key", database_url=f"sqlite:///{tmp_path / 'test.db'}")
    wb_base_client._server_cooldowns.clear()
    wb_base_client._limiter._hits.clear()
    wb_base_client._limiter._last_hit.clear()

    class DummyClient:
        is_closed = False

        async def request(self, method, path, headers=None, params=None, json=None, timeout=None):
            request = httpx.Request(method, f"{settings.wb_finance_api_base_url}{path}")
            return httpx.Response(
                429,
                request=request,
                json={"error": "rate limited"},
                headers={"X-Ratelimit-Retry": "61"},
            )

    with SessionLocal() as db:
        async def fake_client(self):
            return DummyClient()

        monkeypatch.setattr(WbFinanceClient, "_client", fake_client)
        client = WbFinanceClient(settings, "super-secret-token", db=db, seller_id=None)
        with pytest.raises(WbRateLimitError) as exc:
            await client.get_balance()
        assert exc.value.details["retry_after_seconds"] == 61.0
        log = db.query(ApiDiagnosticLog).one()
        assert log.status_code == 429
        assert "token" not in str(log.request_meta).casefold()
        assert "super-secret-token" not in str(log.request_meta)


@pytest.mark.anyio
async def test_wb_finance_client_respects_server_cooldown_after_429(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    _ = (User, Store, Seller, ApiDiagnosticLog)
    Base.metadata.create_all(bind=engine)
    settings = Settings(app_env="test", app_secret_key="test-secret-key", database_url=f"sqlite:///{tmp_path / 'test.db'}")
    wb_base_client._server_cooldowns.clear()
    wb_base_client._limiter._hits.clear()
    wb_base_client._limiter._last_hit.clear()
    calls = {"count": 0}

    class DummyClient:
        is_closed = False

        async def request(self, method, path, headers=None, params=None, json=None, timeout=None):
            calls["count"] += 1
            request = httpx.Request(method, f"{settings.wb_finance_api_base_url}{path}")
            return httpx.Response(
                429,
                request=request,
                json={"error": "rate limited"},
                headers={"X-Ratelimit-Retry": "120"},
            )

    with SessionLocal() as db:
        async def fake_client(self):
            return DummyClient()

        monkeypatch.setattr(WbFinanceClient, "_client", fake_client)
        client = WbFinanceClient(settings, "super-secret-token", db=db, seller_id=None)
        with pytest.raises(WbRateLimitError):
            await client.get_balance()
        with pytest.raises(WbRateLimitError) as exc:
            await client.get_balance()
        assert calls["count"] == 1
        assert exc.value.details["retry_after_seconds"] > 0


@pytest.mark.anyio
async def test_wb_finance_client_uses_safe_fallback_when_retry_headers_missing(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    _ = (User, Store, Seller, ApiDiagnosticLog)
    Base.metadata.create_all(bind=engine)
    settings = Settings(app_env="test", app_secret_key="test-secret-key", database_url=f"sqlite:///{tmp_path / 'test.db'}")
    wb_base_client._server_cooldowns.clear()
    wb_base_client._limiter._hits.clear()
    wb_base_client._limiter._last_hit.clear()

    class DummyClient:
        is_closed = False

        async def request(self, method, path, headers=None, params=None, json=None, timeout=None):
            request = httpx.Request(method, f"{settings.wb_finance_api_base_url}{path}")
            return httpx.Response(429, request=request, json={"error": "rate limited"})

    with SessionLocal() as db:
        async def fake_client(self):
            return DummyClient()

        monkeypatch.setattr(WbFinanceClient, "_client", fake_client)
        client = WbFinanceClient(settings, "super-secret-token", db=db, seller_id=77)
        with pytest.raises(WbRateLimitError) as exc:
            await client.get_balance()
        assert exc.value.details["retry_after_seconds"] == 60.0
