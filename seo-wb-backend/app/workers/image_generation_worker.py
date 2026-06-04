import asyncio
import logging

from redis.exceptions import RedisError

import app.models  # noqa: F401 - ensure SQLAlchemy relationship targets are registered.
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.billing_foundation import IMAGE_JOB_PRIORITY_QUEUES
from app.services.product_image_generator import ProductImageGenerator
from app.services.redis_client import require_redis


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def pop_next_image_job(redis):
    for queue_name in IMAGE_JOB_PRIORITY_QUEUES:
        job_id = await redis.lpop(queue_name)
        if job_id:
            return queue_name, job_id
    return None


async def run_worker() -> None:
    settings = get_settings()
    redis = require_redis(settings)
    try:
        await redis.ping()
    except RedisError:
        logger.exception("Image generation worker cannot connect to Redis.")
        raise

    generator = ProductImageGenerator(settings, redis)
    logger.info("Image generation worker started. queues=%s", ",".join(IMAGE_JOB_PRIORITY_QUEUES))
    while True:
        try:
            item = await pop_next_image_job(redis)
        except RedisError:
            logger.exception("Redis queue read failed; retrying in 5 seconds.")
            await asyncio.sleep(5)
            continue
        if not item:
            await asyncio.sleep(1)
            continue
        queue_name, job_id = item
        db = SessionLocal()
        try:
            logger.info("Processing image generation job %s from queue=%s", job_id, queue_name)
            await generator.run_job(str(job_id), db)
            logger.info("Completed image generation job %s", job_id)
        except Exception:
            logger.exception("Image generation job failed: %s", job_id)
        finally:
            db.close()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
