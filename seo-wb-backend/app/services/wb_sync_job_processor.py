import json
import logging
from datetime import UTC, date, datetime
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.security import decrypt_secret
from app.db.session import SessionLocal
from app.models.card import CardJob
from app.models.finance import WbFinanceSyncState
from app.models.store import Store
from app.models.wb_product import WbProductSyncState
from app.services.card_job_runner import CardJobRunner
from app.services.finance_service import FinanceSyncService
from app.services.finance_automation_service import ensure_finance_automation_state
from app.services.seller_service import ensure_seller_for_store
from app.services.wb_content_client import WbContentClient
from app.services.wb_finance_client import WbFinanceClient
from app.services.wb_product_sync_service import WbProductSyncService


logger = logging.getLogger(__name__)


class InvalidSyncJobError(ValueError):
    pass


class RetryableSyncJobError(RuntimeError):
    pass


class WbSyncJobProcessor:
    def __init__(self, settings: Settings, redis: Redis) -> None:
        self._settings = settings
        self._redis = redis

    async def process(self, job: dict[str, Any]) -> str:
        job_type = str(job.get("type") or "").strip()
        if job_type not in {"card.push", "product.sync", "finance.sync"}:
            raise InvalidSyncJobError(f"Unsupported sync job type: {job_type or '<empty>'}")

        try:
            store_id = int(job["store_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidSyncJobError("Sync job store_id must be an integer.") from exc

        payload = job.get("payload")
        if not isinstance(payload, dict):
            raise InvalidSyncJobError("Sync job payload must be an object.")

        idempotency_key = str(job.get("idempotency_key") or self._fallback_idempotency_key(job_type, store_id, payload))
        completed_key = f"wb:sync:completed:{idempotency_key}"
        failed_key = f"wb:sync:failed:{idempotency_key}"
        processing_key = f"wb:sync:processing:{idempotency_key}"

        try:
            if self._redis.exists(completed_key):
                return "duplicate"
            failed_value = self._redis.get(failed_key)
            if failed_value:
                try:
                    failed_payload = json.loads(failed_value)
                    failed_message = str(failed_payload.get("error") or "Previous sync attempt failed.")
                except (TypeError, json.JSONDecodeError):
                    failed_message = "Previous sync attempt failed."
                try:
                    self._record_automation_failure(job_type, store_id, payload, RuntimeError(failed_message))
                except Exception:
                    logger.exception("Failed to persist duplicate WB sync failure. store_id=%s type=%s", store_id, job_type)
                return "duplicate"
            acquired = self._redis.set(
                processing_key,
                "1",
                nx=True,
                ex=self._settings.rabbitmq_processing_lock_seconds,
            )
        except RedisError as exc:
            raise RetryableSyncJobError(f"Redis idempotency check failed: {exc}") from exc

        if not acquired:
            return "duplicate"

        try:
            if job_type == "card.push":
                await self._run_card_push(payload)
            elif job_type == "product.sync":
                await self._run_product_sync(store_id, payload)
            else:
                await self._run_finance_sync(store_id, payload)
        except Exception as exc:
            try:
                self._record_automation_failure(job_type, store_id, payload, exc)
            except Exception:
                logger.exception("Failed to persist WB sync automation failure. store_id=%s type=%s", store_id, job_type)
            try:
                self._redis.set(
                    failed_key,
                    json.dumps({"error": str(exc)[:1000]}),
                    ex=self._settings.rabbitmq_failed_idempotency_ttl_seconds,
                )
            except RedisError:
                pass
            raise
        else:
            try:
                self._redis.set(
                    completed_key,
                    "1",
                    ex=self._settings.rabbitmq_idempotency_ttl_seconds,
                )
            except RedisError as exc:
                raise RetryableSyncJobError(f"Redis idempotency completion write failed: {exc}") from exc
            return "completed"
        finally:
            try:
                self._redis.delete(processing_key)
            except RedisError:
                pass

    async def _run_card_push(self, payload: dict[str, Any]) -> None:
        try:
            job_id = int(payload["job_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidSyncJobError("card.push payload.job_id must be an integer.") from exc

        with SessionLocal() as db:
            card_job = db.get(CardJob, job_id)
            if card_job is None:
                raise InvalidSyncJobError(f"Card job {job_id} was not found.")
            if card_job.status in {"completed", "failed"}:
                return

        await CardJobRunner(self._settings).run(job_id)

        with SessionLocal() as db:
            card_job = db.get(CardJob, job_id)
            if card_job is None or card_job.status != "completed":
                error = card_job.error if card_job is not None else "job disappeared"
                raise RuntimeError(f"Card job {job_id} did not complete: {error}")

    async def _run_product_sync(self, store_id: int, payload: dict[str, Any]) -> None:
        full = bool(payload.get("full", False))
        with SessionLocal() as db:
            store = db.get(Store, store_id)
            if store is None:
                raise InvalidSyncJobError(f"Store {store_id} was not found.")
            seller = ensure_seller_for_store(db, store)
            state = db.query(WbProductSyncState).filter_by(seller_id=seller.id, sync_type="active_cards").one_or_none()
            if full and state is not None and state.status == "completed":
                return
            api_key = decrypt_secret(self._settings, store.wb_api_key_encrypted)
            client = WbContentClient(self._settings, api_key, db=db, seller_id=seller.id)
            await WbProductSyncService(db, seller, client).sync(full=full)

    async def _run_finance_sync(self, store_id: int, payload: dict[str, Any]) -> None:
        try:
            date_from = date.fromisoformat(str(payload["date_from"]))
            date_to = date.fromisoformat(str(payload["date_to"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidSyncJobError("finance.sync requires ISO date_from and date_to values.") from exc

        period = str(payload.get("period") or "daily")
        force = bool(payload.get("force", False))
        with SessionLocal() as db:
            store = db.get(Store, store_id)
            if store is None:
                raise InvalidSyncJobError(f"Store {store_id} was not found.")
            seller = ensure_seller_for_store(db, store)
            state = (
                db.query(WbFinanceSyncState)
                .filter(
                    WbFinanceSyncState.seller_id == seller.id,
                    WbFinanceSyncState.date_from == date_from,
                    WbFinanceSyncState.date_to == date_to,
                    WbFinanceSyncState.period == period,
                )
                .one_or_none()
            )
            if not force and state is not None and state.status == "completed":
                return
            api_key = decrypt_secret(self._settings, store.wb_api_key_encrypted)
            client = WbFinanceClient(self._settings, api_key, db=db, seller_id=seller.id)
            await FinanceSyncService(db, self._settings, seller, client).sync(
                date_from=date_from,
                date_to=date_to,
                period=period,
                force=force,
            )

    @staticmethod
    def _fallback_idempotency_key(job_type: str, store_id: int, payload: dict[str, Any]) -> str:
        if job_type == "card.push":
            return f"card.push:{payload.get('job_id')}"
        if job_type == "product.sync":
            mode = "full" if payload.get("full") else "incremental"
            return f"product.sync:{store_id}:{mode}"
        return (
            f"finance.sync:{store_id}:{payload.get('date_from')}:{payload.get('date_to')}:"
            f"{payload.get('period') or 'daily'}"
        )

    def _record_automation_failure(
        self,
        job_type: str,
        store_id: int,
        payload: dict[str, Any],
        exc: Exception,
    ) -> None:
        if job_type not in {"product.sync", "finance.sync"}:
            return
        with SessionLocal() as db:
            store = db.get(Store, store_id)
            if store is None:
                return
            seller = ensure_seller_for_store(db, store)
            state = ensure_finance_automation_state(db, self._settings, seller.id)
            message = str(exc)[:1000]
            now = datetime.now(UTC)
            if job_type == "product.sync":
                state.bootstrap_status = "failed"
                state.bootstrap_finished_at = now
                state.bootstrap_last_error = message
            else:
                date_from = str(payload.get("date_from") or "")
                date_to = str(payload.get("date_to") or "")
                is_bootstrap = (
                    state.bootstrap_range_from is not None
                    and state.bootstrap_range_to is not None
                    and date_from == state.bootstrap_range_from.isoformat()
                    and date_to == state.bootstrap_range_to.isoformat()
                )
                if is_bootstrap:
                    state.bootstrap_status = "failed"
                    state.bootstrap_finished_at = now
                    state.bootstrap_last_error = message
                else:
                    state.last_daily_status = "failed"
                    state.last_daily_error = message
            db.commit()
