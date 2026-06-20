from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_store
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import decrypt_secret
from app.db.session import get_db
from app.models.seller import Seller
from app.models.user import User
from app.models.wb_product import WbProduct, WbProductSyncState
from app.schemas.card import CardListRequest, PayloadTnvedEnrichRequest, TnvedSuggestionRequest
from app.schemas.finance import ProductSyncResponse, ProductSyncStatusResponse, WbProductResponse, WbProductsListResponse
from app.services.seller_service import ensure_seller_for_store, update_seller_from_wb
from app.services.card_flow import CardFlowService
from app.services.wb_common_client import WbCommonClient
from app.services.wb_content_client import WbContentClient
from app.services.wb_finance_client import WbFinanceClient
from app.services.wb_marketplace_client import WbMarketplaceClient
from app.services.wb_product_sync_service import WbProductSyncService
from datetime import UTC, datetime


router = APIRouter(prefix="/wb", tags=["wildberries"])


def _seller(db: Session, settings: Settings, user: User, store_id: int) -> tuple[Seller, str]:
    store = get_owned_store(db, user, store_id)
    api_key = decrypt_secret(settings, store.wb_api_key_encrypted)
    seller = ensure_seller_for_store(db, store)
    return seller, api_key


def _content_client(db: Session, settings: Settings, user: User, store_id: int) -> WbContentClient:
    seller, api_key = _seller(db, settings, user, store_id)
    return WbContentClient(settings, api_key, db=db, seller_id=seller.id)


def _common_client(db: Session, settings: Settings, user: User, store_id: int) -> WbCommonClient:
    seller, api_key = _seller(db, settings, user, store_id)
    return WbCommonClient(settings, api_key, db=db, seller_id=seller.id)


def _finance_client(db: Session, settings: Settings, user: User, store_id: int) -> WbFinanceClient:
    seller, api_key = _seller(db, settings, user, store_id)
    return WbFinanceClient(settings, api_key, db=db, seller_id=seller.id)


def _marketplace_client(db: Session, settings: Settings, user: User, store_id: int) -> WbMarketplaceClient:
    seller, api_key = _seller(db, settings, user, store_id)
    return WbMarketplaceClient(settings, api_key, db=db, seller_id=seller.id)


def _flow(db: Session, settings: Settings, user: User, store_id: int) -> CardFlowService:
    store = get_owned_store(db, user, store_id)
    return CardFlowService(settings, db, user, store)


@router.get("/warehouses")
async def warehouses(
    store_id: int,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
):
    return {"data": await _marketplace_client(db, settings, user, store_id).get_warehouses()}


@router.get("/parent-categories")
async def parent_categories(
    store_id: int,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
):
    return {"data": await _content_client(db, settings, user, store_id).get_parent_categories(locale="ru")}


@router.get("/subjects")
async def subjects(
    store_id: int,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
    parent_id: int | None = Query(default=1),
    q: str | None = Query(default=None),
):
    items = await _content_client(db, settings, user, store_id).get_subjects(parent_id=parent_id, locale="ru")
    if q:
        query = q.casefold()
        items = [item for item in items if query in str(item.get("subjectName", "")).casefold()]
    return {"data": items}


@router.get("/subjects/{subject_id}/charcs")
async def subject_charcs(
    store_id: int,
    subject_id: int,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
):
    items = await _content_client(db, settings, user, store_id).get_subject_charcs(subject_id, locale="ru")
    return {"data": items}


@router.get("/directories/{directory_name}")
async def directory(
    store_id: int,
    directory_name: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
):
    client = _content_client(db, settings, user, store_id)
    handlers = {
        "colors": client.get_colors,
        "kinds": client.get_kinds,
        "countries": client.get_countries,
        "seasons": client.get_seasons,
        "vat": client.get_vat_rates,
    }
    if directory_name not in handlers:
        return {"data": [], "error": f"Unknown directory: {directory_name}"}
    return {"data": await handlers[directory_name](locale="ru")}


@router.get("/subjects/{subject_id}/tnved")
async def subject_tnved(
    store_id: int,
    subject_id: int,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
    search: str | None = Query(default=None),
):
    items = await _content_client(db, settings, user, store_id).get_tnved(subject_id, search=search, locale="ru")
    return {"data": items, "selected": items[0] if items else None}


@router.post("/tnved/suggest")
async def suggest_tnved(
    store_id: int,
    payload: TnvedSuggestionRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
):
    return await _flow(db, settings, user, store_id).suggest_tnved(
        payload.subjectID,
        payload.search,
        subject_name=payload.subjectName,
        category=payload.category,
        gender=payload.gender,
        material=payload.material,
    )


@router.post("/payload/enrich-tnved")
async def enrich_payload_tnved(
    store_id: int,
    payload: PayloadTnvedEnrichRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
):
    return await _flow(db, settings, user, store_id).enrich_payload_with_tnved(
        payload.subjectID,
        payload.payload,
        payload.search,
        subject_name=payload.subjectName,
        category=payload.category,
        gender=payload.gender,
        material=payload.material,
    )


@router.get("/subjects/{subject_id}/brands")
async def subject_brands(
    store_id: int,
    subject_id: int,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
    next_value: int | None = Query(default=None, alias="next"),
):
    return await _content_client(db, settings, user, store_id).get_brands(subject_id, next_value)


@router.get("/card-limits")
async def card_limits(
    store_id: int,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
):
    return await _content_client(db, settings, user, store_id).get_card_limits()


@router.post("/cards/list")
async def cards_list(
    store_id: int,
    payload: CardListRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
):
    text_search = payload.textSearch or payload.vendorCode or (str(payload.nmID) if payload.nmID else "")
    wb_payload: dict[str, Any] = {
        "settings": {
            "cursor": {"limit": payload.limit},
            "filter": {"withPhoto": payload.withPhoto},
        }
    }
    if text_search:
        wb_payload["settings"]["filter"]["textSearch"] = text_search
    return await _content_client(db, settings, user, store_id).get_cards_list(wb_payload)


@router.post("/raw")
async def wb_raw_proxy(
    store_id: int,
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    """Narrow internal proxy for frontend debugging of WB payloads during development."""
    if not settings.enable_wb_raw_proxy:
        raise AppError("raw_proxy_disabled", "Raw Wildberries proxy is disabled.", 403)
    client = _content_client(db, settings, user, store_id)
    method = str(payload.get("method") or "POST").upper()
    path = str(payload.get("path") or "")
    if not path.startswith("/content/"):
        return {"error": "Only /content/* paths are allowed."}
    return await client.request(method, path, json_body=payload.get("json"), params=payload.get("params"))


@router.get("/card-errors")
async def card_errors(
    store_id: int,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
):
    return await _content_client(db, settings, user, store_id).get_card_errors()


@router.get("/health/ping")
async def ping(
    store_id: int,
    category: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    category_key = category.casefold()
    if category_key == "content":
        data = await _content_client(db, settings, user, store_id).ping()
    elif category_key == "finance":
        data = await _finance_client(db, settings, user, store_id).ping()
    elif category_key == "common":
        data = await _common_client(db, settings, user, store_id).ping()
    else:
        raise AppError("unknown_wb_category", "Unknown WB category.", 422)
    return {"category": category_key, "ok": True, "data": data}


@router.get("/seller-info")
async def seller_info(
    store_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller(db, settings, user, store_id)
    payload = await _common_client(db, settings, user, store_id).get_seller_info()
    seller = update_seller_from_wb(db, seller, payload)
    return {
        "seller": {
            "id": seller.id,
            "storeId": seller.store_id,
            "externalSid": seller.external_sid,
            "name": seller.name,
            "tradeMark": seller.trade_mark,
            "tin": seller.tin,
        },
        "raw": payload,
    }


@router.post("/products/sync", response_model=ProductSyncResponse)
async def sync_products(
    store_id: int,
    full: bool = Query(default=False),
    max_batches: int | None = Query(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller(db, settings, user, store_id)
    service = WbProductSyncService(db, seller, _content_client(db, settings, user, store_id))
    return await service.sync(full=full, max_batches=max_batches if not settings.wb_live_full_product_sync else None)


@router.get("/products/sync/status", response_model=ProductSyncStatusResponse)
def product_sync_status(
    store_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller(db, settings, user, store_id)
    state = db.query(WbProductSyncState).filter_by(seller_id=seller.id, sync_type="active_cards").one_or_none()
    if not state:
        return {"status": "idle"}
    if WbProductSyncService.is_stale_state(state):
        state.status = "interrupted"
        state.last_error = "stale running product sync recovered"
        state.finished_at = datetime.now(UTC)
        db.commit()
        db.refresh(state)
    return {
        "status": state.status,
        "cursorUpdatedAt": state.cursor_updated_at.isoformat() if state.cursor_updated_at else None,
        "cursorNmId": state.cursor_nm_id,
        "totalSynced": state.total_synced,
        "lastError": state.last_error,
        "startedAt": state.started_at.isoformat() if state.started_at else None,
        "finishedAt": state.finished_at.isoformat() if state.finished_at else None,
    }


@router.get("/products", response_model=WbProductsListResponse)
def list_products(
    store_id: int,
    nm_id: int | None = Query(default=None, alias="nmId"),
    vendor_code: str | None = Query(default=None, alias="vendorCode"),
    sku: str | None = Query(default=None),
    title: str | None = Query(default=None),
    brand: str | None = Query(default=None),
    subject_name: str | None = Query(default=None, alias="subjectName"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller(db, settings, user, store_id)
    query = db.query(WbProduct).filter(WbProduct.seller_id == seller.id)
    if nm_id is not None:
        query = query.filter(WbProduct.nm_id == nm_id)
    if vendor_code:
        query = query.filter(WbProduct.vendor_code == vendor_code)
    if sku:
        query = query.filter(WbProduct.skus.contains([sku]))
    if title:
        query = query.filter(WbProduct.title.ilike(f"%{title}%"))
    if brand:
        query = query.filter(WbProduct.brand == brand)
    if subject_name:
        query = query.filter(WbProduct.subject_name == subject_name)
    products = query.order_by(WbProduct.id.desc()).all()
    start = (page - 1) * per_page
    end = start + per_page
    return {"items": [_product_payload(product) for product in products[start:end]], "page": page, "perPage": per_page, "total": len(products)}


@router.get("/products/{product_id}", response_model=WbProductResponse)
def get_product(
    product_id: int,
    store_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    seller, _ = _seller(db, settings, user, store_id)
    product = db.query(WbProduct).filter(WbProduct.id == product_id, WbProduct.seller_id == seller.id).one_or_none()
    if not product:
        raise AppError("product_not_found", "Product not found.", 404)
    return _product_payload(product)


def _product_payload(product: WbProduct) -> dict[str, Any]:
    return {
        "id": product.id,
        "nmId": product.nm_id,
        "imtId": product.imt_id,
        "vendorCode": product.vendor_code,
        "brand": product.brand,
        "title": product.title,
        "description": product.description,
        "subjectId": product.subject_id,
        "subjectName": product.subject_name,
        "photoBigUrl": product.photo_big_url,
        "photoSquareUrl": product.photo_square_url,
        "sizes": product.sizes,
        "skus": product.skus,
        "characteristics": product.characteristics,
        "rawData": product.raw_data,
        "wbUpdatedAt": product.wb_updated_at.isoformat() if product.wb_updated_at else None,
    }
