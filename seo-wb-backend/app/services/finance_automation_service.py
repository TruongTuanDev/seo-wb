import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from redis.asyncio import Redis
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import decrypt_secret
from app.models.finance import SellerFinanceAutomationState, WbFinanceSyncState
from app.models.store import Store
from app.models.wb_product import WbProductSyncState
from app.services.finance_service import FinanceSyncService
from app.services.seller_service import ensure_seller_for_store
from app.services.wb_base_client import WbRateLimitError
from app.services.wb_content_client import WbContentClient
from app.services.wb_finance_client import WbFinanceClient
from app.services.wb_product_sync_service import WbProductSyncService


logger = logging.getLogger(__name__)

FINANCE_AUTO_SYNC_QUEUE_KEY = "finance:auto:sync:jobs"
FINANCE_AUTO_SYNC_LEADER_LOCK_KEY = "finance:auto:sync:scheduler:leader"


@dataclass(frozen=True)
class FinanceAutomationJob:
    kind: str
    store_id: int
    target_date: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"kind": self.kind, "storeId": self.store_id}
        if self.target_date is not None:
            payload["targetDate"] = self.target_date
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FinanceAutomationJob":
        return cls(kind=str(payload["kind"]), store_id=int(payload["storeId"]), target_date=payload.get("targetDate"))


def finance_timezone(settings: Settings) -> ZoneInfo:
    return ZoneInfo(settings.finance_auto_sync_timezone)


def finance_local_today(settings: Settings, now: datetime | None = None) -> date:
    current = now or datetime.now(UTC)
    return current.astimezone(finance_timezone(settings)).date()


def next_finance_midnight(settings: Settings, now: datetime | None = None) -> datetime:
    current = now or datetime.now(UTC)
    tz = finance_timezone(settings)
    local_now = current.astimezone(tz)
    next_local = datetime.combine(local_now.date() + timedelta(days=1), datetime.min.time(), tzinfo=tz)
    return next_local.astimezone(UTC)


def bootstrap_date_range(settings: Settings, now: datetime | None = None) -> tuple[date, date]:
    target = finance_local_today(settings, now=now) - timedelta(days=1)
    lookback_days = max(1, settings.finance_bootstrap_lookback_days)
    return target - timedelta(days=lookback_days - 1), target


def ensure_finance_automation_state(db: Session, settings: Settings, seller_id: int) -> SellerFinanceAutomationState:
    state = db.query(SellerFinanceAutomationState).filter(SellerFinanceAutomationState.seller_id == seller_id).one_or_none()
    if state is not None:
        return state
    state = SellerFinanceAutomationState(seller_id=seller_id, timezone=settings.finance_auto_sync_timezone)
    db.add(state)
    db.commit()
    db.refresh(state)
    return state


def publish_rabbitmq_job(rabbitmq_url: str, routing_key: str, store_id: int, payload: dict, type_name: str) -> None:
    import pika
    import json
    from datetime import datetime, timezone
    import uuid

    job_id = f"{type_name}-{store_id}-{uuid.uuid4().hex}"
    if type_name == "product.sync":
        idempotency_key = f"product.sync:{store_id}:full" if payload.get("full") else f"product.sync:{store_id}:inc"
    elif type_name == "finance.sync":
        idempotency_key = f"finance.sync:{store_id}:{payload.get('date_from')}:{payload.get('date_to')}:{payload.get('period')}"
    else:
        idempotency_key = f"{type_name}:{store_id}:{uuid.uuid4().hex}"

    sync_job = {
        "id": job_id,
        "type": type_name,
        "store_id": store_id,
        "payload": payload,
        "idempotency_key": idempotency_key,
        "attempt": 0,
        "requested_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }

    params = pika.URLParameters(rabbitmq_url)
    connection = pika.BlockingConnection(params)
    try:
        channel = connection.channel()
        channel.basic_publish(
            exchange="wb.sync",
            routing_key=routing_key,
            body=json.dumps(sync_job),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
                headers={
                    "type": type_name,
                    "idempotency_key": idempotency_key,
                    "attempt": 0
                }
            )
        )
    finally:
        connection.close()



class FinanceAutomationService:
    def __init__(self, settings: Settings, session_factory: sessionmaker[Session], redis: Redis | None) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._redis = redis

    def enqueue_store_bootstrap_sync(self, store_id: int) -> None:
        asyncio.run(self.enqueue_store_bootstrap_sync_async(store_id))

    async def enqueue_store_bootstrap_sync_async(self, store_id: int) -> bool:
        if self._redis is None:
            self._mark_store_bootstrap_error(store_id, "REDIS_URL or REDIS_HOST/REDIS_PASSWORD is not configured.")
            return False
        return await self._enqueue_for_store(FinanceAutomationJob(kind="bootstrap_store", store_id=store_id))

    def run_scheduler_cycle(self) -> int:
        return asyncio.run(self.run_scheduler_cycle_async())

    async def run_scheduler_cycle_async(self, now: datetime | None = None) -> int:
        redis = self._require_redis()
        acquired = await redis.set(
            FINANCE_AUTO_SYNC_LEADER_LOCK_KEY,
            "1",
            nx=True,
            ex=self._settings.finance_scheduler_leader_lock_seconds,
        )
        if not acquired:
            return 0

        enqueued = 0
        target_date = finance_local_today(self._settings, now=now) - timedelta(days=1)
        try:
            with self._session_factory() as db:
                stores = db.query(Store).order_by(Store.id.asc()).all()
                for store in stores:
                    if not store.wb_api_key_encrypted:
                        continue
                    seller = ensure_seller_for_store(db, store)
                    state = ensure_finance_automation_state(db, self._settings, seller.id)
                    state.last_scheduler_seen_at = now or datetime.now(UTC)
                    db.commit()

                    # Monitor Go sync progress for bootstrap
                    if state.bootstrap_status in {"queued", "running"}:
                        product_completed = db.query(WbProductSyncState).filter(
                            WbProductSyncState.seller_id == seller.id,
                            WbProductSyncState.sync_type == "active_cards",
                            WbProductSyncState.status == "completed"
                        ).first()

                        finance_completed = db.query(WbFinanceSyncState).filter(
                            WbFinanceSyncState.seller_id == seller.id,
                            WbFinanceSyncState.period == "daily",
                            WbFinanceSyncState.date_from == state.bootstrap_range_from,
                            WbFinanceSyncState.date_to == state.bootstrap_range_to,
                            WbFinanceSyncState.status == "completed"
                        ).first()

                        if product_completed and finance_completed:
                            state.bootstrap_status = "completed"
                            state.bootstrap_finished_at = now or datetime.now(UTC)
                            state.bootstrap_last_error = None
                            state.last_successful_daily_sync_date = state.bootstrap_range_to
                            state.last_attempted_daily_sync_date = state.bootstrap_range_to
                            state.last_daily_status = "completed"
                            state.last_daily_error = None
                            db.commit()
                        else:
                            product_failed = db.query(WbProductSyncState).filter(
                                WbProductSyncState.seller_id == seller.id,
                                WbProductSyncState.sync_type == "active_cards",
                                WbProductSyncState.status.in_({"failed", "interrupted"})
                            ).first()

                            finance_failed = db.query(WbFinanceSyncState).filter(
                                WbFinanceSyncState.seller_id == seller.id,
                                WbFinanceSyncState.period == "daily",
                                WbFinanceSyncState.date_from == state.bootstrap_range_from,
                                WbFinanceSyncState.date_to == state.bootstrap_range_to,
                                WbFinanceSyncState.status == "failed"
                            ).first()

                            if product_failed or finance_failed:
                                state.bootstrap_status = "failed"
                                state.bootstrap_finished_at = now or datetime.now(UTC)
                                state.bootstrap_last_error = (
                                    (product_failed.last_error if product_failed else finance_failed.last_error)
                                    or "Failed during Go bootstrap sync."
                                )
                                db.commit()

                    # Monitor Go sync progress for daily
                    if state.last_daily_status == "running" and state.last_attempted_daily_sync_date:
                        finance_completed = db.query(WbFinanceSyncState).filter(
                            WbFinanceSyncState.seller_id == seller.id,
                            WbFinanceSyncState.period == "daily",
                            WbFinanceSyncState.date_from == state.last_attempted_daily_sync_date,
                            WbFinanceSyncState.date_to == state.last_attempted_daily_sync_date,
                            WbFinanceSyncState.status == "completed"
                        ).first()
                        if finance_completed:
                            state.last_successful_daily_sync_date = state.last_attempted_daily_sync_date
                            state.last_daily_status = "completed"
                            state.last_daily_error = None
                            db.commit()
                        else:
                            finance_failed = db.query(WbFinanceSyncState).filter(
                                WbFinanceSyncState.seller_id == seller.id,
                                WbFinanceSyncState.period == "daily",
                                WbFinanceSyncState.date_from == state.last_attempted_daily_sync_date,
                                WbFinanceSyncState.date_to == state.last_attempted_daily_sync_date,
                                WbFinanceSyncState.status == "failed"
                            ).first()
                            if finance_failed:
                                state.last_daily_status = "failed"
                                state.last_daily_error = finance_failed.last_error or "Failed during Go daily sync."
                                db.commit()

                    if state.bootstrap_status != "completed":
                        enqueued += int(await self._enqueue_for_store(FinanceAutomationJob(kind="bootstrap_store", store_id=store.id)))
                        continue

                    from_date = state.last_successful_daily_sync_date or state.bootstrap_range_to
                    if from_date is None:
                        enqueued += int(await self._enqueue_for_store(FinanceAutomationJob(kind="bootstrap_store", store_id=store.id)))
                        continue

                    next_date = from_date + timedelta(days=1)
                    if next_date > target_date:
                        continue

                    completed_days = {
                        item[0]
                        for item in db.query(WbFinanceSyncState.date_from)
                        .filter(
                            WbFinanceSyncState.seller_id == seller.id,
                            WbFinanceSyncState.period == "daily",
                            WbFinanceSyncState.date_from == WbFinanceSyncState.date_to,
                            WbFinanceSyncState.status == "completed",
                            WbFinanceSyncState.date_from >= next_date,
                            WbFinanceSyncState.date_from <= target_date,
                        )
                        .all()
                    }
                    current = next_date
                    while current <= target_date:
                        if current not in completed_days:
                            enqueued += int(
                                await self._enqueue_for_store(
                                    FinanceAutomationJob(kind="daily_store", store_id=store.id, target_date=current.isoformat())
                                )
                            )
                        current += timedelta(days=1)
        finally:
            await redis.delete(FINANCE_AUTO_SYNC_LEADER_LOCK_KEY)
        return enqueued

    async def process_payload(self, payload: str) -> None:
        job = FinanceAutomationJob.from_dict(json.loads(payload))
        dedupe_key = self._dedupe_key(job)
        try:
            await self.process_job(job)
        finally:
            if self._redis is not None:
                await self._redis.delete(dedupe_key)

    async def process_job(self, job: FinanceAutomationJob) -> None:
        redis = self._require_redis()
        store_lock_key = f"finance:auto:sync:lock:store:{job.store_id}"
        acquired = await redis.set(store_lock_key, "1", nx=True, ex=self._settings.finance_auto_job_lock_seconds)
        if not acquired:
            logger.info("Finance automation job skipped because a store lock is already active. store_id=%s kind=%s", job.store_id, job.kind)
            return
        try:
            if job.kind == "bootstrap_store":
                await self._run_bootstrap(job.store_id)
                return
            if job.kind == "daily_store":
                if not job.target_date:
                    raise AppError("finance_auto_invalid_job", "Finance automation daily job is missing targetDate.", 500)
                await self._run_daily_sync(job.store_id, date.fromisoformat(job.target_date))
                return
            raise AppError("finance_auto_invalid_job", f"Unknown finance automation job type: {job.kind}", 500)
        finally:
            await redis.delete(store_lock_key)

    async def _enqueue_for_store(self, job: FinanceAutomationJob) -> bool:
        if self._redis is None:
            self._mark_store_bootstrap_error(job.store_id, "REDIS_URL or REDIS_HOST/REDIS_PASSWORD is not configured.")
            return False
        redis = self._redis
        dedupe_key = self._dedupe_key(job)
        acquired = await redis.set(dedupe_key, "1", nx=True, ex=self._settings.finance_auto_job_lock_seconds)
        if not acquired:
            return False
        await redis.rpush(FINANCE_AUTO_SYNC_QUEUE_KEY, json.dumps(job.to_dict()))
        with self._session_factory() as db:
            store = db.get(Store, job.store_id)
            if store is not None:
                seller = ensure_seller_for_store(db, store)
                state = ensure_finance_automation_state(db, self._settings, seller.id)
                if job.kind == "bootstrap_store" and state.bootstrap_status != "completed":
                    state.bootstrap_status = "queued"
                    state.bootstrap_last_error = None
                    db.commit()
        return True

    async def _run_bootstrap(self, store_id: int) -> None:
        with self._session_factory() as db:
            store = db.get(Store, store_id)
            if store is None:
                return
            seller = ensure_seller_for_store(db, store)
            state = ensure_finance_automation_state(db, self._settings, seller.id)
            state.bootstrap_status = "running"
            state.bootstrap_started_at = datetime.now(UTC)
            state.bootstrap_finished_at = None
            state.bootstrap_last_error = None
            db.commit()
            date_from, date_to = bootstrap_date_range(self._settings)
            state.bootstrap_range_from = date_from
            state.bootstrap_range_to = date_to
            db.commit()

            try:
                product_completed = db.query(WbProductSyncState).filter(
                    WbProductSyncState.seller_id == seller.id,
                    WbProductSyncState.sync_type == "active_cards",
                    WbProductSyncState.status == "completed",
                ).first()

                finance_state = db.query(WbFinanceSyncState).filter(
                    WbFinanceSyncState.seller_id == seller.id,
                    WbFinanceSyncState.date_from == date_from,
                    WbFinanceSyncState.date_to == date_to,
                    WbFinanceSyncState.period == "daily",
                ).one_or_none()

                rabbitmq_url = self._settings.effective_rabbitmq_url

                if not product_completed:
                    publish_rabbitmq_job(
                        rabbitmq_url=rabbitmq_url,
                        routing_key="product.sync",
                        store_id=store_id,
                        payload={"full": True},
                        type_name="product.sync",
                    )
                elif finance_state is None or finance_state.status in {"failed", "interrupted", "idle"}:
                    publish_rabbitmq_job(
                        rabbitmq_url=rabbitmq_url,
                        routing_key="finance.sync",
                        store_id=store_id,
                        payload={
                            "date_from": date_from.isoformat(),
                            "date_to": date_to.isoformat(),
                            "period": "daily",
                            "force": False,
                        },
                        type_name="finance.sync",
                    )
            except Exception as exc:
                state.bootstrap_status = "failed"
                state.bootstrap_finished_at = datetime.now(UTC)
                state.bootstrap_last_error = str(exc)[:1000]
                db.commit()

    async def _run_daily_sync(self, store_id: int, target_date: date) -> None:
        with self._session_factory() as db:
            store = db.get(Store, store_id)
            if store is None:
                return
            seller = ensure_seller_for_store(db, store)
            state = ensure_finance_automation_state(db, self._settings, seller.id)
            state.last_attempted_daily_sync_date = target_date
            state.last_daily_status = "running"
            state.last_daily_error = None
            db.commit()

            try:
                publish_rabbitmq_job(
                    rabbitmq_url=self._settings.effective_rabbitmq_url,
                    routing_key="finance.sync",
                    store_id=store_id,
                    payload={
                        "date_from": target_date.isoformat(),
                        "date_to": target_date.isoformat(),
                        "period": "daily",
                        "force": False,
                    },
                    type_name="finance.sync",
                )
            except Exception as exc:
                state.last_daily_status = "failed"
                state.last_daily_error = str(exc)[:1000]
                db.commit()

    def _require_redis(self) -> Redis:
        if self._redis is None:
            raise AppError("redis_not_configured", "REDIS_URL or REDIS_HOST/REDIS_PASSWORD is not configured.", 500)
        return self._redis

    def _mark_store_bootstrap_error(self, store_id: int, message: str) -> None:
        with self._session_factory() as db:
            store = db.get(Store, store_id)
            if store is None:
                return
            seller = ensure_seller_for_store(db, store)
            state = ensure_finance_automation_state(db, self._settings, seller.id)
            state.bootstrap_status = "failed"
            state.bootstrap_last_error = message[:1000]
            state.bootstrap_finished_at = datetime.now(UTC)
            db.commit()

    @staticmethod
    def _sanitize_error(exc: WbRateLimitError) -> str:
        retry_after = exc.details.get("retry_after_seconds") if isinstance(exc.details, dict) else None
        return f"{exc.message} retry_after_seconds={retry_after}"[:1000]

    @staticmethod
    def _dedupe_key(job: FinanceAutomationJob) -> str:
        if job.kind == "bootstrap_store":
            return f"finance:auto:sync:queued:bootstrap:{job.store_id}"
        return f"finance:auto:sync:queued:daily:{job.store_id}:{job.target_date}"
