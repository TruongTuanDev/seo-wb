import json
import uuid
from typing import Annotated, Any
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from fastapi.responses import FileResponse
import asyncio
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_store
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models.admin import GeneratedImageJob
from app.models.card import CardDraft, CardJob
from app.models.user import User
from app.schemas.card import (
    CardGenerateResponse,
    CardJobResponse,
    DraftListResponse,
    CardUploadGroup,
    DraftResponse,
    DraftUpdateRequest,
    MediaUploadByLinksRequest,
    MoveNmRequest,
    ProductInput,
    PushDraftRequest,
    PushMergeRequest,
    PushResponse,
    ImageAnalysis,
    ImageGenerationImageActionRequest,
    ImageGenerationJobResponse,
)
from app.services.card_flow import CardFlowService
from app.services.rabbitmq_publisher import publish_sync_job
from app.services.admin_runtime import get_effective_ai_runtime_settings, list_public_model_templates
from app.services.billing_foundation import credit_cost_for_job, pending_credit_reservations, queue_name_for_plan
from app.services.product_image_generator import ProductImageGenerator
from app.services.redis_client import require_redis
from app.services.usage_plans import get_usage_plan


router = APIRouter(prefix="/cards", tags=["cards"])
JOB_STORAGE_DIR = Path("storage/card_jobs")
CHUNK_SIZE = 1024 * 1024

def resolve_model_image_path(model_id: str) -> Path | None:
    import os
    admin_model_dir = Path("storage/admin_models") / model_id
    if admin_model_dir.is_dir():
        for candidate in ["reference.jpg", "reference.jpeg", "reference.png", "reference.webp", "front.jpg", "front.jpeg", "front.png", "front.webp"]:
            path = admin_model_dir / candidate
            if path.exists():
                return path
    clean_id = model_id.replace("_", "")
    for m_id in [model_id, clean_id]:
        model_dir = Path("storage/models") / m_id
        if model_dir.is_dir():
            for filename in os.listdir(model_dir):
                if filename.lower().startswith("front") and filename.lower().endswith((".png", ".jpg", ".jpeg")):
                    return model_dir / filename
    for m_id in [model_id, clean_id]:
        models_dir = Path("storage/models")
        if models_dir.is_dir():
            for filename in os.listdir(models_dir):
                name, ext = os.path.splitext(filename)
                if name.lower() == m_id.lower() and ext.lower() in {".png", ".jpg", ".jpeg"}:
                    return models_dir / filename
    models_dir = Path("storage/models")
    if models_dir.is_dir():
        for filename in os.listdir(models_dir):
            name, ext = os.path.splitext(filename)
            if name.lower() == "model1" and ext.lower() in {".png", ".jpg", ".jpeg"}:
                return models_dir / filename
    return None


def select_auto_model_template(
    db: Session,
    garment_json: dict[str, Any],
    analysis: dict[str, Any],
    selected_model_gender: str | None
) -> Any | None:
    category = garment_json.get("category") or analysis.get("category")
    mapped_garment_type = None
    if category:
        cat = category.lower().strip()
        if any(token in cat for token in ["брюки", "штаны", "леггинсы", "джоггеры", "pants", "джинсы", "jeans", "шорты", "shorts"]):
            mapped_garment_type = "pants"
        elif any(token in cat for token in ["юбк", "skirt", "плать", "сарафан", "dress"]):
            mapped_garment_type = "dress"
        elif any(token in cat for token in ["рубаш", "блуз", "shirt", "футболк", "майк", "топ", "t-shirt", "худи", "свитшот", "толстовк", "джемпер", "свитер", "пуловер", "кардиган", "hoodie", "куртк", "пальто", "пиджак", "жилет", "ветровк", "бомбер", "jacket"]):
            mapped_garment_type = "shirt"
        elif any(token in cat for token in ["костюм", "комбинезон", "комплект", "set", "suit"]):
            mapped_garment_type = "suit"
        elif any(token in cat for token in ["обувь", "shoes", "ботин", "сапог", "кроссов"]):
            mapped_garment_type = "shoes"

    normalized_gender = str(selected_model_gender or garment_json.get("gender") or analysis.get("gender") or "female").lower()
    model_gender = "female"
    if any(token in normalized_gender for token in ("male", "man", "men", "boy", "муж")):
        model_gender = "male"

    from sqlalchemy import select, func, or_
    from app.models.admin import ModelTemplate

    query = select(ModelTemplate).where(
        ModelTemplate.status == "active",
        ModelTemplate.quality_status == "approved",
        ModelTemplate.deleted_at.is_(None),
        ModelTemplate.gender == model_gender
    )
    if mapped_garment_type:
        query = query.where(
            or_(
                ModelTemplate.garment_type == mapped_garment_type,
                ModelTemplate.garment_type == "full_body",
                ModelTemplate.garment_type.is_(None)
            )
        )
    query = query.order_by(func.random())
    resolved_model = db.scalars(query).first()

    if not resolved_model:
        query_fb = select(ModelTemplate).where(
            ModelTemplate.status == "active",
            ModelTemplate.quality_status == "approved",
            ModelTemplate.deleted_at.is_(None),
            ModelTemplate.gender == model_gender
        ).order_by(func.random())
        resolved_model = db.scalars(query_fb).first()

    if not resolved_model:
        query_any = select(ModelTemplate).where(
            ModelTemplate.status == "active",
            ModelTemplate.quality_status == "approved",
            ModelTemplate.deleted_at.is_(None)
        ).order_by(func.random())
        resolved_model = db.scalars(query_any).first()

    return resolved_model



def _runtime_config(db: Session, settings: Settings) -> dict[str, Any]:
    runtime = get_effective_ai_runtime_settings(db, settings)
    return {
        "default_image_model": runtime.default_image_model,
        "fallback_image_model": runtime.fallback_image_model,
        "gemini_model": runtime.gemini_model,
        "max_retry": runtime.max_retry,
        "default_quantity": runtime.default_quantity,
        "realism_threshold": runtime.realism_threshold,
        "validation_threshold": runtime.validation_threshold,
        "validation_failure_behavior": runtime.validation_failure_behavior,
        "allow_legacy_vton": runtime.allow_legacy_vton,
    }


def _normalize_generation_quantity(quantity: int, runtime_config: dict[str, Any], max_images: int) -> int:
    default_quantity = int(runtime_config.get("default_quantity") or 5)
    normalized = quantity if 1 <= quantity <= max_images else default_quantity
    return max(1, min(normalized, max_images))


def _normalize_catalog_bundle_quantity(quantity: int) -> int:
    if quantity <= 1:
        return 1
    if quantity <= 3:
        return 3
    if quantity <= 5:
        return 5
    if quantity <= 6:
        return 6
    return 6


def _enforce_user_quota(user: User, quantity: int) -> None:
    if user.used_quota + quantity > user.monthly_quota:
        remaining = max(0, user.monthly_quota - user.used_quota)
        raise AppError(
            "quota_exceeded",
            f"Monthly generation quota exceeded. Remaining quota: {remaining}.",
            403,
        )


def _enforce_user_card_quota(user: User, quantity: int) -> None:
    monthly_card_quota = max(0, int(user.monthly_card_quota or 0))
    used_card_quota = max(0, int(user.used_card_quota or 0))
    if used_card_quota + quantity > monthly_card_quota:
        remaining = max(0, monthly_card_quota - used_card_quota)
        raise AppError(
            "card_quota_exceeded",
            f"Monthly card creation quota exceeded. Remaining card quota: {remaining}.",
            403,
        )


def _estimate_generation_cost(runtime_config: dict[str, Any], job_type: str, quantity: int) -> float:
    model = str(runtime_config.get("default_image_model") or "gpt-image-2").lower()
    per_image = 0.05 if "gpt-image" in model else 0.03
    if "gemini" in model:
        per_image = 0.01
    if job_type == "try_on":
        per_image = max(per_image, 0.03)
    return round(max(1, quantity) * per_image, 4)


def _enforce_user_cost_limit(user: User, estimated_cost: float) -> None:
    if user.monthly_cost_limit is None:
        return
    if float(user.used_cost or 0.0) + estimated_cost > float(user.monthly_cost_limit):
        remaining = max(0.0, float(user.monthly_cost_limit) - float(user.used_cost or 0.0))
        raise AppError(
            "cost_limit_exceeded",
            f"Monthly cost limit exceeded. Remaining cost budget: ${remaining:.2f}.",
            403,
        )


def _enforce_plan_restrictions(user: User, quantity: int, *, job_type: str) -> None:
    plan = get_usage_plan(getattr(user, "plan_type", None))
    if quantity > plan.max_images_per_job:
        raise AppError(
            "plan_job_limit_exceeded",
            f"Your {plan.plan_type.title()} plan allows at most {plan.max_images_per_job} images per job.",
            403,
        )
    if job_type == "try_on" and not plan.allow_legacy_vton:
        raise AppError(
            "plan_job_type_forbidden",
            f"Your {plan.plan_type.title()} plan does not include legacy virtual try-on.",
            403,
        )
    if job_type in {"gpt_image", "gpt_image_openai"} and not plan.allow_gpt_image:
        raise AppError(
            "plan_job_type_forbidden",
            f"Your {plan.plan_type.title()} plan does not include GPT image generation.",
            403,
        )


def _enforce_credit_balance(db: Session, user: User, credit_cost: int) -> None:
    if credit_cost <= 0:
        return
    pending_credits = pending_credit_reservations(db, user.id)
    available_credits = max(0, int(user.credit_balance or 0) - pending_credits)
    if credit_cost > available_credits:
        raise AppError(
            "insufficient_credits",
            f"Not enough credits to start this job. Available credits: {available_credits}.",
            403,
        )


def _draft_analysis(draft: CardDraft) -> dict[str, Any]:
    return draft.analysis if isinstance(draft.analysis, dict) else {}


def _draft_garment_json(draft: CardDraft) -> dict[str, Any]:
    if isinstance(draft.garment_json, dict) and draft.garment_json:
        return draft.garment_json
    analysis = _draft_analysis(draft)
    garment_json = analysis.get("garment_json")
    return garment_json if isinstance(garment_json, dict) else {}


def _extract_variant_context(draft: CardDraft, variant_index: int) -> tuple[str | None, str | None]:
    payload = draft.card_payload if isinstance(draft.card_payload, list) else []
    if not payload or not isinstance(payload[0], dict):
        return None, None
    variants = payload[0].get("variants") or []
    if not isinstance(variants, list) or variant_index >= len(variants) or variant_index < 0:
        return None, None
    variant = variants[variant_index]
    if not isinstance(variant, dict):
        return None, None
    title = variant.get("title")
    description = variant.get("description")
    return str(title) if title else None, str(description) if description else None


def _lock_user_for_generation_budget(db: Session, user_id: int) -> User:
    statement = select(User).where(User.id == user_id).with_for_update()
    locked_user = db.execute(statement).scalar_one_or_none()
    if locked_user is None:
        raise AppError("user_not_found", "User was not found.", 404)
    return locked_user


def _pending_generation_usage(db: Session, user_id: int) -> tuple[int, float]:
    pending_statuses = ("pending", "running")
    pending_quantity, pending_cost = db.query(
        func.coalesce(func.sum(GeneratedImageJob.quantity), 0),
        func.coalesce(func.sum(GeneratedImageJob.estimated_cost), 0.0),
    ).filter(
        GeneratedImageJob.user_id == user_id,
        GeneratedImageJob.status.in_(pending_statuses),
    ).one()
    return int(pending_quantity or 0), float(pending_cost or 0.0)


def _enforce_generation_budget(db: Session, user: User, quantity: int, estimated_cost: float) -> None:
    pending_quota, pending_cost = _pending_generation_usage(db, user.id)
    effective_used_quota = max(0, int(user.used_quota or 0) + pending_quota)
    effective_monthly_quota = max(0, int(user.monthly_quota or 0))
    if effective_used_quota + quantity > effective_monthly_quota:
        remaining = max(0, effective_monthly_quota - effective_used_quota)
        raise AppError(
            "quota_exceeded",
            f"Monthly generation quota exceeded. Remaining quota: {remaining}.",
            403,
        )

    if user.monthly_cost_limit is None:
        return

    effective_used_cost = round(float(user.used_cost or 0.0) + pending_cost, 4)
    if effective_used_cost + estimated_cost > float(user.monthly_cost_limit):
        remaining = max(0.0, float(user.monthly_cost_limit) - effective_used_cost)
        raise AppError(
            "cost_limit_exceeded",
            f"Monthly cost limit exceeded. Remaining cost budget: ${remaining:.2f}.",
            403,
        )


@router.post("/generate", response_model=CardGenerateResponse)
async def generate_card(
    store_id: int = Form(...),
    product_input_json: str = Form(...),
    images: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
) -> CardGenerateResponse:
    store = get_owned_store(db, user, store_id)
    product_input = _parse_product_input(product_input_json)
    if len(images) > settings.max_generate_images:
        raise AppError("too_many_images", f"Upload at most {settings.max_generate_images} images for analysis.", 400)
    image_bytes = [
        await _read_upload_limited(image, settings.max_upload_image_bytes, "image_too_large")
        for image in images
    ]
    draft = await CardFlowService(settings, db, user, store).generate_draft(image_bytes, product_input)
    card_payload = [CardUploadGroup.model_validate(group) for group in draft.card_payload]
    analysis = _draft_analysis(draft)
    return CardGenerateResponse(
        draft_id=draft.id,
        analysis=ImageAnalysis.model_validate(analysis),
        card_payload=card_payload,
        warnings=analysis.get("warnings", []),
    )


@router.post("/jobs", response_model=CardJobResponse)
async def enqueue_card_job(
    store_id: int = Form(...),
    mode: str = Form(default="create_new"),
    card_payload_json: str = Form(...),
    media_manifest_json: str = Form(default='{"items": []}'),
    draft_id: int | None = Form(default=None),
    target_imt: int | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
) -> CardJobResponse:
    store = get_owned_store(db, user, store_id)
    if mode not in {"create_new", "add_to_existing_imt", "create_then_merge"}:
        raise AppError("invalid_job_mode", "Unsupported card job mode.", 400)
    if mode in {"add_to_existing_imt", "create_then_merge"} and not target_imt:
        raise AppError("missing_target_imt", "Target IMT is required for merge modes.", 400)
    if len(files) > settings.max_job_files:
        raise AppError("too_many_job_files", f"Upload at most {settings.max_job_files} media files per job.", 400)
    if len(card_payload_json.encode("utf-8")) > settings.max_card_payload_bytes:
        raise AppError("card_payload_too_large", "Card job payload is too large.", 413)
    if len(media_manifest_json.encode("utf-8")) > settings.max_card_payload_bytes:
        raise AppError("media_manifest_too_large", "Media manifest payload is too large.", 413)
    try:
        card_payload_raw = json.loads(card_payload_json)
        media_manifest_raw = json.loads(media_manifest_json)
        card_payload = [CardUploadGroup.model_validate(group).model_dump(mode="json", exclude_none=True) for group in card_payload_raw]
    except Exception as exc:
        raise AppError("invalid_card_job_payload", "Card job payload is invalid.", 400, {"reason": str(exc)[:500]}) from exc

    # Enrich payload
    flow = CardFlowService(settings, db, user, store)
    try:
        if mode == "add_to_existing_imt":
            if card_payload:
                await flow._enrich_payload({"cardsToAdd": card_payload[0]["variants"]}, card_payload[0]["subjectID"])
        else:
            for group in card_payload:
                await flow._enrich_payload([group], int(group["subjectID"]))
    except Exception as exc:
        raise AppError("enrichment_failed", f"Failed to enrich card payload: {str(exc)}", 400)

    if draft_id is not None:
        draft = _get_owned_draft(db, user, draft_id)
        draft.card_payload = card_payload
        draft.status = "queued"
        draft.subject_id = card_payload[0]["subjectID"] if card_payload else draft.subject_id
        draft.vendor_code = card_payload[0]["variants"][0]["vendorCode"] if card_payload and card_payload[0]["variants"] else draft.vendor_code

    job = CardJob(
        user_id=user.id,
        store_id=store_id,
        draft_id=draft_id,
        status="queued",
        step="queued",
        mode=mode,
        target_imt=target_imt,
        subject_id=card_payload[0]["subjectID"] if card_payload else None,
        card_payload=card_payload,
        media_manifest={"items": []},
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        stored_manifest = await _store_job_files(job.id, media_manifest_raw, files, settings.max_media_upload_bytes)
    except AppError:
        db.delete(job)
        db.commit()
        raise
    job.media_manifest = stored_manifest
    if draft_id is not None:
        draft = _get_owned_draft(db, user, draft_id)
        card_payload = _attach_media_to_payload(job.id, card_payload, stored_manifest)
        draft.card_payload = card_payload
        job.card_payload = card_payload
    db.commit()
    db.refresh(job)

    await asyncio.to_thread(publish_sync_job, settings, "card.push", store_id, {"job_id": job.id})
    return _job_response(job)


@router.get("/jobs/{job_id}", response_model=CardJobResponse)
def get_card_job(
    job_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> CardJobResponse:
    job = db.get(CardJob, job_id)
    if not job or job.user_id != user.id:
        raise AppError("job_not_found", "Card job was not found.", 404)
    return _job_response(job)


@router.post("/drafts/{draft_id}/image-generation/jobs", response_model=ImageGenerationJobResponse)
async def enqueue_image_generation_job(
    draft_id: int,
    store_id: int = Form(...),
    variant_id: str = Form(...),
    variant_index: int = Form(...),
    quantity: int = Form(...),
    metadata_json: str = Form(default="{}"),
    front_image: UploadFile = File(...),
    back_image: UploadFile = File(...),
    model_image: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
) -> ImageGenerationJobResponse:
    get_owned_store(db, user, store_id)
    draft = _get_owned_draft(db, user, draft_id)
    if draft.store_id != store_id:
        raise AppError("draft_store_mismatch", "Draft does not belong to this store.", 400)
    runtime_config = _runtime_config(db, settings)
    quantity = _normalize_generation_quantity(quantity, runtime_config, settings.max_ai_product_images)
    _enforce_plan_restrictions(user, quantity, job_type="image_generation")
    credit_cost = credit_cost_for_job("openai", quantity)
    estimated_cost = _estimate_generation_cost(runtime_config, "openai", quantity)
    locked_user = _lock_user_for_generation_budget(db, user.id)
    _enforce_generation_budget(db, locked_user, quantity, estimated_cost)
    _enforce_credit_balance(db, locked_user, credit_cost)
    try:
        metadata = json.loads(metadata_json)
        if not isinstance(metadata, dict):
            raise ValueError("metadata_json must be an object")
    except Exception as exc:
        raise AppError("invalid_image_job_metadata", "metadata_json must be a valid JSON object.", 400) from exc

    for upload in [front_image, back_image, model_image]:
        if upload is not None:
            _validate_image_upload(upload)
    metadata["runtime_config"] = runtime_config
    metadata.setdefault("model", runtime_config["default_image_model"])
    front_bytes = await _read_upload_limited(front_image, settings.max_upload_image_bytes, "image_too_large")
    back_bytes = await _read_upload_limited(back_image, settings.max_upload_image_bytes, "image_too_large")
    model_bytes = await _read_upload_limited(model_image, settings.max_upload_image_bytes, "image_too_large") if model_image else None
    redis = require_redis(settings)
    job = await ProductImageGenerator(settings, redis).create_job(
        user_id=user.id,
        store_id=store_id,
        draft_id=draft_id,
        variant_id=variant_id,
        variant_index=variant_index,
        quantity=quantity,
        metadata=metadata,
        front_image=front_bytes,
        back_image=back_bytes,
        model_image=model_bytes,
        queue_name=queue_name_for_plan(user.plan_type),
        credit_cost=credit_cost,
        db=db,
    )
    return ImageGenerationJobResponse.model_validate(job)


@router.get("/drafts/{draft_id}/image-generation/jobs/{job_id}", response_model=ImageGenerationJobResponse)
async def get_image_generation_job(
    draft_id: int,
    job_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ImageGenerationJobResponse:
    _get_owned_draft(db, user, draft_id)
    redis = require_redis(settings)
    job = await ProductImageGenerator(settings, redis).get_job(job_id, user.id)
    return ImageGenerationJobResponse.model_validate(job)


@router.get("/image-jobs/{job_id}/media/{file_name}")
async def get_generated_image(
    job_id: str,
    file_name: str,
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    redis = require_redis(settings)
    path = await ProductImageGenerator(settings, redis).resolve_media_path(job_id, file_name, user.id)
    return FileResponse(path, media_type="image/png")


@router.get("/try-on/models")
def list_try_on_models(
    garment_type: str | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return list_public_model_templates(db, settings, garment_type=garment_type)


@router.post("/drafts/{draft_id}/try-on/jobs", response_model=ImageGenerationJobResponse)
async def enqueue_try_on_job(
    draft_id: int,
    store_id: int = Form(...),
    variant_id: str = Form(...),
    variant_index: int = Form(...),
    selectedModelId: str = Form(...),
    selectedModelImageUrl: str = Form(...),
    selectedModelGender: str = Form(...),
    selectedModelBodyType: str = Form(...),
    posePack: str = Form(default=""),
    backgroundStyle: str = Form(default="none"),
    quantity: int = Form(...),
    productFrontImage: UploadFile = File(...),
    productBackImage: UploadFile | None = File(default=None),
    productCategory: str = Form(default=""),
    garmentType: str = Form(default=""),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
) -> ImageGenerationJobResponse:
    get_owned_store(db, user, store_id)
    draft = _get_owned_draft(db, user, draft_id)
    if draft.store_id != store_id:
        raise AppError("draft_store_mismatch", "Draft does not belong to this store.", 400)
    runtime_config = _runtime_config(db, settings)
    if not runtime_config.get("allow_legacy_vton", True):
        raise AppError("legacy_vton_disabled", "Legacy virtual try-on is disabled by admin settings.", 403)
    quantity = _normalize_generation_quantity(quantity, runtime_config, settings.max_ai_product_images)
    _enforce_plan_restrictions(user, quantity, job_type="try_on")
    credit_cost = credit_cost_for_job("try_on", quantity)
    estimated_cost = _estimate_generation_cost(runtime_config, "try_on", quantity)
    locked_user = _lock_user_for_generation_budget(db, user.id)
    _enforce_generation_budget(db, locked_user, quantity, estimated_cost)
    _enforce_credit_balance(db, locked_user, credit_cost)
        
    for upload in [productFrontImage]:
        _validate_image_upload(upload)
    if productBackImage:
        _validate_image_upload(productBackImage)

    front_bytes = await _read_upload_limited(productFrontImage, settings.max_upload_image_bytes, "image_too_large")
    back_bytes = await _read_upload_limited(productBackImage, settings.max_upload_image_bytes, "image_too_large") if productBackImage else None
    
    # Resolve product category and garment type
    resolved_category = productCategory
    analysis = _draft_analysis(draft)
    if not resolved_category:
        resolved_category = analysis.get("category") or ""
        
    resolved_garment_type = garmentType
    if not resolved_garment_type and resolved_category:
        from app.services.virtual_try_on import resolve_garment_type
        resolved_garment_type = resolve_garment_type(resolved_category)
    if not resolved_garment_type:
        resolved_garment_type = "upper_body"

    metadata = {
        "title": draft.vendor_code or "garment",
        "category": "try-on",
        "model_id": selectedModelId,
        "selected_model_image_url": selectedModelImageUrl,
        "selected_model_gender": selectedModelGender,
        "selected_model_body_type": selectedModelBodyType,
        "pose_pack": posePack,
        "background_style": backgroundStyle,
        "product_category": resolved_category,
        "garment_type": resolved_garment_type,
        "runtime_config": runtime_config,
        "model": runtime_config["default_image_model"],
    }

    redis = require_redis(settings)
    job = await ProductImageGenerator(settings, redis).create_job(
        user_id=user.id,
        store_id=store_id,
        draft_id=draft_id,
        variant_id=variant_id,
        variant_index=variant_index,
        quantity=quantity,
        metadata=metadata,
        front_image=front_bytes,
        back_image=back_bytes,
        model_image=None,
        job_type="try_on",
        model_id=selectedModelId,
        queue_name=queue_name_for_plan(user.plan_type),
        credit_cost=credit_cost,
        db=db,
    )
    return ImageGenerationJobResponse.model_validate(job)


@router.get("/drafts/{draft_id}/try-on/jobs/{job_id}", response_model=ImageGenerationJobResponse)
async def get_try_on_job(
    draft_id: int,
    job_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ImageGenerationJobResponse:
    _get_owned_draft(db, user, draft_id)
    redis = require_redis(settings)
    job = await ProductImageGenerator(settings, redis).get_job(job_id, user.id)
    return ImageGenerationJobResponse.model_validate(job)


@router.post("/drafts/{draft_id}/garment/analyze")
async def analyze_draft_garment(
    draft_id: int,
    front_image: UploadFile = File(...),
    back_image: UploadFile | None = File(default=None),
    title: str | None = Form(default=None),
    description: str | None = Form(default=None),
    category: str | None = Form(default=None),
    gender: str | None = Form(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    draft = _get_owned_draft(db, user, draft_id)
    _validate_image_upload(front_image)
    if back_image:
        _validate_image_upload(back_image)
    
    front_bytes = await _read_upload_limited(front_image, settings.max_upload_image_bytes, "image_too_large")
    back_bytes = await _read_upload_limited(back_image, settings.max_upload_image_bytes, "image_too_large") if back_image else None

    from app.services.garment_analyzer import GarmentAnalyzer
    analyzer = GarmentAnalyzer(settings)
    garment_json = analyzer.analyze(
        front_image_bytes=front_bytes,
        back_image_bytes=back_bytes,
        title=title,
        description=description,
        category=category,
        gender=gender
    )

    # Save to draft's analysis JSON column
    analysis_copy = dict(draft.analysis or {})
    analysis_copy["garment_json"] = garment_json
    analysis_copy["garment_area"] = garment_json.get("garment_area")
    draft.analysis = analysis_copy
    draft.garment_json = garment_json
    db.commit()

    return garment_json


@router.get("/drafts/{draft_id}/garment")
def get_draft_garment(
    draft_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    draft = _get_owned_draft(db, user, draft_id)
    garment_json = _draft_garment_json(draft)
    if not garment_json:
        raise AppError("garment_not_analyzed", "Garment has not been analyzed yet.", 404)
    return garment_json


@router.post("/drafts/{draft_id}/gpt-image/jobs", response_model=ImageGenerationJobResponse)
async def enqueue_gpt_image_job(
    draft_id: int,
    store_id: int = Form(...),
    variant_id: str = Form(...),
    variant_index: int = Form(...),
    selectedModelId: str | None = Form(default=None),
    selectedModelImageUrl: str | None = Form(default=None),
    selectedModelGender: str | None = Form(default=None),
    selectedModelBodyType: str | None = Form(default=None),
    style: str = Form(...),
    quantity: int = Form(...),
    productFrontImage: UploadFile = File(...),
    productBackImage: UploadFile | None = File(default=None),
    autoGenerateModel: bool = Form(default=False),
    model: str | None = Form(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
) -> ImageGenerationJobResponse:
    get_owned_store(db, user, store_id)
    draft = _get_owned_draft(db, user, draft_id)
    if draft.store_id != store_id:
        raise AppError("draft_store_mismatch", "Draft does not belong to this store.", 400)
    runtime_config = _runtime_config(db, settings)
    quantity = _normalize_generation_quantity(quantity, runtime_config, settings.max_ai_product_images)
    quantity = _normalize_catalog_bundle_quantity(quantity)
    _enforce_plan_restrictions(user, quantity, job_type="gpt_image")
    credit_cost = credit_cost_for_job("gpt_image", quantity)
    estimated_cost = _estimate_generation_cost(runtime_config, "gpt_image", quantity)
    locked_user = _lock_user_for_generation_budget(db, user.id)
    _enforce_generation_budget(db, locked_user, quantity, estimated_cost)
    _enforce_credit_balance(db, locked_user, credit_cost)

    auto_model_generation = bool(autoGenerateModel or selectedModelId == "auto_russian_model")
    if not auto_model_generation and (not selectedModelId or selectedModelId == "none"):
        raise AppError("missing_model_reference", "Please select a real model reference before generating catalog images.", 400)

    _validate_image_upload(productFrontImage)
    if productBackImage:
        _validate_image_upload(productBackImage)

    front_bytes = await _read_upload_limited(productFrontImage, settings.max_upload_image_bytes, "image_too_large")
    back_bytes = await _read_upload_limited(productBackImage, settings.max_upload_image_bytes, "image_too_large") if productBackImage else None

    # Resolve model reference image
    model_bytes = None
    if not auto_model_generation and selectedModelId and selectedModelId not in {"none", "auto_russian_model"}:
        model_p = resolve_model_image_path(selectedModelId)
        if model_p and model_p.exists():
            with open(model_p, "rb") as f:
                model_bytes = f.read()

    analysis = _draft_analysis(draft)
    garment_json = _draft_garment_json(draft)
    if not garment_json:
        from app.services.garment_analyzer import GarmentAnalyzer
        analyzer = GarmentAnalyzer(settings)
        title, description = _extract_variant_context(draft, variant_index)
        garment_json = analyzer.analyze(
            front_image_bytes=front_bytes,
            back_image_bytes=back_bytes,
            title=title or draft.vendor_code,
            description=description,
            category=analysis.get("category"),
            gender=selectedModelGender
        )
        analysis_copy = dict(analysis)
        analysis_copy["garment_json"] = garment_json
        analysis_copy["garment_area"] = garment_json.get("garment_area")
        draft.analysis = analysis_copy
        draft.garment_json = garment_json
        db.commit()

    if auto_model_generation:
        resolved_model = select_auto_model_template(db, garment_json, analysis, selectedModelGender)
        if resolved_model:
            selectedModelId = resolved_model.id
            selectedModelImageUrl = resolved_model.reference_image_url or (resolved_model.poses or {}).get("front") or resolved_model.thumbnail_url or ""
            selectedModelGender = resolved_model.gender
            selectedModelBodyType = resolved_model.body_type
            auto_model_generation = False

            model_p = resolve_model_image_path(selectedModelId)
            if model_p and model_p.exists():
                with open(model_p, "rb") as f:
                    model_bytes = f.read()

    metadata = {
        "title": draft.vendor_code or "garment",
        "category": "gpt-image",
        "model_id": "auto_russian_model" if auto_model_generation else (selectedModelId or "none"),
        "selected_model_image_url": "" if auto_model_generation else (selectedModelImageUrl or ""),
        "selected_model_gender": selectedModelGender or analysis.get("gender") or "female",
        "selected_model_body_type": selectedModelBodyType or "",
        "style": style,
        "garment_json": garment_json,
        "runtime_config": runtime_config,
        "auto_model_generation": auto_model_generation,
        "output_type": "catalog_bundle",
    }
    metadata["model"] = model or runtime_config["default_image_model"]

    redis = require_redis(settings)
    job = await ProductImageGenerator(settings, redis).create_job(
        user_id=user.id,
        store_id=store_id,
        draft_id=draft_id,
        variant_id=variant_id,
        variant_index=variant_index,
        quantity=quantity,
        metadata=metadata,
        front_image=front_bytes,
        back_image=back_bytes,
        model_image=model_bytes,
        job_type="gpt_image",
        model_id="auto_russian_model" if auto_model_generation else (selectedModelId or "none"),
        queue_name=queue_name_for_plan(user.plan_type),
        credit_cost=credit_cost,
        db=db,
    )
    return ImageGenerationJobResponse.model_validate(job)



@router.get("/drafts/{draft_id}/gpt-image/jobs/{job_id}", response_model=ImageGenerationJobResponse)
async def get_gpt_image_job(
    draft_id: int,
    job_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ImageGenerationJobResponse:
    _get_owned_draft(db, user, draft_id)
    redis = require_redis(settings)
    job = await ProductImageGenerator(settings, redis).get_job(job_id, user.id)
    return ImageGenerationJobResponse.model_validate(job)


@router.post("/drafts/{draft_id}/gpt-image-openai/jobs", response_model=ImageGenerationJobResponse)
async def enqueue_gpt_image_openai_job(
    draft_id: int,
    store_id: int = Form(...),
    variant_id: str = Form(...),
    variant_index: int = Form(...),
    selectedModelId: str | None = Form(default=None),
    selectedModelImageUrl: str | None = Form(default=None),
    selectedModelGender: str | None = Form(default=None),
    selectedModelBodyType: str | None = Form(default=None),
    style: str = Form(...),
    quantity: int = Form(...),
    productFrontImage: UploadFile = File(...),
    productBackImage: UploadFile | None = File(default=None),
    modelImage: UploadFile | None = File(default=None),
    autoGenerateModel: bool = Form(default=False),
    model: str | None = Form(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
) -> ImageGenerationJobResponse:
    get_owned_store(db, user, store_id)
    draft = _get_owned_draft(db, user, draft_id)
    if draft.store_id != store_id:
        raise AppError("draft_store_mismatch", "Draft does not belong to this store.", 400)
    runtime_config = _runtime_config(db, settings)
    quantity = _normalize_generation_quantity(quantity, runtime_config, settings.max_ai_product_images)
    quantity = _normalize_catalog_bundle_quantity(quantity)
    _enforce_plan_restrictions(user, quantity, job_type="gpt_image_openai")
    credit_cost = credit_cost_for_job("gpt_image_openai", quantity)
    estimated_cost = _estimate_generation_cost(runtime_config, "gpt_image_openai", quantity)
    locked_user = _lock_user_for_generation_budget(db, user.id)
    _enforce_generation_budget(db, locked_user, quantity, estimated_cost)
    _enforce_credit_balance(db, locked_user, credit_cost)

    auto_model_generation = bool(autoGenerateModel or selectedModelId == "auto_russian_model")
    if not auto_model_generation and not modelImage and (not selectedModelId or selectedModelId == "none"):
        raise AppError("missing_model_reference", "Please select a real model reference before generating catalog images.", 400)

    _validate_image_upload(productFrontImage)
    if productBackImage:
        _validate_image_upload(productBackImage)
    if modelImage:
        _validate_image_upload(modelImage)

    front_bytes = await _read_upload_limited(productFrontImage, settings.max_upload_image_bytes, "image_too_large")
    back_bytes = await _read_upload_limited(productBackImage, settings.max_upload_image_bytes, "image_too_large") if productBackImage else None

    # Resolve model reference image
    model_bytes = None
    if modelImage:
        model_bytes = await _read_upload_limited(modelImage, settings.max_upload_image_bytes, "image_too_large")
    elif selectedModelId and selectedModelId not in {"none", "auto_russian_model"}:
        model_p = resolve_model_image_path(selectedModelId)
        if model_p and model_p.exists():
            with open(model_p, "rb") as f:
                model_bytes = f.read()

    analysis = _draft_analysis(draft)
    garment_json = _draft_garment_json(draft)
    if not garment_json:
        from app.services.garment_analyzer import GarmentAnalyzer
        analyzer = GarmentAnalyzer(settings)
        title, description = _extract_variant_context(draft, variant_index)
        garment_json = analyzer.analyze(
            front_image_bytes=front_bytes,
            back_image_bytes=back_bytes,
            title=title or draft.vendor_code,
            description=description,
            category=analysis.get("category"),
            gender=selectedModelGender or analysis.get("gender") or "female"
        )
        analysis_copy = dict(analysis)
        analysis_copy["garment_json"] = garment_json
        analysis_copy["garment_area"] = garment_json.get("garment_area")
        draft.analysis = analysis_copy
        draft.garment_json = garment_json
        db.commit()

    if auto_model_generation:
        resolved_model = select_auto_model_template(db, garment_json, analysis, selectedModelGender)
        if resolved_model:
            selectedModelId = resolved_model.id
            selectedModelImageUrl = resolved_model.reference_image_url or (resolved_model.poses or {}).get("front") or resolved_model.thumbnail_url or ""
            selectedModelGender = resolved_model.gender
            selectedModelBodyType = resolved_model.body_type
            auto_model_generation = False

            model_p = resolve_model_image_path(selectedModelId)
            if model_p and model_p.exists():
                with open(model_p, "rb") as f:
                    model_bytes = f.read()

    metadata = {
        "title": draft.vendor_code or "garment",
        "category": "gpt-image",
        "model_id": "auto_russian_model" if auto_model_generation else ("custom" if modelImage else (selectedModelId or "none")),
        "selected_model_image_url": "" if (modelImage or auto_model_generation) else (selectedModelImageUrl or ""),
        "selected_model_gender": selectedModelGender or analysis.get("gender") or "female",
        "selected_model_body_type": selectedModelBodyType or "",
        "style": style,
        "garment_json": garment_json,
        "runtime_config": runtime_config,
        "auto_model_generation": auto_model_generation,
        "output_type": "catalog_bundle",
    }
    metadata["model"] = model or runtime_config["default_image_model"]

    redis = require_redis(settings)
    job = await ProductImageGenerator(settings, redis).create_job(
        user_id=user.id,
        store_id=store_id,
        draft_id=draft_id,
        variant_id=variant_id,
        variant_index=variant_index,
        quantity=quantity,
        metadata=metadata,
        front_image=front_bytes,
        back_image=back_bytes,
        model_image=model_bytes,
        job_type="gpt_image_openai",
        model_id="auto_russian_model" if auto_model_generation else ("custom" if modelImage else (selectedModelId or "none")),
        queue_name=queue_name_for_plan(user.plan_type),
        credit_cost=credit_cost,
        db=db,
    )
    return ImageGenerationJobResponse.model_validate(job)


@router.get("/drafts/{draft_id}/gpt-image-openai/jobs/{job_id}", response_model=ImageGenerationJobResponse)
async def get_gpt_image_openai_job(
    draft_id: int,
    job_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ImageGenerationJobResponse:
    _get_owned_draft(db, user, draft_id)
    redis = require_redis(settings)
    job = await ProductImageGenerator(settings, redis).get_job(job_id, user.id)
    return ImageGenerationJobResponse.model_validate(job)


@router.post("/drafts/{draft_id}/image-jobs/{job_id}/images/{image_id}/actions", response_model=ImageGenerationJobResponse)
async def update_generated_image_action(
    draft_id: int,
    job_id: str,
    image_id: str,
    payload: ImageGenerationImageActionRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ImageGenerationJobResponse:
    _get_owned_draft(db, user, draft_id)
    redis = require_redis(settings)
    job = await ProductImageGenerator(settings, redis).update_job_image(
        job_id=job_id,
        image_id=image_id,
        user_id=user.id,
        db=db,
        action=payload.action,
    )
    return ImageGenerationJobResponse.model_validate(job)


@router.post("/drafts/{draft_id}/image-jobs/{job_id}/images/{image_id}/retry", response_model=ImageGenerationJobResponse)
async def retry_single_generated_image(
    draft_id: int,
    job_id: str,
    image_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ImageGenerationJobResponse:
    _get_owned_draft(db, user, draft_id)
    redis = require_redis(settings)
    job = await ProductImageGenerator(settings, redis).retry_single_catalog_image_job(
        job_id=job_id,
        image_id=image_id,
        user_id=user.id,
        db=db,
    )
    return ImageGenerationJobResponse.model_validate(job)


async def _export_image_job_package(
    draft_id: int,
    job_id: str,
    marketplace: str,
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    _get_owned_draft(db, user, draft_id)
    redis = require_redis(settings)
    job = await ProductImageGenerator(settings, redis).get_job(job_id, user.id)
    
    if job.get("status") not in {"completed", "completed_with_warnings"}:
        raise AppError("job_not_completed", "Image generation job is not completed yet.", 400)
        
    from app.services.product_image_generator import IMAGE_JOB_STORAGE_DIR
    job_dir = IMAGE_JOB_STORAGE_DIR / job_id
    
    quality_report = job.get("quality_report") or {}
    images = job.get("images") or []
    
    from app.services.catalog_exporter import CatalogExporter
    exporter = CatalogExporter()
    try:
        zip_bytes = exporter.export_marketplace_package(job_dir, quality_report, images, marketplace)
    except ValueError as val_err:
        raise AppError("invalid_marketplace", str(val_err), 400)
        
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={marketplace}_catalog_{job_id[:8]}.zip"
        }
    )


@router.get("/drafts/{draft_id}/image-jobs/{job_id}/export/{marketplace}")
async def export_image_job(
    draft_id: int,
    job_id: str,
    marketplace: str,
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    return await _export_image_job_package(draft_id, job_id, marketplace, settings, user, db)


@router.get("/drafts/{draft_id}/try-on/jobs/{job_id}/export/{marketplace}")
async def export_try_on_job(
    draft_id: int,
    job_id: str,
    marketplace: str,
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    return await _export_image_job_package(draft_id, job_id, marketplace, settings, user, db)


@router.get("/drafts", response_model=DraftListResponse)
def list_drafts(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    store_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> DraftListResponse:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    query = db.query(CardDraft).filter(CardDraft.user_id == user.id)
    if store_id is not None:
        query = query.filter(CardDraft.store_id == store_id)
    total = query.count()
    drafts = query.order_by(CardDraft.updated_at.desc()).offset(offset).limit(limit).all()
    return DraftListResponse(
        items=[_draft_response(draft) for draft in drafts],
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(drafts) < total,
    )


@router.get("/drafts/{draft_id}", response_model=DraftResponse)
def get_draft(
    draft_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> DraftResponse:
    draft = _get_owned_draft(db, user, draft_id)
    return _draft_response(draft)


@router.get("/media/{job_id}/{file_name}")
def get_job_media(
    job_id: int,
    file_name: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    job = db.get(CardJob, job_id)
    if not job or job.user_id != user.id:
        raise AppError("media_not_found", "Media file was not found.", 404)
    safe_name = Path(file_name).name
    job_dir = (JOB_STORAGE_DIR / str(job_id)).resolve()
    path = (job_dir / safe_name).resolve()
    if job_dir not in path.parents or not path.is_file():
        raise AppError("media_not_found", "Media file was not found.", 404)
    return FileResponse(path)


@router.put("/drafts/{draft_id}", response_model=DraftResponse)
def update_draft(
    draft_id: int,
    payload: DraftUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> DraftResponse:
    draft = _get_owned_draft(db, user, draft_id)
    next_payload = [group.model_dump(mode="json", exclude_none=True) for group in payload.card_payload]
    draft.card_payload = _preserve_existing_media(draft.card_payload, next_payload)
    draft.vendor_code = payload.card_payload[0].variants[0].vendorCode if payload.card_payload else draft.vendor_code
    draft.subject_id = payload.card_payload[0].subjectID if payload.card_payload else draft.subject_id
    db.commit()
    db.refresh(draft)
    return _draft_response(draft)


@router.delete("/drafts/{draft_id}", status_code=204)
def delete_draft(
    draft_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    draft = _get_owned_draft(db, user, draft_id)
    db.delete(draft)
    db.commit()
    return Response(status_code=204)


@router.post("/drafts/{draft_id}/push", response_model=PushResponse)
async def push_draft(
    draft_id: int,
    payload: PushDraftRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
) -> PushResponse:
    draft = _get_owned_draft(db, user, draft_id)
    store = get_owned_store(db, user, draft.store_id)
    groups = payload.card_payload or [CardUploadGroup.model_validate(group) for group in draft.card_payload]
    
    quantity = sum(len(group.variants) for group in groups)
    _enforce_user_card_quota(user, quantity)
    
    wb_response = await CardFlowService(settings, db, user, store).push_new_cards(groups, payload.dry_run)
    request_payload = [group.model_dump(mode="json", exclude_none=True) for group in groups]
    draft.status = "dry_run" if payload.dry_run else "pushed"
    draft.card_payload = request_payload
    draft.wb_response = wb_response
    
    if not payload.dry_run:
        user.used_card_quota = user.used_card_quota + quantity
        
    db.commit()
    return PushResponse(dry_run=payload.dry_run, request_payload=request_payload, wb_response=wb_response)


@router.post("/stores/{store_id}/push-merge", response_model=PushResponse)
async def push_merge(
    store_id: int,
    payload: PushMergeRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
) -> PushResponse:
    store = get_owned_store(db, user, store_id)
    
    quantity = len(payload.cardsToAdd)
    _enforce_user_card_quota(user, quantity)
    
    variants = [variant.model_dump(mode="json", exclude_none=True) for variant in payload.cardsToAdd]
    wb_response = await CardFlowService(settings, db, user, store).push_merge_cards(
        payload.imtID,
        variants,
        payload.dry_run,
        payload.subjectID,
    )
    request_payload = {"imtID": payload.imtID, "cardsToAdd": variants}
    
    if not payload.dry_run:
        user.used_card_quota = user.used_card_quota + quantity
        db.commit()
        
    return PushResponse(dry_run=payload.dry_run, request_payload=request_payload, wb_response=wb_response)


@router.post("/stores/{store_id}/move-nm", response_model=PushResponse)
async def move_nm(
    store_id: int,
    payload: MoveNmRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
) -> PushResponse:
    store = get_owned_store(db, user, store_id)
    wb_response = await CardFlowService(settings, db, user, store).move_nm_cards(
        payload.nmIDs,
        payload.targetIMT,
        payload.dry_run,
    )
    request_payload = {"nmIDs": payload.nmIDs}
    if payload.targetIMT is not None:
        request_payload["targetIMT"] = payload.targetIMT
    return PushResponse(dry_run=payload.dry_run, request_payload=request_payload, wb_response=wb_response)


@router.post("/{nm_id}/media")
async def upload_media_links(
    store_id: int,
    nm_id: int,
    payload: MediaUploadByLinksRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
):
    store = get_owned_store(db, user, store_id)
    return await CardFlowService(settings, db, user, store).upload_media_links(nm_id, payload.links)


@router.post("/{nm_id}/media-file")
async def upload_media_file(
    store_id: int,
    nm_id: int,
    photo_number: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    store = get_owned_store(db, user, store_id)
    content = await _read_upload_limited(file, settings.max_media_upload_bytes, "media_file_too_large")
    return await CardFlowService(settings, db, user, store).upload_media_file(nm_id, photo_number, file.filename or "media", content)


def _parse_product_input(raw: str) -> ProductInput:
    try:
        return ProductInput.model_validate(json.loads(raw))
    except Exception as exc:
        raise AppError("invalid_product_input", "product_input_json must be valid ProductInput JSON.", 400) from exc


def _validate_image_upload(upload: UploadFile) -> None:
    if upload.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise AppError("invalid_image_type", "Images must be JPG, PNG, or WEBP.", 400)


async def _store_job_files(job_id: int, media_manifest: dict[str, Any], files: list[UploadFile], max_file_bytes: int) -> dict[str, Any]:
    job_dir = JOB_STORAGE_DIR / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    items = media_manifest.get("items") or []
    stored_items = []
    for index, upload in enumerate(files):
        manifest_item = items[index] if index < len(items) and isinstance(items[index], dict) else {}
        safe_name = Path(upload.filename or f"image-{index + 1}.jpg").name
        path = job_dir / f"{index + 1:03d}-{uuid.uuid4().hex}-{safe_name}"
        try:
            with path.open("wb") as target:
                await _copy_upload_limited(upload, target, max_file_bytes)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        stored_items.append(
            {
                "vendorCode": manifest_item.get("vendorCode"),
                "photoNumber": manifest_item.get("photoNumber", index + 1),
                "path": str(path),
                "fileName": path.name,
                "url": f"/cards/media/{job_id}/{path.name}",
            }
        )
    return {"items": stored_items}


async def _read_upload_limited(upload: UploadFile, max_bytes: int, code: str) -> bytes:
    chunks = []
    total = 0
    while True:
        chunk = await upload.read(CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise AppError(code, f"Uploaded file exceeds {max_bytes // (1024 * 1024)} MB.", 413)
        chunks.append(chunk)
    return b"".join(chunks)


async def _copy_upload_limited(upload: UploadFile, target, max_bytes: int) -> None:
    total = 0
    while True:
        chunk = await upload.read(CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise AppError("media_file_too_large", f"Uploaded file exceeds {max_bytes // (1024 * 1024)} MB.", 413)
        target.write(chunk)


def _attach_media_to_payload(job_id: int, card_payload: list[dict[str, Any]], media_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    payload = json.loads(json.dumps(card_payload))
    media_by_vendor: dict[str, list[dict[str, Any]]] = {}
    for item in media_manifest.get("items", []):
        vendor_code = str(item.get("vendorCode") or "").strip()
        if not vendor_code:
            continue
        media_by_vendor.setdefault(vendor_code, []).append(
            {
                "photoNumber": item.get("photoNumber"),
                "fileName": item.get("fileName"),
                "url": item.get("url"),
                "jobId": job_id,
            }
        )

    for group in payload:
        for variant in group.get("variants") or []:
            vendor_code = str(variant.get("vendorCode") or "").strip()
            items = sorted(media_by_vendor.get(vendor_code, []), key=lambda item: item.get("photoNumber") or 0)
            if not items:
                continue
            variant["media"] = {
                **(variant.get("media") or {}),
                "cover": items[0].get("url"),
                "local_files": items,
            }
    return payload


def _preserve_existing_media(existing_payload: Any, next_payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload = json.loads(json.dumps(next_payload))
    existing_variants_by_code: dict[str, dict[str, Any]] = {}
    existing_variants_by_index: dict[tuple[int, int], dict[str, Any]] = {}

    for group_index, group in enumerate(existing_payload or []):
        if not isinstance(group, dict):
            continue
        for variant_index, variant in enumerate(group.get("variants") or []):
            if not isinstance(variant, dict) or not variant.get("media"):
                continue
            vendor_code = str(variant.get("vendorCode") or "").strip().casefold()
            if vendor_code:
                existing_variants_by_code[vendor_code] = variant
            existing_variants_by_index[(group_index, variant_index)] = variant

    for group_index, group in enumerate(payload):
        for variant_index, variant in enumerate(group.get("variants") or []):
            if variant.get("media"):
                continue
            vendor_code = str(variant.get("vendorCode") or "").strip().casefold()
            existing_variant = existing_variants_by_code.get(vendor_code) or existing_variants_by_index.get((group_index, variant_index))
            if existing_variant and existing_variant.get("media"):
                variant["media"] = existing_variant["media"]
    return payload


def _job_response(job: CardJob) -> CardJobResponse:
    return CardJobResponse(
        id=job.id,
        status=job.status,
        step=job.step,
        draft_id=job.draft_id,
        mode=job.mode,
        result=job.result,
        error=job.error,
    )


def _get_owned_draft(db: Session, user: User, draft_id: int) -> CardDraft:
    draft = db.get(CardDraft, draft_id)
    if not draft or draft.user_id != user.id:
        raise AppError("draft_not_found", "Draft not found.", 404)
    return draft


def _draft_response(draft: CardDraft) -> DraftResponse:
    analysis = draft.analysis or {}
    if "recommendations" not in analysis:
        from app.services.studio_recommender import recommend_for_product_dict
        analysis_copy = dict(analysis)
        analysis_copy["recommendations"] = recommend_for_product_dict(analysis_copy)
        draft.analysis = analysis_copy
    return DraftResponse(
        id=draft.id,
        status=draft.status,
        subject_id=draft.subject_id,
        vendor_code=draft.vendor_code,
        analysis=draft.analysis,
        card_payload=draft.card_payload,
        wb_response=draft.wb_response,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )
