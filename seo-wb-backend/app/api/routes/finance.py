from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_store
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import decrypt_secret
from app.db.session import get_db
from app.models.user import User
from app.schemas.finance import (
    AiAnalyzeResponse,
    AiSnapshotsResponse,
    AllocationPreviewResponse,
    CostBreakdownResponse,
    ExternalCostRequest,
    ExternalCostResponse,
    ExternalCostsListResponse,
    FinanceAiAnalyzeRequest,
    FinanceRawRowsResponse,
    FinanceSummaryResponse,
    FinanceSyncRequest,
    FinanceSyncResponse,
    FinanceSyncStatusResponse,
    FinanceSystemStatusResponse,
    InsightsResponse,
    MissingFinanceProductsResponse,
    ProductBreakdownResponse,
    ProductFinanceBulkSettingsRequest,
    ProductFinanceCatalogResponse,
    ProductFinanceSettingsRequest,
    ProductFinanceSettingsListResponse,
    ProductFinanceSettingsResponse,
    ReconciliationResponse,
    SellerFinanceSettingsRequest,
    SellerFinanceSettingsResponse,
    TimelineResponse,
)
from app.services.finance_service import (
    FinanceAggregationService,
    FinanceAiAnalysisService,
    FinanceSettingsService,
    FinanceSystemStatusService,
    FinanceSyncService,
)
from app.services.seller_service import ensure_seller_for_store
from app.services.wb_finance_client import WbFinanceClient


router = APIRouter(prefix="/finance", tags=["finance"])


def _seller_and_client(db: Session, settings: Settings, user: User, store_id: int):
    store = get_owned_store(db, user, store_id)
    seller = ensure_seller_for_store(db, store)
    api_key = decrypt_secret(settings, store.wb_api_key_encrypted)
    client = WbFinanceClient(settings, api_key, db=db, seller_id=seller.id)
    return seller, client


@router.get("/settings", response_model=SellerFinanceSettingsResponse)
def get_seller_settings(
    store_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    row = FinanceSettingsService(db, seller).get_seller_settings()
    return {
        "id": row.id,
        "sellerId": row.seller_id,
        "currency": row.currency,
        "defaultTaxMode": row.default_tax_mode,
        "defaultTaxRate": str(row.default_tax_rate),
        "taxBase": row.tax_base,
        "defaultPackagingCost": str(row.default_packaging_cost),
        "defaultLabelingCost": str(row.default_labeling_cost),
        "defaultShippingToWarehouseCost": str(row.default_shipping_to_warehouse_cost),
        "defaultOtherUnitCost": str(row.default_other_unit_cost),
    }


@router.put("/settings", response_model=SellerFinanceSettingsResponse)
def update_seller_settings(
    store_id: int,
    payload: SellerFinanceSettingsRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    row = FinanceSettingsService(db, seller).update_seller_settings(payload.model_dump(exclude_none=True))
    return {
        "id": row.id,
        "sellerId": row.seller_id,
        "currency": row.currency,
        "defaultTaxMode": row.default_tax_mode,
        "defaultTaxRate": str(row.default_tax_rate),
        "taxBase": row.tax_base,
        "defaultPackagingCost": str(row.default_packaging_cost),
        "defaultLabelingCost": str(row.default_labeling_cost),
        "defaultShippingToWarehouseCost": str(row.default_shipping_to_warehouse_cost),
        "defaultOtherUnitCost": str(row.default_other_unit_cost),
    }


@router.get("/product-settings", response_model=ProductFinanceSettingsListResponse)
def list_product_settings(
    store_id: int,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    rows = FinanceSettingsService(db, seller).list_product_settings()
    start = (page - 1) * per_page
    end = start + per_page
    return {"items": [_product_setting_payload(row) for row in rows[start:end]], "page": page, "perPage": per_page, "total": len(rows)}


@router.get("/product-settings/catalog", response_model=ProductFinanceCatalogResponse)
def list_product_settings_catalog(
    store_id: int,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    search: str | None = Query(default=None),
    brands: list[str] | None = Query(default=None),
    subjects: list[str] | None = Query(default=None),
    only_missing: bool = Query(default=False, alias="onlyMissing"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    return FinanceSettingsService(db, seller).list_product_settings_catalog(
        page=page,
        per_page=per_page,
        search=search,
        brands=brands,
        subjects=subjects,
        only_missing=only_missing,
    )


@router.put("/product-settings/bulk", response_model=ProductFinanceSettingsListResponse)
def bulk_upsert_product_settings(
    store_id: int,
    payload: ProductFinanceBulkSettingsRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    rows = FinanceSettingsService(db, seller).bulk_upsert_product_cost_prices(
        [item.model_dump(exclude_none=True) for item in payload.items]
    )
    return {"items": [_product_setting_payload(row) for row in rows], "page": 1, "perPage": len(rows), "total": len(rows)}


@router.get("/product-settings/export-template")
def export_template(
    store_id: int,
    mode: str = Query(default="prepared"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    include_values = mode != "sample"
    content = FinanceSettingsService(db, seller).export_product_settings_template_xlsx(include_values=include_values)
    filename = "product-finance-prepared.xlsx" if include_values else "product-finance-sample.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/product-settings/import")
async def import_template(
    store_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    if not file.filename or not file.filename.lower().endswith((".csv", ".xlsx")):
        raise AppError("unsupported_import_file", "Only .xlsx and .csv imports are supported.", 422)
    content = await file.read()
    return FinanceSettingsService(db, seller).import_product_settings_file(file.filename, content)


@router.get("/product-settings/{product_id}", response_model=ProductFinanceSettingsListResponse)
def get_product_settings(
    store_id: int,
    product_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    rows = FinanceSettingsService(db, seller).get_product_settings(product_id)
    return {"items": [_product_setting_payload(row) for row in rows]}


@router.put("/product-settings/{product_id}", response_model=ProductFinanceSettingsResponse)
def upsert_product_settings(
    store_id: int,
    product_id: int,
    payload: ProductFinanceSettingsRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    row = FinanceSettingsService(db, seller).upsert_product_setting(product_id, payload.model_dump(exclude_none=True))
    return _product_setting_payload(row)


@router.get("/products/missing-settings", response_model=MissingFinanceProductsResponse)
def missing_product_settings(
    store_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    items = FinanceSettingsService(db, seller).list_missing_finance_settings()
    return {"items": [{"id": item.id, "nmId": item.nm_id, "vendorCode": item.vendor_code, "title": item.title} for item in items]}


@router.get("/external-costs", response_model=ExternalCostsListResponse)
def list_external_costs(
    store_id: int,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    rows = FinanceSettingsService(db, seller).list_external_costs()
    start = (page - 1) * per_page
    end = start + per_page
    return {"items": [_external_cost_payload(row) for row in rows[start:end]], "page": page, "perPage": per_page, "total": len(rows)}


@router.post("/external-costs", response_model=ExternalCostResponse)
def create_external_cost(
    store_id: int,
    payload: ExternalCostRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    row = FinanceSettingsService(db, seller).create_external_cost(payload.model_dump(exclude_none=True))
    return _external_cost_payload(row)


@router.put("/external-costs/{cost_id}", response_model=ExternalCostResponse)
def update_external_cost(
    store_id: int,
    cost_id: int,
    payload: ExternalCostRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    row = FinanceSettingsService(db, seller).update_external_cost(cost_id, payload.model_dump(exclude_none=True))
    return _external_cost_payload(row)


@router.delete("/external-costs/{cost_id}", status_code=204)
def delete_external_cost(
    store_id: int,
    cost_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    FinanceSettingsService(db, seller).delete_external_cost(cost_id)
    return Response(status_code=204)


@router.post("/reports/sync", response_model=FinanceSyncResponse)
async def sync_reports(
    store_id: int,
    payload: FinanceSyncRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, client = _seller_and_client(db, settings, user, store_id)
    return await FinanceSyncService(db, settings, seller, client).sync(
        date_from=payload.date_from,
        date_to=payload.date_to,
        period=payload.period,
        force=payload.force,
    )


@router.get("/reports/sync/status", response_model=FinanceSyncStatusResponse)
def finance_sync_status(
    store_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
    period: str = Query(default="daily"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    from app.models.finance import WbFinanceSyncState

    seller, _ = _seller_and_client(db, settings, user, store_id)
    query = db.query(WbFinanceSyncState).filter(WbFinanceSyncState.seller_id == seller.id)
    if date_from is not None:
        query = query.filter(WbFinanceSyncState.date_from == date_from)
    if date_to is not None:
        query = query.filter(WbFinanceSyncState.date_to == date_to)
    if period:
        query = query.filter(WbFinanceSyncState.period == period)
    state = query.order_by(WbFinanceSyncState.updated_at.desc(), WbFinanceSyncState.id.desc()).first()
    if not state:
        return {"status": "idle"}
    if FinanceSyncService.is_stale_state(state):
        state.status = "interrupted"
        state.last_error = "stale running finance sync recovered"
        state.finished_at = datetime.now(UTC)
        db.commit()
        db.refresh(state)
    return {
        "status": state.status,
        "lastRrdId": state.last_rrd_id,
        "totalRows": state.total_rows,
        "lastError": state.last_error,
    }


@router.get("/reports/raw", response_model=FinanceRawRowsResponse)
def raw_rows(
    store_id: int,
    date_from: date,
    date_to: date,
    limit: int = Query(default=100, le=1000),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    from app.models.finance import WbFinanceReportRow

    seller, _ = _seller_and_client(db, settings, user, store_id)
    rows = (
        db.query(WbFinanceReportRow)
        .filter(WbFinanceReportRow.seller_id == seller.id, WbFinanceReportRow.rr_date >= date_from, WbFinanceReportRow.rr_date <= date_to)
        .order_by(WbFinanceReportRow.id.desc())
        .limit(limit)
        .all()
    )
    return {"items": [{"id": row.id, "rrdId": row.rrd_id, "nmId": row.nm_id, "vendorCode": row.vendor_code, "rawData": row.raw_data} for row in rows]}


@router.get("/reports/summary", response_model=FinanceSummaryResponse)
def summary(
    store_id: int,
    date_from: date,
    date_to: date,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    return FinanceAggregationService(db, seller).summary(date_from, date_to)


@router.get("/reports/timeline", response_model=TimelineResponse)
def timeline(
    store_id: int,
    date_from: date,
    date_to: date,
    group_by: str = Query(default="day"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    return {"items": FinanceAggregationService(db, seller).timeline(date_from, date_to, group_by=group_by)}


@router.get("/reports/products", response_model=ProductBreakdownResponse)
def product_breakdown(
    store_id: int,
    date_from: date,
    date_to: date,
    sort: str = Query(default="profitAfterTax"),
    order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    items = FinanceAggregationService(db, seller).product_breakdown(date_from, date_to, sort=sort, order=order)
    start = (page - 1) * per_page
    end = start + per_page
    return {"items": items[start:end], "page": page, "perPage": per_page, "total": len(items)}


@router.get("/reports/cost-breakdown", response_model=CostBreakdownResponse)
def cost_breakdown(
    store_id: int,
    date_from: date,
    date_to: date,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    return FinanceAggregationService(db, seller).cost_breakdown(date_from, date_to)


@router.get("/reports/insights", response_model=InsightsResponse)
def insights(
    store_id: int,
    date_from: date,
    date_to: date,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    return {"items": FinanceAggregationService(db, seller).insights(date_from, date_to)}


@router.get("/reports/reconciliation", response_model=ReconciliationResponse)
async def reconciliation(
    store_id: int,
    date_from: date,
    date_to: date,
    period: str = Query(default="daily"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, client = _seller_and_client(db, settings, user, store_id)
    return await FinanceAiAnalysisService(db, settings, seller).reconciliation(date_from=date_from, date_to=date_to, client=client, period=period)


@router.get("/external-costs/preview-allocation", response_model=AllocationPreviewResponse)
def preview_allocation(
    store_id: int,
    date_from: date,
    date_to: date,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    return FinanceAggregationService(db, seller).allocation_preview(date_from, date_to)


@router.post("/ai/analyze", response_model=AiAnalyzeResponse)
def analyze_ai(
    store_id: int,
    payload: FinanceAiAnalyzeRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    return FinanceAiAnalysisService(db, settings, seller).analyze(
        date_from=payload.date_from,
        date_to=payload.date_to,
        group_by=payload.group_by,
    )


@router.get("/ai/snapshots", response_model=AiSnapshotsResponse)
def list_ai_snapshots(
    store_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    rows = FinanceAiAnalysisService(db, settings, seller).list_snapshots()
    return {"items": [{"id": row.id, "dateFrom": row.date_from.isoformat(), "dateTo": row.date_to.isoformat(), "aiAnalysis": row.ai_analysis} for row in rows]}


@router.get("/system-status", response_model=FinanceSystemStatusResponse)
async def system_status(
    store_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller_and_client(db, settings, user, store_id)
    return await FinanceSystemStatusService(db, settings, seller).build()


def _product_setting_payload(row) -> dict:
    return {
        "id": row.id,
        "sellerId": row.seller_id,
        "productId": row.product_id,
        "costPrice": str(row.cost_price),
        "costCurrency": row.cost_currency,
        "packagingCost": str(row.packaging_cost),
        "labelingCost": str(row.labeling_cost),
        "shippingToWarehouseCost": str(row.shipping_to_warehouse_cost),
        "otherUnitCost": str(row.other_unit_cost),
        "taxMode": row.tax_mode,
        "taxRate": str(row.tax_rate) if row.tax_rate is not None else None,
        "taxBase": row.tax_base,
        "effectiveFrom": row.effective_from.isoformat(),
        "effectiveTo": row.effective_to.isoformat() if row.effective_to else None,
        "note": row.note,
    }


def _external_cost_payload(row) -> dict:
    return {
        "id": row.id,
        "sellerId": row.seller_id,
        "costDate": row.cost_date.isoformat(),
        "periodFrom": row.period_from.isoformat() if row.period_from else None,
        "periodTo": row.period_to.isoformat() if row.period_to else None,
        "costType": row.cost_type,
        "amount": str(row.amount),
        "currency": row.currency,
        "allocationMethod": row.allocation_method,
        "productId": row.product_id,
        "note": row.note,
    }
