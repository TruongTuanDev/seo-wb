import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_current_user, get_owned_store
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import encrypt_secret
from app.db.session import get_db
from app.models.shop_category import StoreCategory, StoreCategorySyncState
from app.models.store import Store
from app.models.user import User
from app.schemas.shop_category import (
    StoreCategoryCreateRequest,
    StoreCategoryResponse,
    StoreCategorySyncStatusResponse,
    StoreCategoryUpdateRequest,
)
from app.schemas.store import StoreCreateRequest, StoreResponse, StoreUpdateRequest
from app.services.shop_category_sync_service import ShopCategorySyncService
from app.services.store_bootstrap_service import StoreBootstrapSyncService


router = APIRouter(prefix="/stores", tags=["stores"])
logger = logging.getLogger(__name__)

CATEGORY_SYNC_STALE_MINUTES = 10


def _category_sync_is_stale(state: StoreCategorySyncState) -> bool:
    if state.status != "running" or not state.updated_at:
        return False
    elapsed = (datetime.now(timezone.utc) - state.updated_at.astimezone(timezone.utc)).total_seconds()
    return elapsed > CATEGORY_SYNC_STALE_MINUTES * 60


async def _run_category_sync(
    session_factory: sessionmaker[Session], settings: Settings, store_id: int
) -> None:
    with session_factory() as db:
        store = db.get(Store, store_id)
        state = db.scalar(
            select(StoreCategorySyncState).where(StoreCategorySyncState.store_id == store_id)
        )
        if store is None or state is None:
            return
        try:
            await ShopCategorySyncService(settings, db, store).sync(state)
            state.status = "completed"
            state.last_error = None
        except Exception as exc:  # noqa: BLE001 - record failure for the UI
            state.status = "failed"
            state.last_error = str(exc)[:1000]
            logger.exception("Category sync failed. store_id=%s", store_id)
        finally:
            state.finished_at = datetime.now(timezone.utc)
            db.commit()


def _delete_store_in_background(session_factory: sessionmaker[Session], user_id: int, store_id: int) -> None:
    with session_factory() as db:
        store = db.scalar(select(Store).where(Store.id == store_id, Store.user_id == user_id))
        if store is None:
            return
        db.delete(store)
        db.commit()


@router.post("", response_model=StoreResponse)
def create_store(
    payload: StoreCreateRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
) -> StoreResponse:
    store = Store(
        user_id=user.id,
        name=payload.name,
        wb_api_key_encrypted=encrypt_secret(settings, payload.wb_api_key),
    )
    db.add(store)
    db.commit()
    db.refresh(store)
    bind = db.get_bind()
    session_factory = sessionmaker(bind=bind, autoflush=False, autocommit=False)
    bootstrap_service = StoreBootstrapSyncService(settings, session_factory)
    background_tasks.add_task(bootstrap_service.enqueue_store_bootstrap, store.id)
    return StoreResponse(id=store.id, name=store.name, created_at=store.created_at, updated_at=store.updated_at)


@router.get("", response_model=list[StoreResponse])
def list_stores(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[StoreResponse]:
    stores = db.scalars(select(Store).where(Store.user_id == user.id).order_by(Store.id.desc())).all()
    return [StoreResponse(id=s.id, name=s.name, created_at=s.created_at, updated_at=s.updated_at) for s in stores]


@router.patch("/{store_id}", response_model=StoreResponse)
def update_store(
    store_id: int,
    payload: StoreUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
) -> StoreResponse:
    store = get_owned_store(db, user, store_id)
    if payload.name is not None:
        store.name = payload.name
    if payload.wb_api_key is not None:
        store.wb_api_key_encrypted = encrypt_secret(settings, payload.wb_api_key)
    db.commit()
    db.refresh(store)
    return StoreResponse(id=store.id, name=store.name, created_at=store.created_at, updated_at=store.updated_at)


@router.post(
    "/{store_id}/categories/sync",
    response_model=StoreCategorySyncStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def sync_store_categories(
    store_id: int,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
) -> StoreCategorySyncStatusResponse:
    store = get_owned_store(db, user, store_id)
    state = db.scalar(
        select(StoreCategorySyncState).where(StoreCategorySyncState.store_id == store.id)
    )
    if state is None:
        state = StoreCategorySyncState(store_id=store.id)
        db.add(state)
    elif state.status == "running" and not _category_sync_is_stale(state):
        raise AppError("category_sync_running", "A category sync is already in progress.", 409)

    state.status = "running"
    state.started_at = datetime.now(timezone.utc)
    state.finished_at = None
    state.last_error = None
    state.total_scanned = 0
    state.categories_found = 0
    db.commit()

    bind = db.get_bind()
    session_factory = sessionmaker(bind=bind, autoflush=False, autocommit=False)
    background_tasks.add_task(_run_category_sync, session_factory, settings, store.id)
    return StoreCategorySyncStatusResponse.model_validate(state)


@router.get("/{store_id}/categories/sync/status", response_model=StoreCategorySyncStatusResponse)
def store_category_sync_status(
    store_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> StoreCategorySyncStatusResponse:
    store = get_owned_store(db, user, store_id)
    state = db.scalar(
        select(StoreCategorySyncState).where(StoreCategorySyncState.store_id == store.id)
    )
    if state is None:
        return StoreCategorySyncStatusResponse()
    if state.status == "running" and _category_sync_is_stale(state):
        state.status = "interrupted"
        state.last_error = "stale running sync recovered"
        state.finished_at = datetime.now(timezone.utc)
        db.commit()
    return StoreCategorySyncStatusResponse.model_validate(state)


@router.get("/{store_id}/categories", response_model=list[StoreCategoryResponse])
def list_store_categories(
    store_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[StoreCategoryResponse]:
    store = get_owned_store(db, user, store_id)
    rows = (
        db.scalars(
            select(StoreCategory)
            .where(StoreCategory.store_id == store.id)
            .order_by(StoreCategory.product_count.desc(), StoreCategory.subject_name.asc())
        ).all()
    )
    return [StoreCategoryResponse.model_validate(row) for row in rows]


@router.post("/{store_id}/categories", response_model=StoreCategoryResponse)
def add_store_category(
    store_id: int,
    payload: StoreCategoryCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> StoreCategoryResponse:
    store = get_owned_store(db, user, store_id)
    existing = db.scalar(
        select(StoreCategory).where(
            StoreCategory.store_id == store.id,
            StoreCategory.subject_id == payload.subject_id,
        )
    )
    if existing is not None:
        raise AppError("category_exists", "This category is already in the shop catalog.", 409)
    row = StoreCategory(
        store_id=store.id,
        subject_id=payload.subject_id,
        subject_name=payload.subject_name,
        tnved=payload.tnved,
        source="manual",
        locked=bool(payload.tnved),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return StoreCategoryResponse.model_validate(row)


@router.patch("/{store_id}/categories/{category_id}", response_model=StoreCategoryResponse)
def update_store_category(
    store_id: int,
    category_id: int,
    payload: StoreCategoryUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> StoreCategoryResponse:
    store = get_owned_store(db, user, store_id)
    row = db.scalar(
        select(StoreCategory).where(
            StoreCategory.id == category_id,
            StoreCategory.store_id == store.id,
        )
    )
    if row is None:
        raise AppError("category_not_found", "Category was not found in this shop catalog.", 404)
    if payload.subject_name is not None:
        row.subject_name = payload.subject_name
    if payload.tnved is not None:
        row.tnved = payload.tnved or None
        # A manually chosen TN VED is locked so re-sync won't overwrite it.
        row.locked = True
    if payload.locked is not None:
        row.locked = payload.locked
    db.commit()
    db.refresh(row)
    return StoreCategoryResponse.model_validate(row)


@router.delete("/{store_id}/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_store_category(
    store_id: int,
    category_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    store = get_owned_store(db, user, store_id)
    row = db.scalar(
        select(StoreCategory).where(
            StoreCategory.id == category_id,
            StoreCategory.store_id == store.id,
        )
    )
    if row is not None:
        db.delete(row)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{store_id}", status_code=status.HTTP_202_ACCEPTED)
def delete_store(
    store_id: int,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    store = get_owned_store(db, user, store_id)
    bind = db.get_bind()
    session_factory = sessionmaker(bind=bind, autoflush=False, autocommit=False)
    background_tasks.add_task(_delete_store_in_background, session_factory, user.id, store.id)
    logger.info("Queued store deletion. store_id=%s user_id=%s", store.id, user.id)
    return Response(status_code=status.HTTP_202_ACCEPTED)
