from datetime import UTC, date, datetime
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import encrypt_secret
from app.db.session import Base
from app.models.card import CardDraft, CardJob
from app.models.finance import SellerFinanceAutomationState, WbFinanceSyncState
from app.models.seller import Seller
from app.models.store import Store
from app.models.user import User
from app.services.finance_automation_service import FinanceAutomationJob, FinanceAutomationService, bootstrap_date_range
from app.services.store_bootstrap_service import StoreBootstrapSyncService


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.queue: list[str] = []

    async def set(self, key: str, value: str, nx: bool = False, ex: int | None = None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def delete(self, key: str):
        self.values.pop(key, None)

    async def rpush(self, key: str, value: str):
        self.queue.append(value)
        return len(self.queue)


def _build_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'bootstrap.db'}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    _ = (Store, User, CardDraft, CardJob, Seller, SellerFinanceAutomationState, WbFinanceSyncState)
    Base.metadata.create_all(bind=engine)
    return SessionLocal


def _create_store(SessionLocal, settings: Settings) -> int:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "seller@example.com").one_or_none()
        if user is None:
            user = User(name="Seller", email="seller@example.com", password_hash="hashed")
            db.add(user)
            db.commit()
            db.refresh(user)
        store = Store(
            user_id=user.id,
            name="Demo Store",
            wb_api_key_encrypted=encrypt_secret(settings, "x" * 32),
        )
        db.add(store)
        db.commit()
        db.refresh(store)
        return store.id


def test_store_bootstrap_marks_state_failed_when_redis_missing(tmp_path, monkeypatch):
    SessionLocal = _build_session(tmp_path)
    settings = Settings(
        app_env="test",
        app_secret_key="test-secret-key",
        encryption_key="0123456789abcdef0123456789abcdef",
        database_url=f"sqlite:///{tmp_path / 'bootstrap.db'}",
        cookie_secure=False,
    )
    store_id = _create_store(SessionLocal, settings)
    monkeypatch.setattr(
        "app.services.store_bootstrap_service.require_redis",
        lambda _settings: (_ for _ in ()).throw(AppError("redis_not_configured", "missing redis", 500)),
    )

    service = StoreBootstrapSyncService(settings, SessionLocal)
    service.enqueue_store_bootstrap(store_id)

    with SessionLocal() as db:
        state = db.query(SellerFinanceAutomationState).one()
        assert state.bootstrap_status == "failed"
        assert "REDIS_URL" in (state.bootstrap_last_error or "")


@pytest.mark.anyio
async def test_finance_automation_scheduler_enqueues_bootstrap_and_missing_daily_jobs(tmp_path):
    SessionLocal = _build_session(tmp_path)
    settings = Settings(
        app_env="test",
        app_secret_key="test-secret-key",
        encryption_key="0123456789abcdef0123456789abcdef",
        database_url=f"sqlite:///{tmp_path / 'bootstrap.db'}",
        cookie_secure=False,
    )
    store_id = _create_store(SessionLocal, settings)
    other_store_id = _create_store(SessionLocal, settings)

    with SessionLocal() as db:
        first_seller = Seller(store_id=store_id, name="Seller One")
        second_seller = Seller(store_id=other_store_id, name="Seller Two")
        db.add(first_seller)
        db.add(second_seller)
        db.commit()
        db.refresh(first_seller)
        db.refresh(second_seller)
        db.add(
            SellerFinanceAutomationState(
                seller_id=first_seller.id,
                timezone="Europe/Moscow",
                bootstrap_status="completed",
                bootstrap_range_from=date(2026, 4, 18),
                bootstrap_range_to=date(2026, 5, 16),
                last_successful_daily_sync_date=date(2026, 5, 16),
            )
        )
        db.add(
            WbFinanceSyncState(
                seller_id=first_seller.id,
                date_from=date(2026, 5, 17),
                date_to=date(2026, 5, 17),
                period="daily",
                status="completed",
            )
        )
        db.add(
            SellerFinanceAutomationState(
                seller_id=second_seller.id,
                timezone="Europe/Moscow",
                bootstrap_status="failed",
            )
        )
        db.commit()

    redis = FakeRedis()
    service = FinanceAutomationService(settings, SessionLocal, redis)
    now = datetime(2026, 5, 19, 1, 0, tzinfo=UTC)
    enqueued = await service.run_scheduler_cycle_async(now=now)

    assert enqueued == 2
    payloads = [FinanceAutomationJob.from_dict(json.loads(item)) for item in redis.queue]
    assert payloads[0].kind == "daily_store"
    assert payloads[0].store_id == store_id
    assert payloads[0].target_date == "2026-05-18"
    assert payloads[1].kind == "bootstrap_store"
    assert payloads[1].store_id == other_store_id


@pytest.mark.anyio
async def test_finance_automation_scheduler_waits_before_retrying_failed_bootstrap(tmp_path):
    SessionLocal = _build_session(tmp_path)
    settings = Settings(
        app_env="test",
        app_secret_key="test-secret-key",
        encryption_key="0123456789abcdef0123456789abcdef",
        database_url=f"sqlite:///{tmp_path / 'bootstrap.db'}",
        cookie_secure=False,
        finance_failed_retry_seconds=3600,
    )
    store_id = _create_store(SessionLocal, settings)
    now = datetime(2026, 5, 19, 1, 0, tzinfo=UTC)

    with SessionLocal() as db:
        seller = Seller(store_id=store_id, name="Seller")
        db.add(seller)
        db.commit()
        db.refresh(seller)
        db.add(
            SellerFinanceAutomationState(
                seller_id=seller.id,
                timezone="Europe/Moscow",
                bootstrap_status="failed",
                bootstrap_finished_at=now,
            )
        )
        db.commit()

    redis = FakeRedis()
    service = FinanceAutomationService(settings, SessionLocal, redis)

    assert await service.run_scheduler_cycle_async(now=now) == 0
    assert redis.queue == []


@pytest.mark.anyio
async def test_finance_automation_bootstrap_runs_product_then_finance_and_updates_state(tmp_path, monkeypatch):
    SessionLocal = _build_session(tmp_path)
    settings = Settings(
        app_env="test",
        app_secret_key="test-secret-key",
        encryption_key="0123456789abcdef0123456789abcdef",
        database_url=f"sqlite:///{tmp_path / 'bootstrap.db'}",
        cookie_secure=False,
    )
    store_id = _create_store(SessionLocal, settings)
    redis = FakeRedis()
    published_jobs = []

    def fake_publish_rabbitmq_job(rabbitmq_url, routing_key, store_id, payload, type_name):
        published_jobs.append((routing_key, store_id, payload, type_name))

    monkeypatch.setattr("app.services.finance_automation_service.publish_rabbitmq_job", fake_publish_rabbitmq_job)

    # Need WbProductSyncState and WbFinanceSyncState imported or present for the scheduler to query them
    from app.models.wb_product import WbProductSyncState

    service = FinanceAutomationService(settings, SessionLocal, redis)
    await service.process_job(FinanceAutomationJob(kind="bootstrap_store", store_id=store_id))

    expected_from, expected_to = bootstrap_date_range(settings)
    with SessionLocal() as db:
        seller = db.query(Seller).one()
        state = db.query(SellerFinanceAutomationState).filter(SellerFinanceAutomationState.seller_id == seller.id).one()
        assert state.bootstrap_status == "running"
        assert state.bootstrap_range_from == expected_from
        assert state.bootstrap_range_to == expected_to

    assert len(published_jobs) == 1
    assert published_jobs[0] == ("product.sync", store_id, {"full": True}, "product.sync")

    # Simulate the RabbitMQ sync worker finishing product and finance sync.
    with SessionLocal() as db:
        seller = db.query(Seller).one()
        db.add(WbProductSyncState(
            seller_id=seller.id,
            sync_type="active_cards",
            status="completed",
            finished_at=datetime.now(UTC)
        ))
        db.add(WbFinanceSyncState(
            seller_id=seller.id,
            date_from=expected_from,
            date_to=expected_to,
            period="daily",
            status="completed",
            finished_at=datetime.now(UTC)
        ))
        db.commit()

    # Now run scheduler cycle to transition bootstrap state to completed
    await service.run_scheduler_cycle_async()

    with SessionLocal() as db:
        seller = db.query(Seller).one()
        state = db.query(SellerFinanceAutomationState).filter(SellerFinanceAutomationState.seller_id == seller.id).one()
        assert state.bootstrap_status == "completed"
        assert state.last_successful_daily_sync_date == expected_to
