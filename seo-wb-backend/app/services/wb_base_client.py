import asyncio
import time
from collections import defaultdict, deque
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models.finance import ApiDiagnosticLog


_clients: dict[str, httpx.AsyncClient] = {}
_clients_lock = asyncio.Lock()
_server_cooldowns: dict[str, "CooldownState"] = {}
_server_cooldowns_lock = asyncio.Lock()


async def close_wb_clients() -> None:
    async with _clients_lock:
        clients = list(_clients.values())
        _clients.clear()
    await asyncio.gather(*(client.aclose() for client in clients), return_exceptions=True)


class WbApiError(AppError):
    pass


class WbUnauthorizedError(WbApiError):
    pass


class WbRateLimitError(WbApiError):
    pass


class WbNoData(WbApiError):
    pass


@dataclass(frozen=True)
class RateRule:
    max_requests: int
    window_seconds: float
    min_interval_seconds: float = 0.0


@dataclass
class CooldownState:
    seller_key: str
    category: str
    host: str
    method: str
    endpoint: str
    active_until_monotonic: float
    retry_after_seconds: float
    ratelimit_limit: str | None = None
    ratelimit_remaining: str | None = None
    ratelimit_reset: str | None = None
    ratelimit_retry: str | None = None
    source: str = "server_429"


class _InMemoryWbLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._last_hit: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, key: str, rule: RateRule) -> None:
        now = time.monotonic()
        cutoff = now - rule.window_seconds
        async with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= rule.max_requests:
                retry_after = max(rule.window_seconds - (now - hits[0]), 0.0)
                raise WbRateLimitError(
                    "wb_client_rate_limited",
                    "Wildberries client-side rate limit reached.",
                    429,
                    {"retry_after_seconds": round(retry_after, 3), "scope": key},
                )
            last_hit = self._last_hit.get(key)
            if last_hit is not None and rule.min_interval_seconds > 0:
                delta = now - last_hit
                if delta < rule.min_interval_seconds:
                    retry_after = max(rule.min_interval_seconds - delta, 0.0)
                    raise WbRateLimitError(
                        "wb_client_rate_limited",
                        "Wildberries client-side rate limit reached.",
                        429,
                        {"retry_after_seconds": round(retry_after, 3), "scope": key},
                    )
            hits.append(now)
            self._last_hit[key] = now


_limiter = _InMemoryWbLimiter()


def _rule_for_scope(scope: str) -> RateRule:
    if scope == "finance":
        return RateRule(max_requests=1, window_seconds=60.0)
    if scope == "ping":
        return RateRule(max_requests=3, window_seconds=30.0)
    if scope == "content":
        return RateRule(max_requests=100, window_seconds=60.0, min_interval_seconds=0.6)
    return RateRule(max_requests=30, window_seconds=60.0)


class WbBaseClient:
    def __init__(
        self,
        settings: Settings,
        api_key: str,
        *,
        base_url: str,
        category: str,
        db: Session | None = None,
        seller_id: int | None = None,
    ) -> None:
        self._settings = settings
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._category = category
        self._db = db
        self._seller_id = seller_id
        self._seller_key = str(seller_id) if seller_id is not None else "anonymous"
        self._host = urlparse(self._base_url).netloc or self._base_url

    async def _client(self) -> httpx.AsyncClient:
        async with _clients_lock:
            client = _clients.get(self._base_url)
            if client and not client.is_closed:
                return client
            limits = httpx.Limits(
                max_connections=self._settings.wb_max_connections,
                max_keepalive_connections=self._settings.wb_max_keepalive_connections,
            )
            client = httpx.AsyncClient(
                base_url=self._base_url,
                limits=limits,
                proxy=self._settings.wb_proxy_url or None,
            )
            _clients[self._base_url] = client
            return client

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
        timeout: float | None = None,
        rate_scope: str | None = None,
        allow_no_data: bool = False,
    ) -> Any:
        scope = rate_scope or self._category
        rule = _rule_for_scope(scope)
        
        max_retries = 10
        for attempt in range(max_retries):
            try:
                await _limiter.acquire(f"{self._seller_key}:{self._base_url}:{scope}", rule)
                break
            except WbRateLimitError as exc:
                if exc.code == "wb_client_rate_limited" and attempt < max_retries - 1:
                    retry_after = exc.details.get("retry_after_seconds", 0.1)
                    await asyncio.sleep(retry_after + 0.05)
                else:
                    raise

        cooldown_key = self._cooldown_key(method, path)
        await self._check_server_cooldown(cooldown_key)

        client = await self._client()
        request_meta = self._sanitize_request_meta(params=params, json_body=json_body)
        try:
            response = await client.request(
                method.upper(),
                path,
                headers={"Authorization": self._api_key},
                params=params,
                json=json_body,
                timeout=timeout or self._settings.wb_timeout_seconds,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            # httpx timeout/connect errors often carry an empty str(exc); fall back to the
            # exception class name so the failure stays diagnosable (e.g. "ConnectTimeout").
            reason = str(exc) or type(exc).__name__
            detail = f"{type(exc).__name__}: {self._host}{path}" if not str(exc) else str(exc)
            self._log_diagnostic(method, path, None, request_meta, None, detail)
            raise WbApiError(
                "wildberries_network_failed",
                "Wildberries API request failed.",
                502,
                {"reason": reason[:500], "host": self._host, "endpoint": path},
            ) from exc

        payload = self._parse_payload(response)
        response_meta = self._sanitize_response_meta(response, payload)
        self._log_diagnostic(method, path, response.status_code, request_meta, response_meta, None)

        if response.status_code == 204:
            if allow_no_data:
                raise WbNoData("wildberries_no_data", "Wildberries returned no data.", 204)
            return None
        if response.status_code in {401, 403}:
            raise WbUnauthorizedError(
                "wildberries_unauthorized",
                f"Wildberries API returned {response.status_code}.",
                502,
                {"status_code": response.status_code, "payload": payload},
            )
        if response.status_code == 429:
            retry_after = self._retry_after_seconds(response.headers, fallback_seconds=rule.window_seconds)
            await self._set_server_cooldown(cooldown_key, retry_after, response.headers, source="server_429", method=method, path=path)
            raise WbRateLimitError(
                "wildberries_rate_limited",
                "Wildberries API rate limit reached.",
                429,
                {
                    "status_code": 429,
                    "retry_after_seconds": retry_after,
                    "category": self._category,
                    "host": self._host,
                    "endpoint": path,
                    "source": "server_429",
                    "payload": payload,
                },
            )
        retry_after = self._retry_after_seconds(response.headers, fallback_seconds=rule.window_seconds)
        remaining = response.headers.get("X-Ratelimit-Remaining") or response.headers.get("x-ratelimit-remaining")
        if retry_after and remaining == "0":
            await self._set_server_cooldown(cooldown_key, retry_after, response.headers, source="headers_remaining_zero", method=method, path=path)
        if response.status_code >= 400:
            raise WbApiError(
                "wildberries_request_failed",
                f"Wildberries API returned {response.status_code}.",
                502,
                {"status_code": response.status_code, "payload": payload},
            )
        return payload

    def _cooldown_key(self, method: str, path: str) -> str:
        return f"{self._seller_key}:{self._category}:{self._base_url}:{method.upper()}:{path}"

    async def _check_server_cooldown(self, key: str) -> None:
        async with _server_cooldowns_lock:
            state = _server_cooldowns.get(key)
            now = time.monotonic()
            if state is None:
                return
            if state.active_until_monotonic <= now:
                _server_cooldowns.pop(key, None)
                return
            retry_after_seconds = round(state.active_until_monotonic - now, 3)
            self._log_diagnostic(
                state.method,
                state.endpoint,
                429,
                None,
                {
                    "source": "local_cooldown",
                    "category": state.category,
                    "host": state.host,
                    "retry_after_seconds": retry_after_seconds,
                    "headers": {
                        "x-ratelimit-limit": state.ratelimit_limit,
                        "x-ratelimit-remaining": state.ratelimit_remaining,
                        "x-ratelimit-retry": state.ratelimit_retry,
                        "x-ratelimit-reset": state.ratelimit_reset,
                    },
                },
                None,
            )
            raise WbRateLimitError(
                "wildberries_rate_limited",
                "Wildberries API endpoint is still in cooldown.",
                429,
                {
                    "retry_after_seconds": retry_after_seconds,
                    "category": state.category,
                    "host": state.host,
                    "endpoint": state.endpoint,
                    "source": "local_cooldown",
                },
            )

    async def _set_server_cooldown(
        self,
        key: str,
        retry_after: float | None,
        headers: Mapping[str, str] | None,
        *,
        source: str,
        method: str,
        path: str,
    ) -> None:
        if retry_after is None or retry_after <= 0:
            return
        async with _server_cooldowns_lock:
            _server_cooldowns[key] = CooldownState(
                seller_key=self._seller_key,
                category=self._category,
                host=self._host,
                method=method.upper(),
                endpoint=path,
                active_until_monotonic=time.monotonic() + retry_after,
                retry_after_seconds=retry_after,
                ratelimit_limit=(headers.get("X-Ratelimit-Limit") if headers else None),
                ratelimit_remaining=(headers.get("X-Ratelimit-Remaining") if headers else None),
                ratelimit_reset=(headers.get("X-Ratelimit-Reset") if headers else None),
                ratelimit_retry=(headers.get("X-Ratelimit-Retry") if headers else None),
                source=source,
            )

    @staticmethod
    def _parse_payload(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text[:2000]}

    @staticmethod
    def _retry_after_seconds(headers: Mapping[str, str], fallback_seconds: float | None = None) -> float | None:
        for key in ("X-Ratelimit-Retry", "X-Ratelimit-Reset", "Retry-After"):
            value = headers.get(key) or headers.get(key.lower())
            if not value:
                continue
            try:
                return float(value)
            except ValueError:
                continue
        return fallback_seconds

    def _sanitize_request_meta(self, *, params: Mapping[str, Any] | None, json_body: Any) -> dict[str, Any]:
        body = json_body
        if isinstance(body, dict):
            body = {key: value for key, value in body.items() if "token" not in key.casefold()}
        return {"params": dict(params or {}), "json": body}

    @staticmethod
    def _sanitize_response_meta(response: httpx.Response, payload: Any) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "headers": {
                "x-ratelimit-limit": response.headers.get("X-Ratelimit-Limit"),
                "x-ratelimit-remaining": response.headers.get("X-Ratelimit-Remaining"),
                "x-ratelimit-retry": response.headers.get("X-Ratelimit-Retry"),
                "x-ratelimit-reset": response.headers.get("X-Ratelimit-Reset"),
            }
        }
        if isinstance(payload, list):
            meta["payload_count"] = len(payload)
        elif isinstance(payload, dict):
            meta["payload_keys"] = sorted(payload.keys())[:50]
        else:
            meta["payload_type"] = type(payload).__name__
        return meta

    def _log_diagnostic(
        self,
        method: str,
        endpoint: str,
        status_code: int | None,
        request_meta: dict[str, Any] | None,
        response_meta: dict[str, Any] | None,
        error_text: str | None,
    ) -> None:
        if self._db is None:
            return
        self._db.add(
            ApiDiagnosticLog(
                seller_id=self._seller_id,
                category=self._category,
                endpoint=endpoint,
                method=method.upper(),
                status_code=status_code,
                request_meta=request_meta,
                response_meta=response_meta,
                error_text=error_text[:1000] if error_text else None,
            )
        )
        self._db.commit()


async def get_active_cooldowns(*, seller_id: int | None = None, category: str | None = None) -> list[dict[str, Any]]:
    seller_key = str(seller_id) if seller_id is not None else None
    now = time.monotonic()
    items: list[dict[str, Any]] = []
    async with _server_cooldowns_lock:
        expired = [key for key, state in _server_cooldowns.items() if state.active_until_monotonic <= now]
        for key in expired:
            _server_cooldowns.pop(key, None)
        for state in _server_cooldowns.values():
            if seller_key is not None and state.seller_key != seller_key:
                continue
            if category is not None and state.category != category:
                continue
            items.append(
                {
                    "sellerId": int(state.seller_key) if state.seller_key.isdigit() else None,
                    "category": state.category,
                    "host": state.host,
                    "method": state.method,
                    "endpoint": state.endpoint,
                    "retryAfterSeconds": round(state.active_until_monotonic - now, 3),
                    "source": state.source,
                    "headers": {
                        "x-ratelimit-limit": state.ratelimit_limit,
                        "x-ratelimit-remaining": state.ratelimit_remaining,
                        "x-ratelimit-retry": state.ratelimit_retry,
                        "x-ratelimit-reset": state.ratelimit_reset,
                    },
                }
            )
    return sorted(items, key=lambda item: (item["category"], item["endpoint"]))
