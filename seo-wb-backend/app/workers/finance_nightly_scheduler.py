import asyncio
import logging

from redis.exceptions import RedisError

import app.models  # noqa: F401 - ensure SQLAlchemy relationship targets are registered.
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.finance_automation_service import FinanceAutomationService
from app.services.redis_client import require_redis


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def run_scheduler() -> None:
    settings = get_settings()
    redis = require_redis(settings)
    try:
        await redis.ping()
    except RedisError:
        logger.exception("Finance nightly scheduler cannot connect to Redis.")
        raise

    service = FinanceAutomationService(settings, SessionLocal, redis)
    logger.info("Finance nightly scheduler started. poll_seconds=%s", settings.finance_scheduler_poll_seconds)
    while True:
        try:
            enqueued = await service.run_scheduler_cycle_async()
            if enqueued:
                logger.info("Finance nightly scheduler enqueued %s job(s).", enqueued)
        except Exception:
            logger.exception("Finance nightly scheduler cycle failed.")
        await asyncio.sleep(max(1, settings.finance_scheduler_poll_seconds))


def main() -> None:
    asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()
