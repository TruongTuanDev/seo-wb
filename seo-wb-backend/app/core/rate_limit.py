import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Lock

from fastapi import Request

from app.core.errors import AppError


@dataclass
class FixedWindowRateLimiter:
    max_requests: int
    window_seconds: int
    _hits: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))
    _lock: Lock = field(default_factory=Lock)

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.max_requests:
                raise AppError(
                    "rate_limited",
                    "Too many requests. Please wait and try again.",
                    429,
                    {"retry_after_seconds": self.window_seconds},
                )
            hits.append(now)


def client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit_dependency(limiter: FixedWindowRateLimiter, key_factory: Callable[[Request], str]):
    def dependency(request: Request) -> None:
        limiter.check(key_factory(request))

    return dependency
