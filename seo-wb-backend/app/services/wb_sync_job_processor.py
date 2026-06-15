import json
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.db.session import SessionLocal
from app.models.card import CardJob
from app.services.card_job_runner import CardJobRunner


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
        if job_type != "card.push":
            raise InvalidSyncJobError(f"Unsupported sync job type: {job_type or '<empty>'}")

        payload = job.get("payload")
        if not isinstance(payload, dict):
            raise InvalidSyncJobError("Sync job payload must be an object.")
        try:
            job_id = int(payload["job_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidSyncJobError("card.push payload.job_id must be an integer.") from exc

        key = f"wb:sync:card.push:{job_id}"
        processing_key = f"{key}:processing"
        completed_key = f"{key}:completed"
        try:
            if self._redis.exists(completed_key):
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
            with SessionLocal() as db:
                card_job = db.get(CardJob, job_id)
                if card_job is None:
                    raise InvalidSyncJobError(f"Card job {job_id} was not found.")
                if card_job.status == "completed":
                    return "duplicate"

            await CardJobRunner(self._settings).run(job_id)

            with SessionLocal() as db:
                card_job = db.get(CardJob, job_id)
                if card_job is None or card_job.status != "completed":
                    error = card_job.error if card_job is not None else "job disappeared"
                    raise RuntimeError(f"Card job {job_id} did not complete: {error}")
            self._redis.set(completed_key, "1", ex=self._settings.rabbitmq_idempotency_ttl_seconds)
            return "completed"
        finally:
            try:
                self._redis.delete(processing_key)
            except RedisError:
                pass
