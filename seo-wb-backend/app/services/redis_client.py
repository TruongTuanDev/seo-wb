from functools import lru_cache

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.errors import AppError


@lru_cache
def get_redis_client(redis_url: str) -> Redis:
    return Redis.from_url(redis_url, decode_responses=True)


def require_redis(settings: Settings) -> Redis:
    redis_url = settings.effective_redis_url
    if not redis_url:
        raise AppError("redis_not_configured", "REDIS_URL or REDIS_HOST/REDIS_PASSWORD is not configured.", 500)
    return get_redis_client(redis_url)
