import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.core.config import Settings


T = TypeVar("T")

_ai_semaphore: asyncio.Semaphore | None = None
_job_semaphore: asyncio.Semaphore | None = None


def _semaphore(current: asyncio.Semaphore | None, limit: int) -> asyncio.Semaphore:
    if current is None:
        return asyncio.Semaphore(max(1, limit))
    return current


async def run_ai_limited(settings: Settings, fn: Callable[[], Awaitable[T]]) -> T:
    global _ai_semaphore
    _ai_semaphore = _semaphore(_ai_semaphore, settings.max_ai_concurrency)
    async with _ai_semaphore:
        return await fn()


async def run_job_limited(settings: Settings, fn: Callable[[], Awaitable[T]]) -> T:
    global _job_semaphore
    _job_semaphore = _semaphore(_job_semaphore, settings.max_background_jobs)
    async with _job_semaphore:
        return await fn()
