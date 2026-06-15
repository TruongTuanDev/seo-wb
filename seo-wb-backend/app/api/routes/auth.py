from typing import Annotated
from functools import lru_cache

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.rate_limit import FixedWindowRateLimiter, client_ip, rate_limit_dependency
from app.core.security import (
    clear_auth_cookies,
    create_access_token,
    hash_password,
    new_csrf_token,
    request_fingerprint,
    set_auth_cookies,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    TokenResponse,
    UsageSummaryResponse,
    UserResponse,
)
from app.services.usage_plans import apply_plan_defaults, get_usage_plan


router = APIRouter(prefix="/auth", tags=["auth"])
def _auth_rate_key(request: Request) -> str:
    return f"{client_ip(request)}:{request.url.path}"


@lru_cache
def _auth_limiter(max_requests: int, window_seconds: int) -> FixedWindowRateLimiter:
    return FixedWindowRateLimiter(max_requests=max_requests, window_seconds=window_seconds)


def _enforce_auth_rate_limit(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if settings.app_env.lower() == "test":
        return
    limiter = _auth_limiter(settings.auth_rate_limit_requests, settings.auth_rate_limit_window_seconds)
    rate_limit_dependency(limiter, _auth_rate_key)(request)


auth_rate_limit = Depends(_enforce_auth_rate_limit)


@router.post("/register", response_model=TokenResponse, dependencies=[auth_rate_limit])
def register(
    request: Request,
    response: Response,
    payload: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise AppError("email_already_registered", "Email is already registered.", 409)
    user = User(name=payload.name, email=payload.email.lower(), password_hash=hash_password(payload.password))
    apply_plan_defaults(user, "free")
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(settings, request, response, user)


@router.post("/login", response_model=TokenResponse, dependencies=[auth_rate_limit])
def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise AppError("invalid_credentials", "Invalid email or password.", 401)
    return _token_response(settings, request, response, user)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    _: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    clear_auth_cookies(settings, response)
    return response


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse(id=user.id, name=user.name, email=user.email, role=user.role, status=user.status, plan_type=user.plan_type)


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: ProfileUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    next_name = payload.display_name if payload.display_name is not None else payload.name
    if next_name is None:
        raise AppError("missing_profile_fields", "Provide name or display_name to update the profile.", 400)
    normalized_name = next_name.strip()
    if len(normalized_name) < 2:
        raise AppError("invalid_name", "Name must be at least 2 characters.", 400)
    user.name = normalized_name
    db.commit()
    db.refresh(user)
    return UserResponse(id=user.id, name=user.name, email=user.email, role=user.role, status=user.status, plan_type=user.plan_type)


@router.post("/change-password", status_code=204)
def change_password(
    payload: ChangePasswordRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    if not verify_password(payload.current_password, user.password_hash):
        raise AppError("invalid_current_password", "Current password is incorrect.", 401)
    if verify_password(payload.new_password, user.password_hash):
        raise AppError("password_unchanged", "New password must be different from the current password.", 400)
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return Response(status_code=204)


@router.get("/usage", response_model=UsageSummaryResponse)
def usage_summary(user: Annotated[User, Depends(get_current_user)]) -> UsageSummaryResponse:
    plan = get_usage_plan(user.plan_type)
    monthly_quota = max(0, int(user.monthly_quota or 0))
    used_quota = max(0, int(user.used_quota or 0))
    remaining_quota = max(0, monthly_quota - used_quota)
    quota_percent = round((used_quota / monthly_quota) * 100, 2) if monthly_quota > 0 else 0.0

    monthly_card_quota = max(0, int(user.monthly_card_quota or 0))
    used_card_quota = max(0, int(user.used_card_quota or 0))
    remaining_card_quota = max(0, monthly_card_quota - used_card_quota)
    card_quota_percent = round((used_card_quota / monthly_card_quota) * 100, 2) if monthly_card_quota > 0 else 0.0

    used_cost = round(float(user.used_cost or 0.0), 4)
    monthly_cost_limit = float(user.monthly_cost_limit) if user.monthly_cost_limit is not None else None
    remaining_cost = round(max(0.0, monthly_cost_limit - used_cost), 4) if monthly_cost_limit is not None else None
    cost_percent = round((used_cost / monthly_cost_limit) * 100, 2) if monthly_cost_limit and monthly_cost_limit > 0 else None

    return UsageSummaryResponse(
        plan_type=plan.plan_type,
        monthly_quota=monthly_quota,
        used_quota=used_quota,
        remaining_quota=remaining_quota,
        quota_percent=quota_percent,
        monthly_card_quota=monthly_card_quota,
        used_card_quota=used_card_quota,
        remaining_card_quota=remaining_card_quota,
        card_quota_percent=card_quota_percent,
        monthly_cost_limit=monthly_cost_limit,
        used_cost=used_cost,
        remaining_cost=remaining_cost,
        cost_percent=cost_percent,
        max_images_per_job=plan.max_images_per_job,
        allow_legacy_vton=plan.allow_legacy_vton,
        allow_gpt_image=plan.allow_gpt_image,
        priority_queue=plan.priority_queue,
        credit_balance=max(0, int(user.credit_balance or 0)),
        credits_used=max(0, int(user.credits_used or 0)),
        credits_granted=max(0, int(user.credits_granted or 0)),
        quota_reset_at=user.quota_reset_at,
        last_quota_reset_at=user.last_quota_reset_at,
    )


def _token_response(settings: Settings, request: Request, response: Response, user: User) -> TokenResponse:
    return _scoped_token_response(settings, request, response, user, scope="user")


def _scoped_token_response(
    settings: Settings,
    request: Request,
    response: Response,
    user: User,
    *,
    scope: str,
) -> TokenResponse:
    csrf_token = new_csrf_token()
    token = create_access_token(
        settings,
        str(user.id),
        {
            "csrf": csrf_token,
            "fp": request_fingerprint(settings, request),
        },
    )
    if scope == "admin":
        set_auth_cookies(
            settings,
            response,
            token,
            csrf_token,
            auth_cookie_name=settings.admin_auth_cookie_name,
            csrf_cookie_name=settings.admin_csrf_cookie_name,
        )
    else:
        set_auth_cookies(settings, response, token, csrf_token)
    return TokenResponse(
        access_token=None,
        user=UserResponse(id=user.id, name=user.name, email=user.email, role=user.role, status=user.status, plan_type=user.plan_type),
    )
