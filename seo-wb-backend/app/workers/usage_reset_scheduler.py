import asyncio
import logging

import app.models  # noqa: F401 - ensure SQLAlchemy relationship targets are registered.
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.usage_reset_scheduler import run_monthly_usage_reset_cycle


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def run_scheduler() -> None:
    settings = get_settings()
    logger.info("Usage reset scheduler started. poll_seconds=%s", settings.usage_reset_scheduler_poll_seconds)
    while True:
        db = SessionLocal()
        try:
            reset_count = run_monthly_usage_reset_cycle(db)
            if reset_count:
                logger.info("Usage reset scheduler processed %s user(s).", reset_count)
        except Exception:
            logger.exception("Usage reset scheduler cycle failed.")
        finally:
            db.close()
        await asyncio.sleep(max(60, settings.usage_reset_scheduler_poll_seconds))


def main() -> None:
    asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()
