import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_current_user, get_owned_store
from app.core.config import Settings, get_settings
from app.core.security import encrypt_secret
from app.db.session import get_db
from app.models.store import Store
from app.models.user import User
from app.schemas.store import StoreCreateRequest, StoreResponse, StoreUpdateRequest
from app.services.store_bootstrap_service import StoreBootstrapSyncService


router = APIRouter(prefix="/stores", tags=["stores"])
logger = logging.getLogger(__name__)


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
