from typing import Any

from app.core.config import Settings
from app.services.wb_base_client import WbBaseClient


class WbMarketplaceClient(WbBaseClient):
    """Wildberries Marketplace (FBS) API — warehouses and stock.

    Stock is set per SKU (the size barcode) at a specific seller warehouse.
    """

    def __init__(self, settings: Settings, api_key: str, **kwargs: Any) -> None:
        super().__init__(settings, api_key, base_url=settings.wb_marketplace_base_url, category="marketplace", **kwargs)

    async def get_warehouses(self) -> list[dict[str, Any]]:
        response = await self.request("GET", "/api/v3/warehouses")
        if isinstance(response, list):
            return response
        if isinstance(response, dict) and isinstance(response.get("data"), list):
            return response["data"]
        return []

    async def update_stocks(self, warehouse_id: int, stocks: list[dict[str, Any]]) -> Any:
        """stocks: [{"sku": "<barcode>", "amount": int}] — returns 204 on success."""
        return await self.request(
            "PUT",
            f"/api/v3/stocks/{warehouse_id}",
            json_body={"stocks": stocks},
            allow_no_data=True,
        )
