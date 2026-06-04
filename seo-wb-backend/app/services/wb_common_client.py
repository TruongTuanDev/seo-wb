from typing import Any

from app.core.config import Settings
from app.services.wb_base_client import WbBaseClient


class WbCommonClient(WbBaseClient):
    def __init__(self, settings: Settings, api_key: str, **kwargs: Any) -> None:
        super().__init__(settings, api_key, base_url=settings.wb_common_api_base_url, category="common", **kwargs)

    async def ping(self) -> Any:
        return await self.request("GET", "/ping", rate_scope="ping")

    async def get_seller_info(self) -> dict[str, Any]:
        payload = await self.request("GET", "/api/v1/seller-info")
        if isinstance(payload, dict) and "data" in payload and isinstance(payload["data"], dict):
            return payload["data"]
        return payload if isinstance(payload, dict) else {"raw": payload}
