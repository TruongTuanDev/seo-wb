from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import clear_auth_cookies, hash_password
from app.db.session import get_db
from app.models.admin import AdminAiSettings, AdminAuditLog, GeneratedImageJob, ModelTemplate, UsageRecord
from app.models.user import User
from app.schemas.admin import (
    AdminAiSettingsResponse,
    AdminAiSettingsUpdateRequest,
    AdminDashboardResponse,
    AdminDashboardUserMetric,
    AdminLoginRequest,
    AdminUsageSummaryResponse,
    AdminUserCreateRequest,
    AdminUserResponse,
    AdminUserUpdateRequest,
    GeneratedImageJobDetailResponse,
    GeneratedImageJobResponse,
    ModelTemplateResponse,
    ModelTemplateUpsertRequest,
    UsageRecordResponse,
)
from app.schemas.auth import TokenResponse, UserResponse
from app.schemas.card import ImageGenerationImageActionRequest
from app.services.billing_foundation import log_platform_audit
from app.services.product_image_generator import IMAGE_JOB_QUEUE_KEY, ProductImageGenerator
from app.services.redis_client import require_redis
from app.services.admin_runtime import (
    get_or_create_admin_ai_settings,
    list_public_model_templates,
    soft_delete_job,
    soft_delete_model,
    soft_delete_user,
)
from app.services.usage_plans import (
    apply_plan_defaults,
    cost_ratio,
    get_usage_plan,
    normalize_plan_type,
    quota_ratio,
    reset_usage_cycle,
    reset_usage_if_due,
)
from app.api.routes.auth import auth_rate_limit, _scoped_token_response


router = APIRouter(prefix="/admin", tags=["admin"])
MODEL_STORAGE_DIR = Path("storage/admin_models")
ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
SUPPORTED_POSES = {"front", "side_45", "walking", "back", "hand_on_hip", "sitting"}


@router.post("/login", response_model=TokenResponse, dependencies=[auth_rate_limit])
def admin_login(
    request: Request,
    response: Response,
    payload: AdminLoginRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or user.deleted_at is not None or user.status != "active" or user.role not in {"admin", "super_admin"}:
        raise AppError("invalid_admin_credentials", "Invalid admin credentials.", 401)
    from app.core.security import verify_password

    if not verify_password(payload.password, user.password_hash):
        raise AppError("invalid_admin_credentials", "Invalid admin credentials.", 401)
    return _scoped_token_response(settings, request, response, user, scope="admin")


@router.post("/logout", status_code=204)
def admin_logout(
    response: Response,
    _: User = Depends(get_current_admin),
    settings: Settings = Depends(get_settings),
) -> Response:
    clear_auth_cookies(
        settings,
        response,
        auth_cookie_name=settings.admin_auth_cookie_name,
        csrf_cookie_name=settings.admin_csrf_cookie_name,
    )
    return response


@router.get("/me", response_model=UserResponse)
def admin_me(user: User = Depends(get_current_admin)) -> UserResponse:
    return UserResponse(id=user.id, name=user.name, email=user.email, role=user.role, status=user.status, plan_type=user.plan_type)


@router.get("", response_model=AdminDashboardResponse)
def dashboard(
    plan: str | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> AdminDashboardResponse:
    start_today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    query = select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc())
    if plan:
        query = query.where(User.plan_type == normalize_plan_type(plan))
    if status:
        query = query.where(User.status == _normalize_status(status))
    if date_from is not None:
        query = query.where(User.created_at >= date_from)
    if date_to is not None:
        query = query.where(User.created_at <= date_to)
    users = db.scalars(query).all()
    if _refresh_users_if_needed(db, users):
        users = db.scalars(query).all()

    total_users = len(users)
    total_models = db.scalar(select(func.count()).select_from(ModelTemplate).where(ModelTemplate.deleted_at.is_(None))) or 0
    total_generated_images = db.scalar(
        select(func.coalesce(func.sum(GeneratedImageJob.quantity), 0)).where(GeneratedImageJob.deleted_at.is_(None))
    ) or 0
    total_failed_jobs = db.scalar(
        select(func.count()).select_from(GeneratedImageJob).where(GeneratedImageJob.status == "failed", GeneratedImageJob.deleted_at.is_(None))
    ) or 0
    total_api_cost_estimate = float(db.scalar(select(func.coalesce(func.sum(UsageRecord.estimated_cost), 0.0))) or 0.0)
    images_generated_today = int(
        db.scalar(
            select(func.coalesce(func.sum(GeneratedImageJob.quantity), 0)).where(
                GeneratedImageJob.created_at >= start_today,
                GeneratedImageJob.status == "completed",
                GeneratedImageJob.deleted_at.is_(None),
            )
        )
        or 0
    )
    validation_failed_count = sum(
        1
        for item in db.scalars(
            select(GeneratedImageJob.validation_result).where(GeneratedImageJob.deleted_at.is_(None))
        ).all()
        if (item or {}).get("failed_validations")
    )
    active_users = sum(1 for user in users if user.status == "active")
    users_over_quota_80 = sum(1 for user in users if quota_ratio(user) >= 0.8)
    users_over_cost_80 = sum(1 for user in users if cost_ratio(user) >= 0.8)
    users_over_quota = sum(1 for user in users if quota_ratio(user) >= 1.0)
    users_over_cost = sum(1 for user in users if cost_ratio(user) >= 1.0)
    top_usage_users = sorted(users, key=lambda user: (quota_ratio(user), user.used_quota), reverse=True)[:5]
    top_cost_users = sorted(users, key=lambda user: (cost_ratio(user), user.used_cost), reverse=True)[:5]
    return AdminDashboardResponse(
        total_users=total_users,
        total_models=total_models,
        total_generated_images=total_generated_images,
        total_failed_jobs=total_failed_jobs,
        total_api_cost_estimate=round(total_api_cost_estimate, 4),
        images_generated_today=images_generated_today,
        validation_failed_count=validation_failed_count,
        active_users=active_users,
        users_over_quota_80=users_over_quota_80,
        users_over_cost_80=users_over_cost_80,
        users_over_quota=users_over_quota,
        users_over_cost=users_over_cost,
        top_usage_users=[_dashboard_user_metric(user) for user in top_usage_users],
        top_cost_users=[_dashboard_user_metric(user) for user in top_cost_users],
    )


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(
    search: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> list[AdminUserResponse]:
    query = select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc())
    if search:
        like = f"%{search.strip()}%"
        query = query.where((User.email.ilike(like)) | (User.name.ilike(like)))
    users = db.scalars(query).all()
    _refresh_users_if_needed(db, users)
    return [_user_response(item) for item in users]


@router.post("/users", response_model=AdminUserResponse)
def create_user(
    payload: AdminUserCreateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> AdminUserResponse:
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing and existing.deleted_at is None:
        raise AppError("email_already_registered", "Email is already registered.", 409)
    if existing and existing.deleted_at is not None:
        user = existing
        user.deleted_at = None
        user.name = payload.name
        user.email = payload.email.lower()
        user.password_hash = hash_password(payload.password)
        user.role = _normalize_role(payload.role)
        user.status = _normalize_status(payload.status)
        apply_plan_defaults(user, normalize_plan_type(payload.plan_type))
        user.monthly_quota = max(0, payload.monthly_quota or user.monthly_quota)
        if payload.monthly_cost_limit is not None:
            user.monthly_cost_limit = max(0.0, payload.monthly_cost_limit)
        user.used_quota = 0
        user.used_cost = 0.0
    else:
        user = User(
            name=payload.name,
            email=payload.email.lower(),
            password_hash=hash_password(payload.password),
            role=_normalize_role(payload.role),
            status=_normalize_status(payload.status),
        )
        apply_plan_defaults(user, normalize_plan_type(payload.plan_type))
        user.monthly_quota = max(0, payload.monthly_quota or user.monthly_quota)
        if payload.monthly_cost_limit is not None:
            user.monthly_cost_limit = max(0.0, payload.monthly_cost_limit)
        db.add(user)
    db.commit()
    db.refresh(user)
    _log_admin_action(db, admin.id, "CREATE_USER", "user", str(user.id), {"email": user.email})
    return _user_response(user)


@router.get("/users/{user_id}", response_model=AdminUserResponse)
def get_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_admin)) -> AdminUserResponse:
    user = db.get(User, user_id)
    if not user or user.deleted_at is not None:
        raise AppError("user_not_found", "User not found.", 404)
    if reset_usage_if_due(user):
        db.commit()
        db.refresh(user)
    return _user_response(user)


@router.put("/users/{user_id}", response_model=AdminUserResponse)
def update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> AdminUserResponse:
    user = db.get(User, user_id)
    if not user or user.deleted_at is not None:
        raise AppError("user_not_found", "User not found.", 404)
    if payload.email and payload.email.lower() != user.email:
        existing = db.scalar(select(User).where(User.email == payload.email.lower(), User.id != user_id))
        if existing:
            raise AppError("email_already_registered", "Email is already registered.", 409)
        user.email = payload.email.lower()
    if payload.name is not None:
        user.name = payload.name
    if payload.password:
        user.password_hash = hash_password(payload.password)
    if payload.role is not None:
        user.role = _normalize_role(payload.role)
    if payload.status is not None:
        user.status = _normalize_status(payload.status)
    if payload.plan_type is not None:
        previous_plan = user.plan_type
        apply_plan_defaults(user, normalize_plan_type(payload.plan_type))
        log_platform_audit(
            db,
            action="PLAN_ASSIGNMENT",
            target_type="user",
            target_id=str(user.id),
            metadata={"previous_plan": previous_plan, "next_plan": user.plan_type, "admin_id": admin.id},
            actor_type="admin",
            actor_id=str(admin.id),
        )
    if payload.monthly_quota is not None:
        user.monthly_quota = max(0, payload.monthly_quota)
    if payload.used_quota is not None:
        user.used_quota = max(0, payload.used_quota)
    if payload.monthly_cost_limit is not None:
        user.monthly_cost_limit = max(0.0, payload.monthly_cost_limit)
    if payload.used_cost is not None:
        user.used_cost = max(0.0, payload.used_cost)
    if payload.credit_balance is not None:
        user.credit_balance = max(0, payload.credit_balance)
    if payload.credits_used is not None:
        user.credits_used = max(0, payload.credits_used)
    if payload.credits_granted is not None:
        user.credits_granted = max(0, payload.credits_granted)
    db.commit()
    db.refresh(user)
    _log_admin_action(db, admin.id, "UPDATE_USER", "user", str(user.id), payload.model_dump(exclude_none=True))
    return _user_response(user)


@router.post("/users/{user_id}/reset-quota", response_model=AdminUserResponse)
def reset_user_quota(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> AdminUserResponse:
    user = db.get(User, user_id)
    if not user or user.deleted_at is not None:
        raise AppError("user_not_found", "User not found.", 404)
    reset_usage_cycle(user)
    log_platform_audit(
        db,
        action="QUOTA_RESET",
        target_type="user",
        target_id=str(user.id),
        metadata={"admin_id": admin.id},
        actor_type="admin",
        actor_id=str(admin.id),
    )
    db.commit()
    db.refresh(user)
    _log_admin_action(db, admin.id, "RESET_QUOTA", "user", str(user.id), {})
    return _user_response(user)


@router.post("/users/{user_id}/reset-cost", response_model=AdminUserResponse)
def reset_user_cost(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> AdminUserResponse:
    user = db.get(User, user_id)
    if not user or user.deleted_at is not None:
        raise AppError("user_not_found", "User not found.", 404)
    user.used_cost = 0.0
    log_platform_audit(
        db,
        action="COST_RESET",
        target_type="user",
        target_id=str(user.id),
        metadata={"admin_id": admin.id},
        actor_type="admin",
        actor_id=str(admin.id),
    )
    db.commit()
    db.refresh(user)
    _log_admin_action(db, admin.id, "RESET_COST", "user", str(user.id), {})
    return _user_response(user)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> Response:
    user = db.get(User, user_id)
    if not user or user.deleted_at is not None:
        raise AppError("user_not_found", "User not found.", 404)
    if user.role == "super_admin" and admin.role != "super_admin":
        raise AppError("admin_forbidden", "Only super admins can delete super admins.", 403)
    soft_delete_user(user)
    db.commit()
    _log_admin_action(db, admin.id, "DELETE_USER", "user", str(user_id), {})
    return Response(status_code=204)


@router.get("/models", response_model=list[ModelTemplateResponse])
def list_models(
    status: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> list[ModelTemplateResponse]:
    query = select(ModelTemplate).where(ModelTemplate.deleted_at.is_(None)).order_by(ModelTemplate.created_at.desc())
    if status:
        query = query.where(ModelTemplate.status == status)
    return [_model_response(item) for item in db.scalars(query).all()]


@router.get("/models/public")
def list_public_models(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    return list_public_model_templates(db, settings)


@router.post("/models", response_model=ModelTemplateResponse)
async def create_model(
    payload_json: str = Form(...),
    reference_image: UploadFile | None = File(default=None),
    thumbnail_image: UploadFile | None = File(default=None),
    front_pose: UploadFile | None = File(default=None),
    side_45_pose: UploadFile | None = File(default=None),
    walking_pose: UploadFile | None = File(default=None),
    back_pose: UploadFile | None = File(default=None),
    hand_on_hip_pose: UploadFile | None = File(default=None),
    sitting_pose: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> ModelTemplateResponse:
    payload = ModelTemplateUpsertRequest.model_validate_json(payload_json)
    existing = db.get(ModelTemplate, payload.id)
    if existing and existing.deleted_at is None:
        raise AppError("model_exists", "Model already exists.", 409)
    if existing and existing.deleted_at is not None:
        model = existing
        model.deleted_at = None
        model.name = payload.name
        model.gender = payload.gender
        model.body_type = payload.body_type
        model.height_cm = payload.height_cm
        model.weight_kg = payload.weight_kg
        model.garment_type = payload.garment_type
        model.is_ai_generated = payload.is_ai_generated
        model.status = payload.status
        model.quality_status = _normalize_quality_status(payload.quality_status)
        model.poses = payload.poses
    else:
        model = ModelTemplate(**{**payload.model_dump(), "quality_status": _normalize_quality_status(payload.quality_status)})
        db.add(model)
    db.commit()
    db.refresh(model)
    await _apply_model_uploads(model, reference_image, thumbnail_image, _pose_uploads(front_pose, side_45_pose, walking_pose, back_pose, hand_on_hip_pose, sitting_pose))
    db.commit()
    db.refresh(model)
    _log_admin_action(db, admin.id, "CREATE_MODEL", "model", model.id, {"name": model.name})
    return _model_response(model)


@router.get("/models/{model_id}", response_model=ModelTemplateResponse)
def get_model(model_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_admin)) -> ModelTemplateResponse:
    model = db.get(ModelTemplate, model_id)
    if not model or model.deleted_at is not None:
        raise AppError("model_not_found", "Model not found.", 404)
    return _model_response(model)


@router.put("/models/{model_id}", response_model=ModelTemplateResponse)
async def update_model(
    model_id: str,
    payload_json: str = Form(...),
    reference_image: UploadFile | None = File(default=None),
    thumbnail_image: UploadFile | None = File(default=None),
    front_pose: UploadFile | None = File(default=None),
    side_45_pose: UploadFile | None = File(default=None),
    walking_pose: UploadFile | None = File(default=None),
    back_pose: UploadFile | None = File(default=None),
    hand_on_hip_pose: UploadFile | None = File(default=None),
    sitting_pose: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> ModelTemplateResponse:
    model = db.get(ModelTemplate, model_id)
    if not model or model.deleted_at is not None:
        raise AppError("model_not_found", "Model not found.", 404)
    payload = ModelTemplateUpsertRequest.model_validate_json(payload_json)
    model.name = payload.name
    model.gender = payload.gender
    model.body_type = payload.body_type
    model.height_cm = payload.height_cm
    model.weight_kg = payload.weight_kg
    model.garment_type = payload.garment_type
    model.is_ai_generated = payload.is_ai_generated
    model.status = payload.status
    model.quality_status = _normalize_quality_status(payload.quality_status)
    model.poses = payload.poses
    await _apply_model_uploads(model, reference_image, thumbnail_image, _pose_uploads(front_pose, side_45_pose, walking_pose, back_pose, hand_on_hip_pose, sitting_pose))
    db.commit()
    db.refresh(model)
    _log_admin_action(db, admin.id, "UPDATE_MODEL", "model", model.id, {"name": model.name})
    return _model_response(model)


@router.delete("/models/{model_id}", status_code=204)
def delete_model(
    model_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> Response:
    model = db.get(ModelTemplate, model_id)
    if not model or model.deleted_at is not None:
        raise AppError("model_not_found", "Model not found.", 404)
    soft_delete_model(model)
    db.commit()
    _log_admin_action(db, admin.id, "DELETE_MODEL", "model", model_id, {})
    return Response(status_code=204)


@router.get("/jobs", response_model=list[GeneratedImageJobResponse])
def list_jobs(
    user_id: int | None = None,
    status: str | None = None,
    model_id: str | None = None,
    ai_model: str | None = None,
    failed_validation: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> list[GeneratedImageJobResponse]:
    query = select(GeneratedImageJob).where(GeneratedImageJob.deleted_at.is_(None)).order_by(GeneratedImageJob.created_at.desc())
    if user_id is not None:
        query = query.where(GeneratedImageJob.user_id == user_id)
    if status:
        query = query.where(GeneratedImageJob.status == status)
    if model_id:
        query = query.where(GeneratedImageJob.model_id == model_id)
    if ai_model:
        query = query.where(GeneratedImageJob.ai_model == ai_model)
    jobs = db.scalars(query).all()
    if failed_validation:
        jobs = [job for job in jobs if (job.validation_result or {}).get("failed_validations")]
    return [_job_response(job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=GeneratedImageJobDetailResponse)
def get_job(job_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_admin)) -> GeneratedImageJobDetailResponse:
    job = db.get(GeneratedImageJob, job_id)
    if not job or job.deleted_at is not None:
        raise AppError("job_not_found", "Job not found.", 404)
    return _job_detail_response(db, job)


@router.post("/jobs/{job_id}/retry", response_model=GeneratedImageJobResponse)
async def retry_job(
    job_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    settings: Settings = Depends(get_settings),
) -> GeneratedImageJobResponse:
    job = db.get(GeneratedImageJob, job_id)
    if not job or job.deleted_at is not None:
        raise AppError("job_not_found", "Job not found.", 404)
    redis = require_redis(settings)
    job.status = "pending"
    job.step = "queued"
    job.error_message = None
    job.retry_count += 1
    db.commit()
    await redis.rpush(job.queue_name or IMAGE_JOB_QUEUE_KEY, job_id)
    _log_admin_action(db, admin.id, "RETRY_JOB", "job", job_id, {})
    return _job_response(job)


@router.post("/jobs/{job_id}/images/{image_id}/actions", response_model=GeneratedImageJobResponse)
async def update_job_image_action(
    job_id: str,
    image_id: str,
    payload: ImageGenerationImageActionRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    settings: Settings = Depends(get_settings),
) -> GeneratedImageJobResponse:
    job = db.get(GeneratedImageJob, job_id)
    if not job or job.deleted_at is not None:
        raise AppError("job_not_found", "Job not found.", 404)
    redis = require_redis(settings)
    await ProductImageGenerator(settings, redis).update_job_image(
        job_id=job_id,
        image_id=image_id,
        user_id=job.user_id,
        db=db,
        action=payload.action,
    )
    _log_admin_action(db, admin.id, "UPDATE_JOB_IMAGE", "job_image", f"{job_id}:{image_id}", payload.model_dump())
    db.refresh(job)
    return _job_response(job)


@router.post("/jobs/{job_id}/images/{image_id}/retry", response_model=GeneratedImageJobResponse)
async def retry_single_job_image(
    job_id: str,
    image_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    settings: Settings = Depends(get_settings),
) -> GeneratedImageJobResponse:
    job = db.get(GeneratedImageJob, job_id)
    if not job or job.deleted_at is not None:
        raise AppError("job_not_found", "Job not found.", 404)
    redis = require_redis(settings)
    retried_job = await ProductImageGenerator(settings, redis).retry_single_catalog_image_job(
        job_id=job_id,
        image_id=image_id,
        user_id=job.user_id,
        db=db,
    )
    _log_admin_action(db, admin.id, "RETRY_JOB_IMAGE", "job_image", f"{job_id}:{image_id}", {})
    created_job = db.get(GeneratedImageJob, retried_job["id"])
    return _job_response(created_job) if created_job else GeneratedImageJobResponse.model_validate(retried_job)


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(
    job_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> Response:
    job = db.get(GeneratedImageJob, job_id)
    if not job or job.deleted_at is not None:
        raise AppError("job_not_found", "Job not found.", 404)
    soft_delete_job(job)
    db.commit()
    _log_admin_action(db, admin.id, "DELETE_JOB", "job", job_id, {})
    return Response(status_code=204)


@router.get("/settings/ai", response_model=AdminAiSettingsResponse)
def get_ai_settings(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: User = Depends(get_current_admin),
) -> AdminAiSettingsResponse:
    row = _ensure_ai_settings(db)
    return _settings_response(row, settings)


@router.put("/settings/ai", response_model=AdminAiSettingsResponse)
def update_ai_settings(
    payload: AdminAiSettingsUpdateRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    admin: User = Depends(get_current_admin),
) -> AdminAiSettingsResponse:
    row = _ensure_ai_settings(db)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    _log_admin_action(db, admin.id, "UPDATE_SETTINGS", "setting", "ai", payload.model_dump())
    return _settings_response(row, settings)


@router.get("/usage", response_model=AdminUsageSummaryResponse)
def get_usage(
    user_id: int | None = None,
    provider: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> AdminUsageSummaryResponse:
    query = select(UsageRecord).join(GeneratedImageJob, isouter=True).where(
        (GeneratedImageJob.deleted_at.is_(None)) | (UsageRecord.job_id.is_(None))
    ).order_by(UsageRecord.created_at.desc())
    if user_id is not None:
        query = query.where(UsageRecord.user_id == user_id)
    if provider:
        query = query.where(UsageRecord.provider == provider)
    items = db.scalars(query).all()
    by_provider: dict[str, float] = {}
    for item in items:
        by_provider[item.provider] = round(by_provider.get(item.provider, 0.0) + float(item.estimated_cost or 0.0), 4)
    successful_generations = sum(1 for item in items if item.operation == "image_generation")
    failed_generations = db.scalar(
        select(func.count()).select_from(GeneratedImageJob).where(GeneratedImageJob.status == "failed", GeneratedImageJob.deleted_at.is_(None))
    ) or 0
    return AdminUsageSummaryResponse(
        total_estimated_cost=round(sum(float(item.estimated_cost or 0.0) for item in items), 4),
        total_quantity=sum(item.quantity for item in items),
        successful_generations=successful_generations,
        failed_generations=failed_generations,
        by_provider=by_provider,
        items=[_usage_response(item) for item in items],
    )


def _user_response(user: User) -> AdminUserResponse:
    plan = get_usage_plan(user.plan_type)
    return AdminUserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        status=user.status,
        plan_type=plan.plan_type,
        max_images_per_job=plan.max_images_per_job,
        allow_legacy_vton=plan.allow_legacy_vton,
        allow_gpt_image=plan.allow_gpt_image,
        priority_queue=plan.priority_queue,
        monthly_quota=user.monthly_quota,
        used_quota=user.used_quota,
        monthly_cost_limit=user.monthly_cost_limit,
        used_cost=user.used_cost,
        credit_balance=max(0, int(user.credit_balance or 0)),
        credits_used=max(0, int(user.credits_used or 0)),
        credits_granted=max(0, int(user.credits_granted or 0)),
        quota_reset_at=user.quota_reset_at,
        last_quota_reset_at=user.last_quota_reset_at,
        close_to_quota_limit=quota_ratio(user) >= 0.8,
        close_to_cost_limit=cost_ratio(user) >= 0.8,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _dashboard_user_metric(user: User) -> AdminDashboardUserMetric:
    return AdminDashboardUserMetric(
        user_id=user.id,
        name=user.name,
        email=user.email,
        plan_type=user.plan_type,
        used_quota=user.used_quota,
        monthly_quota=user.monthly_quota,
        quota_percent=round(quota_ratio(user) * 100, 2),
        used_cost=round(float(user.used_cost or 0.0), 4),
        monthly_cost_limit=user.monthly_cost_limit,
        cost_percent=round(cost_ratio(user) * 100, 2) if user.monthly_cost_limit else None,
    )


def _refresh_users_if_needed(db: Session, users: list[User]) -> bool:
    changed = False
    for user in users:
        if reset_usage_if_due(user):
            changed = True
    if changed:
        db.commit()
    return changed


def _model_response(model: ModelTemplate) -> ModelTemplateResponse:
    return ModelTemplateResponse.model_validate(model, from_attributes=True)


def _job_response(job: GeneratedImageJob) -> GeneratedImageJobResponse:
    return GeneratedImageJobResponse.model_validate(job, from_attributes=True)


def _job_detail_response(db: Session, job: GeneratedImageJob) -> GeneratedImageJobDetailResponse:
    metadata = job.metadata_json or {}
    input_images = []
    for name in ["front.jpg", "back.jpg", "model.jpg"]:
        input_images.append(
            {
                "label": name.split(".")[0],
                "url": f"/storage/image_jobs/{job.id}/input/{name}",
            }
        )
    selected_model_image = None
    if metadata.get("selected_model_image_url"):
        selected_model_image = {
            "url": metadata.get("selected_model_image_url"),
            "model_id": metadata.get("model_id"),
        }
    elif metadata.get("model_id"):
        selected_model_image = {
            "url": f"/storage/admin_models/{metadata.get('model_id')}/reference.png",
            "model_id": metadata.get("model_id"),
        }
    usage_records = db.scalars(
        select(UsageRecord).where(UsageRecord.job_id == job.id).order_by(UsageRecord.created_at.desc())
    ).all()
    data = GeneratedImageJobResponse.model_validate(job, from_attributes=True).model_dump()
    data["input_images"] = input_images
    data["selected_model_image"] = selected_model_image
    data["usage_records"] = [_usage_response(item).model_dump() for item in usage_records]
    return GeneratedImageJobDetailResponse.model_validate(data)


def _usage_response(item: UsageRecord) -> UsageRecordResponse:
    return UsageRecordResponse.model_validate(item, from_attributes=True)


def _normalize_role(value: str) -> str:
    role = value.strip().lower()
    if role not in {"user", "admin", "super_admin"}:
        raise AppError("invalid_role", "Role must be user, admin, or super_admin.", 400)
    return role


def _normalize_status(value: str) -> str:
    status = value.strip().lower()
    if status not in {"active", "suspended"}:
        raise AppError("invalid_status", "Status must be active or suspended.", 400)
    return status


def _normalize_quality_status(value: str) -> str:
    quality_status = value.strip().lower()
    if quality_status not in {"draft", "approved", "rejected"}:
        raise AppError("invalid_quality_status", "Quality status must be draft, approved, or rejected.", 400)
    return quality_status


async def _apply_model_uploads(
    model: ModelTemplate,
    reference_image: UploadFile | None,
    thumbnail_image: UploadFile | None,
    pose_uploads: dict[str, UploadFile | None],
) -> None:
    model_dir = MODEL_STORAGE_DIR / model.id
    model_dir.mkdir(parents=True, exist_ok=True)
    if reference_image is not None:
        model.reference_image_url = await _save_image_upload(reference_image, model_dir, "reference")
    if thumbnail_image is not None:
        model.thumbnail_url = await _save_image_upload(thumbnail_image, model_dir, "thumbnail")
    poses = dict(model.poses or {})
    for pose_name, upload in pose_uploads.items():
        if upload is None:
            continue
        poses[pose_name] = await _save_image_upload(upload, model_dir, pose_name)
    model.poses = poses


def _pose_uploads(
    front_pose: UploadFile | None,
    side_45_pose: UploadFile | None,
    walking_pose: UploadFile | None,
    back_pose: UploadFile | None,
    hand_on_hip_pose: UploadFile | None,
    sitting_pose: UploadFile | None,
) -> dict[str, UploadFile | None]:
    return {
        "front": front_pose,
        "side_45": side_45_pose,
        "walking": walking_pose,
        "back": back_pose,
        "hand_on_hip": hand_on_hip_pose,
        "sitting": sitting_pose,
    }


async def _save_image_upload(upload: UploadFile, target_dir: Path, stem: str) -> str:
    if upload.content_type not in ALLOWED_IMAGE_TYPES:
        raise AppError("invalid_image_type", "Images must be JPG, PNG, or WEBP.", 400)
    extension = ALLOWED_IMAGE_TYPES[upload.content_type]
    content = await upload.read()
    if len(content) > 10 * 1024 * 1024:
        raise AppError("image_too_large", "Images must be 10MB or smaller.", 413)
    path = target_dir / f"{stem}{extension}"
    path.write_bytes(content)
    return f"/storage/admin_models/{target_dir.name}/{path.name}"


def _ensure_ai_settings(db: Session) -> AdminAiSettings:
    return get_or_create_admin_ai_settings(db)


def _settings_response(row: AdminAiSettings, settings: Settings) -> AdminAiSettingsResponse:
    return AdminAiSettingsResponse(
        default_image_model=row.default_image_model,
        fallback_image_model=row.fallback_image_model,
        gemini_model=row.gemini_model,
        max_retry=row.max_retry,
        default_quantity=row.default_quantity,
        realism_threshold=row.realism_threshold,
        validation_threshold=row.validation_threshold,
        validation_failure_behavior=row.validation_failure_behavior,
        allow_legacy_vton=row.allow_legacy_vton,
        openai_configured=bool(settings.openai_api_key),
        fal_configured=bool(settings.fal_key),
        gemini_configured=bool(settings.gemini_api_key),
    )


def _log_admin_action(
    db: Session,
    admin_id: int,
    action: str,
    target_type: str,
    target_id: str | None,
    metadata: dict,
) -> None:
    db.add(
        AdminAuditLog(
            id=uuid4().hex,
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_json=metadata,
        )
    )
    db.commit()
