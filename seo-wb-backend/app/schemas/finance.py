from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


GroupBy = Literal["day", "week", "month", "year"]
FinancePeriod = Literal["daily", "weekly"]


class MoneyStringModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SellerFinanceSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str | None = None
    default_tax_mode: str | None = None
    default_tax_rate: str | float | None = None
    tax_base: str | None = None
    default_packaging_cost: str | float | None = None
    default_labeling_cost: str | float | None = None
    default_shipping_to_warehouse_cost: str | float | None = None
    default_other_unit_cost: str | float | None = None


class ProductFinanceSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    cost_price: str | float = "0"
    cost_currency: str = "RUB"
    packaging_cost: str | float = "0"
    labeling_cost: str | float = "0"
    shipping_to_warehouse_cost: str | float = "0"
    other_unit_cost: str | float = "0"
    tax_mode: str | None = None
    tax_rate: str | float | None = None
    tax_base: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    note: str | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be greater than or equal to effective_from")
        return self


class ProductFinanceBulkItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int
    cost_price: str | float = "0"


class ProductFinanceBulkSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ProductFinanceBulkItemRequest]


class ExternalCostRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cost_date: date
    period_from: date | None = None
    period_to: date | None = None
    cost_type: str
    amount: str | float
    currency: str = "RUB"
    allocation_method: str = "BY_REVENUE"
    product_id: int | None = None
    note: str | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.period_from and self.period_to and self.period_to < self.period_from:
            raise ValueError("period_to must be greater than or equal to period_from")
        return self


class FinanceSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: date
    date_to: date
    period: FinancePeriod = "daily"
    force: bool = False

    @model_validator(mode="after")
    def validate_dates(self):
        if self.date_to < self.date_from:
            raise ValueError("date_to must be greater than or equal to date_from")
        return self


class FinanceAiAnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: date
    date_to: date
    group_by: GroupBy = "day"

    @model_validator(mode="after")
    def validate_dates(self):
        if self.date_to < self.date_from:
            raise ValueError("date_to must be greater than or equal to date_from")
        return self


class PaginationMeta(BaseModel):
    page: int
    perPage: int
    total: int


class SellerFinanceSettingsResponse(BaseModel):
    id: int
    sellerId: int
    currency: str
    defaultTaxMode: str
    defaultTaxRate: str
    taxBase: str
    defaultPackagingCost: str
    defaultLabelingCost: str
    defaultShippingToWarehouseCost: str
    defaultOtherUnitCost: str


class ProductFinanceSettingsResponse(BaseModel):
    id: int
    sellerId: int
    productId: int
    costPrice: str
    costCurrency: str
    packagingCost: str
    labelingCost: str
    shippingToWarehouseCost: str
    otherUnitCost: str
    taxMode: str | None
    taxRate: str | None
    taxBase: str | None
    effectiveFrom: str
    effectiveTo: str | None
    note: str | None


class ProductFinanceSettingsListResponse(BaseModel):
    items: list[ProductFinanceSettingsResponse]
    page: int
    perPage: int
    total: int


class ProductFinanceCatalogItemResponse(BaseModel):
    productId: int
    nmId: int
    vendorCode: str | None
    title: str | None
    subjectName: str | None
    brand: str | None
    photoSquareUrl: str | None
    photoBigUrl: str | None
    hasCostSettings: bool
    settingId: int | None
    costPrice: str | None
    costCurrency: str | None
    packagingCost: str | None
    labelingCost: str | None
    shippingToWarehouseCost: str | None
    otherUnitCost: str | None
    taxMode: str | None
    taxRate: str | None
    taxBase: str | None
    effectiveFrom: str | None
    effectiveTo: str | None
    note: str | None


class ProductFinanceCatalogFacetsResponse(BaseModel):
    brands: list[str]
    subjects: list[str]


class ProductFinanceCatalogResponse(BaseModel):
    items: list[ProductFinanceCatalogItemResponse]
    page: int
    perPage: int
    total: int
    facets: ProductFinanceCatalogFacetsResponse


class MissingFinanceProductResponse(BaseModel):
    id: int
    nmId: int
    vendorCode: str | None
    title: str | None


class MissingFinanceProductsResponse(BaseModel):
    items: list[MissingFinanceProductResponse]


class ExternalCostResponse(BaseModel):
    id: int
    sellerId: int
    costDate: str
    periodFrom: str | None
    periodTo: str | None
    costType: str
    amount: str
    currency: str
    allocationMethod: str
    productId: int | None
    note: str | None


class ExternalCostsListResponse(BaseModel):
    items: list[ExternalCostResponse]
    page: int
    perPage: int
    total: int


class ProductSyncResponse(BaseModel):
    status: str
    totalSynced: int
    cursorUpdatedAt: str | None
    cursorNmId: int | None
    batches: int


class ProductSyncStatusResponse(BaseModel):
    status: str
    cursorUpdatedAt: str | None = None
    cursorNmId: int | None = None
    totalSynced: int | None = None
    lastError: str | None = None
    startedAt: str | None = None
    finishedAt: str | None = None


class WbProductResponse(BaseModel):
    id: int
    nmId: int
    imtId: int | None
    vendorCode: str | None
    brand: str | None
    title: str | None
    description: str | None
    subjectId: int | None
    subjectName: str | None
    photoBigUrl: str | None
    photoSquareUrl: str | None
    sizes: list[dict[str, Any]]
    skus: list[str]
    characteristics: list[dict[str, Any]]
    rawData: dict[str, Any]


class WbProductsListResponse(BaseModel):
    items: list[WbProductResponse]
    page: int
    perPage: int
    total: int


class FinanceSyncResponse(BaseModel):
    status: str
    rowsInserted: int
    lastRrdId: int


class FinanceSyncStatusResponse(BaseModel):
    status: str
    lastRrdId: int | None = None
    totalRows: int | None = None
    lastError: str | None = None


class FinanceRawRowResponse(BaseModel):
    id: int
    rrdId: int
    nmId: int | None
    vendorCode: str | None
    rawData: dict[str, Any]


class FinanceRawRowsResponse(BaseModel):
    items: list[FinanceRawRowResponse]


class FinancePeriodResponse(BaseModel):
    dateFrom: str
    dateTo: str


class FinanceSummaryResponse(BaseModel):
    period: FinancePeriodResponse
    grossRevenue: str
    forPay: str
    wbCosts: str
    cogs: str
    externalAllocatedCosts: str
    profitBeforeTax: str
    taxAmount: str
    profitAfterTax: str
    profitMargin: str
    costCompletenessPercent: str
    rowsCount: int
    productsCount: int


class TimelineItemResponse(BaseModel):
    bucket: str
    forPay: str


class TimelineResponse(BaseModel):
    items: list[TimelineItemResponse]


class ProductBreakdownItemResponse(BaseModel):
    productId: int | None
    nmId: int | None
    vendorCode: str | None
    title: str | None
    quantity: str
    grossRevenue: str
    forPay: str
    wbCosts: str
    cogs: str
    externalAllocatedCosts: str
    profitBeforeTax: str
    taxAmount: str
    profitAfterTax: str
    profitMargin: str
    hasCostSettings: bool
    costMeta: dict[str, Any]


class ProductBreakdownResponse(BaseModel):
    items: list[ProductBreakdownItemResponse]
    page: int
    perPage: int
    total: int


class CostBreakdownResponse(BaseModel):
    wbCosts: str
    cogs: str
    externalAllocatedCosts: str


class InsightItemResponse(BaseModel):
    type: str
    level: Literal["info", "warning", "danger"]
    message: str
    affectedMetric: str
    productIds: list[int]
    recommendedAction: str


class InsightsResponse(BaseModel):
    items: list[InsightItemResponse]


class AllocationPreviewItemResponse(BaseModel):
    productId: int | None
    nmId: int | None
    vendorCode: str | None
    allocatedAmount: str


class AllocationPreviewResponse(BaseModel):
    items: list[AllocationPreviewItemResponse]


class AiAnalyzeResponse(BaseModel):
    snapshotId: int
    analysis: dict[str, Any]


class AiSnapshotResponse(BaseModel):
    id: int
    dateFrom: str
    dateTo: str
    aiAnalysis: dict[str, Any] | None


class AiSnapshotsResponse(BaseModel):
    items: list[AiSnapshotResponse]


class ReconciliationResponse(BaseModel):
    warning: str | None
    calculatedSummary: FinanceSummaryResponse
    reportListCount: int
    reportListTotals: dict[str, str]
    differences: dict[str, str]


class CooldownStateResponse(BaseModel):
    sellerId: int | None
    category: str
    host: str
    method: str
    endpoint: str
    retryAfterSeconds: float
    source: str
    headers: dict[str, Any]


class ApiAvailabilityResponse(BaseModel):
    available: bool
    inCooldown: bool
    activeCooldownCount: int
    cooldowns: list[CooldownStateResponse]


class SyncStatusSummaryResponse(BaseModel):
    status: str | None
    lastSuccessfulAt: str | None
    lastFailedAt: str | None
    lastError: str | None


class FinanceSystemStatusResponse(BaseModel):
    contentApi: ApiAvailabilityResponse
    financeApi: ApiAvailabilityResponse
    commonApi: ApiAvailabilityResponse
    sellerInfoApi: ApiAvailabilityResponse
    activeCooldowns: list[CooldownStateResponse]
    lastSuccessfulProductSyncAt: str | None
    lastSuccessfulFinanceSyncAt: str | None
    lastFailedSyncAt: str | None
    lastFailedSyncError: str | None
    geminiConfigured: bool
    hasProductsMissingFinanceSettings: bool
    missingFinanceSettingsCount: int
    hasUnmappedFinanceRows: bool
    unmappedFinanceRowsCount: int
    automationTimezone: str | None = None
    bootstrapStatus: str | None = None
    bootstrapRangeFrom: str | None = None
    bootstrapRangeTo: str | None = None
    bootstrapFinishedAt: str | None = None
    lastSuccessfulDailySyncDate: str | None = None
    lastDailySyncStatus: str | None = None
    lastDailySyncError: str | None = None
    nextScheduledRunAt: str | None = None
