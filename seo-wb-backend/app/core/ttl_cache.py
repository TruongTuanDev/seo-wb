import time
from copy import deepcopy
from threading import Lock
from typing import Generic, TypeVar


T = TypeVar("T")


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: int):
        self._ttl_seconds = max(0, ttl_seconds)
        self._items: dict[str, tuple[float, T]] = {}
        self._lock = Lock()

    def get(self, key: str) -> T | None:
        if self._ttl_seconds <= 0:
            return None
        now = time.monotonic()
        with self._lock:
            item = self._items.get(key)
            if not item:
                return None
            expires_at, value = item
            if expires_at <= now:
                self._items.pop(key, None)
                return None
            return deepcopy(value)

    def set(self, key: str, value: T) -> None:
        if self._ttl_seconds <= 0:
            return
        with self._lock:
            self._items[key] = (time.monotonic() + self._ttl_seconds, deepcopy(value))

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
