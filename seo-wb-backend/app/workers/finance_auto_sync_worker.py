import asyncio
import logging

from redis.exceptions import RedisError

import app.models  # noqa: F401 - ensure SQLAlchemy relationship targets are registered.
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.finance_automation_service import FINANCE_AUTO_SYNC_QUEUE_KEY, FinanceAutomationService
from app.services.redis_client import require_redis


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def run_worker() -> None:
    settings = get_settings()
    redis = require_redis(settings)
    try:
        await redis.ping()
    except RedisError:
        logger.exception("Finance auto-sync worker cannot connect to Redis.")
        raise

    service = FinanceAutomationService(settings, SessionLocal, redis)
    logger.info("Finance auto-sync worker started. queue=%s", FINANCE_AUTO_SYNC_QUEUE_KEY)
    while True:
        try:
            item = await redis.blpop(FINANCE_AUTO_SYNC_QUEUE_KEY, timeout=5)
        except RedisError:
            logger.exception("Finance auto-sync queue read failed; retrying in 5 seconds.")
            await asyncio.sleep(5)
            continue
        if not item:
            continue
        _, raw_payload = item
        try:
            await service.process_payload(str(raw_payload))
            logger.info("Completed finance auto-sync job payload=%s", raw_payload)
        except Exception:
            logger.exception("Finance auto-sync job failed. payload=%s", raw_payload)


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
