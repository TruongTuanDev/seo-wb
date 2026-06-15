from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from time import time
from uuid import uuid4

from redis.asyncio import Redis


def is_retryable_openai_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code in {429, 500, 502, 503, 504}:
        return True
    return exc.__class__.__name__ in {"RateLimitError", "APIConnectionError", "APITimeoutError"}


_ACQUIRE_SCRIPT = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
local count = redis.call('ZCARD', KEYS[1])
if count < tonumber(ARGV[2]) then
  redis.call('ZADD', KEYS[1], ARGV[3], ARGV[4])
  redis.call('EXPIRE', KEYS[1], ARGV[5])
  return 1
end
return 0
"""


class DistributedImageApiLimiter:
    def __init__(self, redis: Redis | None, *, limit: int, lease_seconds: int, poll_seconds: float = 0.25):
        self._redis = redis
        self._limit = max(1, int(limit))
        self._lease_seconds = max(30, int(lease_seconds))
        self._poll_seconds = max(0.05, float(poll_seconds))
        self._key = "image_generation:openai_slots"

    @asynccontextmanager
    async def slot(self):
        if self._redis is None or not hasattr(self._redis, "eval"):
            yield
            return

        token = uuid4().hex
        while True:
            now = time()
            acquired = await self._redis.eval(
                _ACQUIRE_SCRIPT,
                1,
                self._key,
                now,
                self._limit,
                now + self._lease_seconds,
                token,
                self._lease_seconds * 2,
            )
            if acquired:
                break
            await asyncio.sleep(self._poll_seconds)

        try:
            yield
        finally:
            if hasattr(self._redis, "zrem"):
                await self._redis.zrem(self._key, token)
