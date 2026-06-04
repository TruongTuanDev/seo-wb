import asyncio

from app.core.errors import AppError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.services.finance_automation_service import FinanceAutomationService
from app.services.redis_client import require_redis


class StoreBootstrapSyncService:
    def __init__(self, settings: Settings, session_factory: sessionmaker[Session]) -> None:
        self._settings = settings
        self._session_factory = session_factory

    def enqueue_store_bootstrap(self, store_id: int) -> None:
        asyncio.run(self._enqueue_store_bootstrap(store_id))

    async def _enqueue_store_bootstrap(self, store_id: int) -> None:
        try:
            redis = require_redis(self._settings)
        except AppError:
            redis = None
        await FinanceAutomationService(self._settings, self._session_factory, redis).enqueue_store_bootstrap_sync_async(store_id)
