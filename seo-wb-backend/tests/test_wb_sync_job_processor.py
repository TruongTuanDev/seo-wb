import pytest

from app.core.config import Settings
from app.services.wb_sync_job_processor import InvalidSyncJobError, WbSyncJobProcessor


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def exists(self, key: str) -> bool:
        return key in self.values

    def get(self, key: str):
        return self.values.get(key)

    def set(self, key: str, value: str, nx: bool = False, ex: int | None = None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def delete(self, key: str):
        self.values.pop(key, None)


def _settings() -> Settings:
    return Settings(app_env="test", app_secret_key="test-secret-key", cookie_secure=False)


@pytest.mark.anyio
async def test_processor_deduplicates_completed_sync_job(monkeypatch):
    redis = FakeRedis()
    processor = WbSyncJobProcessor(_settings(), redis)
    calls = []

    async def fake_run(store_id, payload):
        calls.append((store_id, payload))

    monkeypatch.setattr(processor, "_run_product_sync", fake_run)
    job = {
        "type": "product.sync",
        "store_id": 12,
        "payload": {"full": True},
        "idempotency_key": "product.sync:12:full",
    }

    assert await processor.process(job) == "completed"
    assert await processor.process(job) == "duplicate"
    assert calls == [(12, {"full": True})]


@pytest.mark.anyio
async def test_processor_marks_failed_job_to_suppress_duplicate_flood(monkeypatch):
    redis = FakeRedis()
    processor = WbSyncJobProcessor(_settings(), redis)

    async def fake_run(store_id, payload):
        raise RuntimeError("upstream failed")

    monkeypatch.setattr(processor, "_run_product_sync", fake_run)
    job = {"type": "product.sync", "store_id": 12, "payload": {"full": True}}

    with pytest.raises(RuntimeError, match="upstream failed"):
        await processor.process(job)
    assert await processor.process(job) == "duplicate"


@pytest.mark.anyio
async def test_processor_rejects_unknown_job_type():
    processor = WbSyncJobProcessor(_settings(), FakeRedis())

    with pytest.raises(InvalidSyncJobError, match="Unsupported sync job type"):
        await processor.process({"type": "unknown", "store_id": 1, "payload": {}})
