import asyncio
import json
import logging
from contextlib import suppress

from redis.exceptions import RedisError

import app.models  # noqa: F401 - ensure SQLAlchemy relationship targets are registered.
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.billing_foundation import IMAGE_JOB_PRIORITY_QUEUES
from app.services.product_image_generator import ProductImageGenerator
from app.services.redis_client import require_redis


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
IMAGE_JOB_PROCESSING_QUEUE = "image_jobs_processing"


async def pop_next_image_job(redis, lease_seconds: int | None = None):
    for queue_name in IMAGE_JOB_PRIORITY_QUEUES:
        if hasattr(redis, "lmove"):
            job_id = await redis.lmove(queue_name, IMAGE_JOB_PROCESSING_QUEUE, "LEFT", "RIGHT")
        else:
            job_id = await redis.lpop(queue_name)
        if job_id:
            if lease_seconds is not None:
                acquired = await redis.set(
                    f"image_generation_job_lease:{job_id}",
                    "1",
                    nx=True,
                    ex=lease_seconds,
                )
                if not acquired:
                    await _ack_job(redis, str(job_id))
                    continue
            return queue_name, job_id
    return None


async def _ack_job(redis, job_id: str) -> None:
    if hasattr(redis, "lrem"):
        await redis.lrem(IMAGE_JOB_PROCESSING_QUEUE, 1, job_id)


async def _heartbeat(redis, job_id: str, lease_seconds: int) -> None:
    lease_key = f"image_generation_job_lease:{job_id}"
    interval = max(10, lease_seconds // 3)
    while True:
        await asyncio.sleep(interval)
        await redis.expire(lease_key, lease_seconds)
        raw_state = await redis.get(f"image_generation_job:{job_id}")
        if not raw_state:
            continue
        state = json.loads(raw_state)
        for key_name in ("lock_key", "store_lock_key"):
            if state.get(key_name):
                await redis.expire(str(state[key_name]), lease_seconds)


async def recover_abandoned_jobs(redis) -> int:
    if not hasattr(redis, "lrange"):
        return 0
    recovered = 0
    for job_id in await redis.lrange(IMAGE_JOB_PROCESSING_QUEUE, 0, -1):
        if await redis.get(f"image_generation_job_lease:{job_id}"):
            continue
        recovery_lease = await redis.set(f"image_generation_job_lease:{job_id}", "recovery", nx=True, ex=30)
        if not recovery_lease:
            continue
        raw_state = await redis.get(f"image_generation_job:{job_id}")
        await redis.lrem(IMAGE_JOB_PROCESSING_QUEUE, 1, job_id)
        if not raw_state:
            await redis.delete(f"image_generation_job_lease:{job_id}")
            continue
        state = json.loads(raw_state)
        if state.get("status") in {"completed", "completed_with_warnings", "failed", "failed_validation"}:
            await redis.delete(f"image_generation_job_lease:{job_id}")
            continue
        state["status"] = "queued"
        state["step"] = "recovered_after_worker_exit"
        await redis.set(f"image_generation_job:{job_id}", json.dumps(state, ensure_ascii=False), ex=60 * 60 * 24)
        await redis.rpush(str(state.get("queue_name") or "image_jobs_normal"), job_id)
        await redis.delete(f"image_generation_job_lease:{job_id}")
        recovered += 1
    return recovered


async def _process_job(redis, generator: ProductImageGenerator, queue_name: str, job_id: str, lease_seconds: int) -> None:
    lease_key = f"image_generation_job_lease:{job_id}"
    heartbeat = asyncio.create_task(_heartbeat(redis, job_id, lease_seconds))
    db = SessionLocal()
    try:
        logger.info("Processing image generation job %s from queue=%s", job_id, queue_name)
        await generator.run_job(str(job_id), db)
        logger.info("Completed image generation job %s", job_id)
    except Exception:
        logger.exception("Image generation job failed: %s", job_id)
    finally:
        heartbeat.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat
        db.close()
        await redis.delete(lease_key)
        await _ack_job(redis, job_id)


async def run_worker() -> None:
    settings = get_settings()
    redis = require_redis(settings)
    try:
        await redis.ping()
    except RedisError:
        logger.exception("Image generation worker cannot connect to Redis.")
        raise

    generator = ProductImageGenerator(settings, redis)
    concurrency = max(1, int(settings.image_worker_concurrency))
    running: set[asyncio.Task] = set()
    last_recovery = 0.0
    loop = asyncio.get_running_loop()
    logger.info(
        "Image generation worker started. queues=%s concurrency=%d global_openai_limit=%d",
        ",".join(IMAGE_JOB_PRIORITY_QUEUES),
        concurrency,
        settings.image_global_concurrency,
    )

    while True:
        now = loop.time()
        if now - last_recovery >= settings.image_job_recovery_interval_seconds:
            recovered = await recover_abandoned_jobs(redis)
            if recovered:
                logger.warning("Recovered %d abandoned image generation job(s).", recovered)
            last_recovery = now

        running = {task for task in running if not task.done()}
        if len(running) >= concurrency:
            await asyncio.wait(running, return_when=asyncio.FIRST_COMPLETED)
            continue

        try:
            item = await pop_next_image_job(redis, settings.image_job_lease_seconds)
        except RedisError:
            logger.exception("Redis queue read failed; retrying in 5 seconds.")
            await asyncio.sleep(5)
            continue
        if not item:
            await asyncio.sleep(1)
            continue
        queue_name, job_id = item
        running.add(asyncio.create_task(_process_job(redis, generator, queue_name, str(job_id), settings.image_job_lease_seconds)))


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
