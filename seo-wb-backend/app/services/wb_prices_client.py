from typing import Any

from app.core.config import Settings
from app.services.wb_base_client import WbBaseClient


class WbPricesClient(WbBaseClient):
    """Wildberries Discounts & Prices API.

    Prices are set per nmID (one price + optional discount for the whole product,
    across all of its sizes). The upload is asynchronous: WB accepts a task and
    applies it shortly after, so callers verify by reading the goods list.
    """

    def __init__(self, settings: Settings, api_key: str, **kwargs: Any) -> None:
        super().__init__(settings, api_key, base_url=settings.wb_prices_base_url, category="prices", **kwargs)

    async def update_prices(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """items: [{"nmID": int, "price": int, "discount": int (optional)}]"""
        return await self.request("POST", "/api/v2/upload/task", json_body={"data": items})

    async def get_goods(self, *, limit: int = 1000, offset: int = 0, filter_nm_id: int | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if filter_nm_id is not None:
            params["filterNmID"] = filter_nm_id
        response = await self.request("GET", "/api/v2/list/goods/filter", params=params)
        data = response.get("data") if isinstance(response, dict) else None
        if isinstance(data, dict) and isinstance(data.get("listGoods"), list):
            return data["listGoods"]
        return []
