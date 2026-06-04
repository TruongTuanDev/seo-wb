from datetime import datetime
from typing import Any

from app.core.config import Settings
from app.services.wb_base_client import WbBaseClient


DEFAULT_FINANCE_FIELDS = [
    "reportId",
    "dateFrom",
    "dateTo",
    "createDate",
    "currency",
    "reportType",
    "rrdId",
    "subjectName",
    "nmId",
    "brandName",
    "vendorCode",
    "title",
    "techSize",
    "sku",
    "docTypeName",
    "quantity",
    "retailPrice",
    "retailAmount",
    "salePercent",
    "commissionPercent",
    "officeName",
    "sellerOperName",
    "orderDt",
    "saleDt",
    "rrDate",
    "retailPriceWithDisc",
    "deliveryAmount",
    "returnAmount",
    "deliveryService",
    "ppvzSalesCommission",
    "forPay",
    "acquiringFee",
    "acquiringPercent",
    "paymentProcessing",
    "acquiringBank",
    "penalty",
    "additionalPayment",
    "rebillLogisticCost",
    "paidStorage",
    "deduction",
    "paidAcceptance",
    "orderId",
    "orderUid",
    "srid",
    "shkId",
    "kiz",
    "isB2b",
    "deliveryMethod",
    "cashbackAmount",
    "cashbackDiscount",
    "cashbackCommissionChange",
    "agencyVat",
]


class WbFinanceClient(WbBaseClient):
    def __init__(self, settings: Settings, api_key: str, **kwargs: Any) -> None:
        super().__init__(settings, api_key, base_url=settings.wb_finance_api_base_url, category="finance", **kwargs)

    async def ping(self) -> Any:
        return await self.request("GET", "/ping", rate_scope="ping")

    async def get_balance(self) -> dict[str, Any]:
        return await self.request("GET", "/api/v1/account/balance", rate_scope="finance")

    async def get_sales_reports_detailed_by_period(
        self,
        *,
        date_from: datetime,
        date_to: datetime,
        period: str,
        rrd_id: int = 0,
        fields: list[str] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        payload = {
            "dateFrom": date_from.isoformat(),
            "dateTo": date_to.isoformat(),
            "limit": limit or self._settings.wb_finance_report_limit,
            "rrdId": rrd_id,
            "period": period,
            "fields": fields or DEFAULT_FINANCE_FIELDS,
        }
        data = await self.request(
            "POST",
            "/api/finance/v1/sales-reports/detailed",
            json_body=payload,
            allow_no_data=True,
            rate_scope="finance",
        )
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            nested = data.get("data")
            if isinstance(nested, list):
                return nested
        return []

    async def get_sales_reports_list(
        self,
        *,
        date_from: datetime,
        date_to: datetime,
        period: str,
    ) -> list[dict[str, Any]]:
        payload = {"dateFrom": date_from.isoformat(), "dateTo": date_to.isoformat(), "period": period}
        data = await self.request("POST", "/api/finance/v1/sales-reports/list", json_body=payload, allow_no_data=True, rate_scope="finance")
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            return data["data"]
        return []
