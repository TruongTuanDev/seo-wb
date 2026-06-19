from datetime import datetime, timezone

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import assert_csrf, assert_token_fingerprint, decode_access_token
from app.db.session import get_db
from app.models.store import Store
from app.models.user import User
from app.services.billing_foundation import reset_user_usage_and_credits
from app.services.usage_plans import reset_usage_if_due


bearer_scheme = HTTPBearer(auto_error=False)


def _get_current_user_by_cookie(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    *,
    auth_cookie_name: str,
    csrf_cookie_name: str,
) -> User:
    token_source = "bearer" if credentials else "cookie"
    token = credentials.credentials if credentials else request.cookies.get(auth_cookie_name)
    if not token:
        raise AppError("missing_token", "Authentication token is required.", 401)
    payload = decode_access_token(settings, token)
    assert_token_fingerprint(settings, request, payload)
    assert_csrf(settings, request, payload, token_source, csrf_cookie_name=csrf_cookie_name)
    user_id = payload.get("sub")
    if not user_id:
        raise AppError("invalid_token_subject", "Invalid token subject.", 401)
    try:
        user = db.get(User, int(user_id))
    except (TypeError, ValueError) as exc:
        raise AppError("invalid_token_subject", "Invalid token subject.", 401) from exc
    if not user or user.deleted_at is not None:
        raise AppError("user_not_found", "User not found.", 401)
    if user.status != "active":
        raise AppError("user_suspended", "User account is suspended.", 403)
    quota_reset_at = user.quota_reset_at
    reset_due = False
    if quota_reset_at is not None:
        quota_reset_at_utc = quota_reset_at.astimezone(timezone.utc) if quota_reset_at.tzinfo else quota_reset_at.replace(tzinfo=timezone.utc)
        reset_due = quota_reset_at_utc <= datetime.now(timezone.utc)
    elif user.last_quota_reset_at is None:
        reset_due = True
    if reset_due:
        reset_user_usage_and_credits(db, user, actor_type="system", actor_id="lazy-reset")
        db.commit()
        db.refresh(user)
        return user
    if reset_usage_if_due(user, db=db):
        db.commit()
        db.refresh(user)
    return user


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    return _get_current_user_by_cookie(
        request,
        credentials,
        db,
        settings,
        auth_cookie_name=settings.auth_cookie_name,
        csrf_cookie_name=settings.csrf_cookie_name,
    )


def get_current_admin(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    try:
        user = _get_current_user_by_cookie(
            request,
            credentials,
            db,
            settings,
            auth_cookie_name=settings.admin_auth_cookie_name,
            csrf_cookie_name=settings.admin_csrf_cookie_name,
        )
    except AppError as exc:
        if exc.code != "missing_token":
            raise
        user = _get_current_user_by_cookie(
            request,
            credentials,
            db,
            settings,
            auth_cookie_name=settings.auth_cookie_name,
            csrf_cookie_name=settings.csrf_cookie_name,
        )
    if user.role not in {"admin", "super_admin"}:
        raise AppError("admin_forbidden", "Admin access is required.", 403)
    return user


def get_owned_store(db: Session, user: User, store_id: int) -> Store:
    store = db.get(Store, store_id)
    if not store or store.user_id != user.id:
        raise AppError("store_not_found", "Store not found.", 404)
    return store
