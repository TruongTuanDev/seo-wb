import json
import uuid
from typing import Annotated, Any
from pathlib import Path
from datetime import datetime, timezone

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
    AcceptLowConfidenceAttributesRequest,
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
from app.services.card_generator import CardGenerator
from app.services.card_payload_enricher import CardPayloadEnricher
from app.services.product_copy_policy import build_copy_policy_context, build_seo_title, cleanup_description, cleanup_title, render_description, resolve_product_family
from app.services.rabbitmq_publisher import publish_sync_job
from app.services.admin_runtime import get_effective_ai_runtime_settings, list_public_model_templates
from app.services.billing_foundation import credit_cost_for_job, pending_credit_reservations, queue_name_for_plan
from app.services.product_image_generator import ProductImageGenerator
from app.services.redis_client import require_redis
from app.services.seo_content_validator import SeoContentValidator
from app.services.seo_keyword_planner import SeoKeywordPlanner
from app.services.usage_plans import get_usage_plan


router = APIRouter(prefix="/cards", tags=["cards"])
JOB_STORAGE_DIR = Path("storage/card_jobs")
DRAFT_REFERENCE_STORAGE_DIR = Path("storage/card_drafts")
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
        "seo_engine_enabled": runtime.seo_engine_enabled,
        "seo_min_score": runtime.seo_min_score,
        "description_min_chars": runtime.description_min_chars,
        "description_max_chars": runtime.description_max_chars,
        "seo_repair_max_attempts": runtime.seo_repair_max_attempts,
        "require_primary_keyword_in_title": runtime.require_primary_keyword_in_title,
        "warn_low_confidence_attributes": runtime.warn_low_confidence_attributes,
        "enable_russian_grammar_validation": runtime.enable_russian_grammar_validation,
        "enable_keyword_stuffing_detection": runtime.enable_keyword_stuffing_detection,
        "enable_subject_title_templates": runtime.enable_subject_title_templates,
        "include_gender_in_title": runtime.include_gender_in_title,
        "minimum_grammar_score": runtime.minimum_grammar_score,
        "minimum_marketplace_score": runtime.minimum_marketplace_score,
        "minimum_critical_attribute_score": runtime.minimum_critical_attribute_score,
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
    return 8


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


def _draft_reference_manifest(draft: CardDraft) -> dict[str, Any]:
    analysis = _draft_analysis(draft)
    manifest = analysis.get("reference_images")
    return manifest if isinstance(manifest, dict) else {}


def _draft_reference_dir(draft_id: int) -> Path:
    return DRAFT_REFERENCE_STORAGE_DIR / str(draft_id) / "references"


def _guess_reference_extension(file_name: str | None) -> str:
    suffix = Path(file_name or "").suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return suffix
    return ".jpg"


def _store_draft_reference_images(draft: CardDraft, image_bytes: list[bytes], file_names: list[str | None]) -> dict[str, Any]:
    if not image_bytes:
        return _draft_reference_manifest(draft)
    reference_dir = _draft_reference_dir(draft.id)
    reference_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {}

    front_ext = _guess_reference_extension(file_names[0] if file_names else None)
    front_name = f"front{front_ext}"
    (reference_dir / front_name).write_bytes(image_bytes[0])
    manifest["front"] = front_name

    if len(image_bytes) > 1:
        back_ext = _guess_reference_extension(file_names[1] if len(file_names) > 1 else None)
        back_name = f"back{back_ext}"
        (reference_dir / back_name).write_bytes(image_bytes[1])
        manifest["back"] = back_name

    return manifest


def _load_draft_reference_images(draft: CardDraft) -> tuple[bytes | None, bytes | None]:
    manifest = _draft_reference_manifest(draft)
    reference_dir = _draft_reference_dir(draft.id)

    def _read_ref(name: str) -> bytes | None:
        file_name = manifest.get(name)
        if not file_name:
            return None
        path = (reference_dir / str(file_name)).resolve()
        try:
            path.relative_to(reference_dir.resolve())
        except ValueError as exc:
            raise AppError("invalid_reference_image", "Stored reference image path is invalid.", 500) from exc
        if not path.exists():
            return None
        return path.read_bytes()

    return _read_ref("front"), _read_ref("back")


async def _resolve_product_reference_images(
    draft: CardDraft,
    settings: Settings,
    *,
    front_upload: UploadFile | None,
    back_upload: UploadFile | None,
    allow_missing_back: bool = True,
) -> tuple[bytes, bytes | None]:
    if front_upload is not None:
        _validate_image_upload(front_upload)
        front_bytes = await _read_upload_limited(front_upload, settings.max_upload_image_bytes, "image_too_large")
    else:
        front_bytes, _ = _load_draft_reference_images(draft)
        if front_bytes is None:
            raise AppError(
                "missing_front_reference",
                "Front product image is required. Upload it once in the first step or provide a new front image.",
                400,
            )

    if back_upload is not None:
        _validate_image_upload(back_upload)
        back_bytes = await _read_upload_limited(back_upload, settings.max_upload_image_bytes, "image_too_large")
    else:
        _, back_bytes = _load_draft_reference_images(draft)

    if not allow_missing_back and back_bytes is None:
        raise AppError(
            "missing_back_reference",
            "Back product image is required for this action. Upload it in the first step or provide a new back image.",
            400,
        )

    return front_bytes, back_bytes


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
    reference_manifest = _store_draft_reference_images(draft, image_bytes, [image.filename for image in images])
    if reference_manifest:
        analysis_copy = dict(draft.analysis or {})
        analysis_copy["reference_images"] = reference_manifest
        draft.analysis = analysis_copy
        db.commit()
        db.refresh(draft)
    card_payload = [CardUploadGroup.model_validate(group) for group in draft.card_payload]
    analysis = _draft_analysis(draft)
    return CardGenerateResponse(
        draft_id=draft.id,
        analysis=ImageAnalysis.model_validate(analysis),
        card_payload=card_payload,
        warnings=analysis.get("warnings", []),
        seo_keyword_plan=analysis.get("seo_keyword_plan"),
        seo_score=analysis.get("seo_score"),
        seo_issues=analysis.get("seo_issues", []),
        attribute_confidence=analysis.get("attribute_confidence"),
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
    front_image: UploadFile | None = File(default=None),
    back_image: UploadFile | None = File(default=None),
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

    for upload in [model_image]:
        if upload is not None:
            _validate_image_upload(upload)
    metadata["runtime_config"] = runtime_config
    metadata.setdefault("model", runtime_config["default_image_model"])
    front_bytes, back_bytes = await _resolve_product_reference_images(
        draft,
        settings,
        front_upload=front_image,
        back_upload=back_image,
    )
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
    productFrontImage: UploadFile | None = File(default=None),
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
        
    front_bytes, back_bytes = await _resolve_product_reference_images(
        draft,
        settings,
        front_upload=productFrontImage,
        back_upload=productBackImage,
    )
    
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
    front_image: UploadFile | None = File(default=None),
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
    front_bytes, back_bytes = await _resolve_product_reference_images(
        draft,
        settings,
        front_upload=front_image,
        back_upload=back_image,
    )

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
    if front_image is not None or back_image is not None:
        updated_bytes = [front_bytes]
        updated_names = [front_image.filename if front_image is not None else "front.jpg"]
        if back_bytes is not None:
            updated_bytes.append(back_bytes)
            updated_names.append(back_image.filename if back_image is not None else "back.jpg")
        analysis_copy["reference_images"] = _store_draft_reference_images(draft, updated_bytes, updated_names)
        draft.analysis = analysis_copy
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
    productFrontImage: UploadFile | None = File(default=None),
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

    front_bytes, back_bytes = await _resolve_product_reference_images(
        draft,
        settings,
        front_upload=productFrontImage,
        back_upload=productBackImage,
    )

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
    productFrontImage: UploadFile | None = File(default=None),
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

    if modelImage:
        _validate_image_upload(modelImage)

    front_bytes, back_bytes = await _resolve_product_reference_images(
        draft,
        settings,
        front_upload=productFrontImage,
        back_upload=productBackImage,
    )

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
        seo_keyword_plan=draft.analysis.get("seo_keyword_plan") if isinstance(draft.analysis, dict) else None,
        seo_score=draft.analysis.get("seo_score") if isinstance(draft.analysis, dict) else None,
        seo_issues=draft.analysis.get("seo_issues", []) if isinstance(draft.analysis, dict) else [],
        attribute_confidence=draft.analysis.get("attribute_confidence") if isinstance(draft.analysis, dict) else None,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def _draft_payload_copy(draft: CardDraft) -> list[dict[str, Any]]:
    payload = draft.card_payload if isinstance(draft.card_payload, list) else []
    return json.loads(json.dumps(payload))


def _draft_product_input(draft: CardDraft) -> ProductInput:
    analysis = _draft_analysis(draft)
    raw = analysis.get("product_input") if isinstance(analysis, dict) else None
    if isinstance(raw, dict):
        try:
            return ProductInput.model_validate(raw)
        except Exception:
            return ProductInput()
    return ProductInput()


def _draft_image_analysis_model(draft: CardDraft) -> ImageAnalysis:
    analysis = _draft_analysis(draft)
    return ImageAnalysis.model_validate(analysis)


def _draft_subject_context(draft: CardDraft, analysis_model: ImageAnalysis, product_input: ProductInput) -> dict[str, Any]:
    payload = draft.card_payload if isinstance(draft.card_payload, list) and draft.card_payload else []
    subject_id = draft.subject_id or (payload[0].get("subjectID") if payload and isinstance(payload[0], dict) else None) or 0
    subject_name = product_input.category or analysis_model.category or "Товар"
    if payload and isinstance(payload[0], dict):
        first_title = (((payload[0].get("variants") or [None])[0]) or {}).get("title") if payload[0].get("variants") else None
        if first_title and len(str(first_title).split()) <= 8:
            subject_name = str(first_title).split()[0]
    return {"subjectID": int(subject_id), "subjectName": str(subject_name)}


async def _draft_charcs(
    db: Session,
    settings: Settings,
    user: User,
    draft: CardDraft,
    subject_id: int,
) -> list[dict[str, Any]]:
    store = get_owned_store(db, user, draft.store_id)
    flow = CardFlowService(settings, db, user, store)
    return await flow._wb.get_subject_charcs(subject_id, locale="ru")


async def _recompute_draft_seo(
    draft: CardDraft,
    *,
    db: Session,
    settings: Settings,
    user: User,
    rewrite_copy: bool,
    improve_only: bool,
) -> DraftResponse:
    runtime = get_effective_ai_runtime_settings(db, settings)
    if not runtime.seo_engine_enabled:
        raise AppError("seo_engine_disabled", "SEO engine is disabled by admin settings.", 403)

    product_input = _draft_product_input(draft)
    analysis_model = _draft_image_analysis_model(draft)
    subject = _draft_subject_context(draft, analysis_model, product_input)
    charcs = await _draft_charcs(db, settings, user, draft, int(subject["subjectID"]))
    analysis = _draft_analysis(draft)
    payload = _draft_payload_copy(draft)
    attribute_confidence = analysis.get("attribute_confidence") if isinstance(analysis.get("attribute_confidence"), dict) else None
    if not attribute_confidence:
        attribute_confidence = CardPayloadEnricher(charcs).build_attribute_confidence(
            subject_id=int(subject["subjectID"]),
            user_input=product_input,
            analysis=analysis_model,
        )
    seo_keyword_plan = analysis.get("seo_keyword_plan") if isinstance(analysis.get("seo_keyword_plan"), dict) else None
    if not seo_keyword_plan:
        seo_keyword_plan = SeoKeywordPlanner.build_plan(
            category=product_input.category or analysis_model.category,
            subject_name=subject.get("subjectName"),
            brand=product_input.brand,
            gender=product_input.gender or analysis_model.gender,
            analysis=analysis_model,
            user_input=product_input,
            confirmed_attributes=attribute_confidence.get("confirmed_attributes"),
            wb_characteristics=charcs,
            product_family_policy=build_copy_policy_context(subject, analysis_model, product_input),
        )

    current_score = analysis.get("seo_score") if isinstance(analysis.get("seo_score"), dict) else {}
    should_rewrite = rewrite_copy or not improve_only or int(current_score.get("seo_score") or 0) < runtime.seo_min_score

    if should_rewrite:
        for group in payload:
            for variant in group.get("variants") or []:
                title_payload = build_seo_title(
                    subject.get("subjectName"),
                    analysis_model.gender or product_input.gender,
                    CardGenerator._title_attributes(product_input, analysis_model, subject, seo_keyword_plan, attribute_confidence),
                    seo_keyword_plan,
                    brand=(product_input.brand or "").strip() or None,
                    include_gender_in_title=runtime.include_gender_in_title,
                )
                variant["title"] = cleanup_title(
                    str(title_payload.get("title") or variant.get("title") or ""),
                    str(subject.get("subjectName") or "Товар"),
                    analysis_model,
                    product_input,
                )
                policy = resolve_product_family(subject, analysis_model, product_input)
                regenerated = render_description(policy, title=variant["title"], analysis=analysis_model, user_input=product_input)
                variant["description"] = cleanup_description(
                    regenerated if rewrite_copy or not str(variant.get("description") or "").strip() else str(variant.get("description") or ""),
                    title=variant["title"],
                    subject=subject,
                    analysis=analysis_model,
                    user_input=product_input,
                )

    issues: list[str] = []
    suggestions: list[str] = []
    scorecards: list[dict[str, Any]] = []
    for group in payload:
        for variant in group.get("variants") or []:
            validator_result = SeoContentValidator.validate(
                title=str(variant.get("title") or ""),
                description=str(variant.get("description") or ""),
                seo_keyword_plan=seo_keyword_plan,
                confirmed_attributes=attribute_confidence.get("confirmed_attributes"),
                inferred_attributes=attribute_confidence.get("inferred_attributes"),
                min_chars=runtime.description_min_chars,
                max_chars=runtime.description_max_chars,
                auto_fix=True,
            )
            variant["description"] = validator_result.get("fixed_description") or variant.get("description")
            issues.extend(validator_result.get("issues", []))
            suggestions.extend(validator_result.get("suggestions", []))
            scorecard = SeoContentValidator.build_scorecard(
                    title=str(variant.get("title") or ""),
                    description=str(variant.get("description") or ""),
                    seo_keyword_plan=seo_keyword_plan,
                    validator_result=validator_result,
                    confirmed_attributes=attribute_confidence.get("confirmed_attributes"),
                    inferred_attributes=attribute_confidence.get("inferred_attributes"),
                    subject_name=subject.get("subjectName"),
                    wb_characteristics=charcs,
                    low_confidence_attributes=attribute_confidence.get("low_confidence_attributes"),
                )
            scorecards.append(scorecard)
            issues.extend(scorecard.get("issues", []))
            suggestions.extend(scorecard.get("suggestions", []))
    aggregate = {
        "seo_score": int(round(sum(item.get("seo_score", 0) for item in scorecards) / max(1, len(scorecards)))),
        "title_score": int(round(sum(item.get("title_score", 0) for item in scorecards) / max(1, len(scorecards)))),
        "description_score": int(round(sum(item.get("description_score", 0) for item in scorecards) / max(1, len(scorecards)))),
        "attributes_score": int(round(sum(item.get("attributes_score", 0) for item in scorecards) / max(1, len(scorecards)))),
        "keyword_coverage_score": int(round(sum(item.get("keyword_coverage_score", 0) for item in scorecards) / max(1, len(scorecards)))),
        "grammar_score": int(round(sum(item.get("grammar_score", 0) for item in scorecards) / max(1, len(scorecards)))),
        "marketplace_score": int(round(sum(item.get("marketplace_score", 0) for item in scorecards) / max(1, len(scorecards)))),
        "subject_rule_score": int(round(sum(item.get("subject_rule_score", 0) for item in scorecards) / max(1, len(scorecards)))),
        "critical_attribute_score": int(round(sum(item.get("critical_attribute_score", 0) for item in scorecards) / max(1, len(scorecards)))),
        "semantic_consistency_score": int(round(sum(item.get("semantic_consistency_score", 0) for item in scorecards) / max(1, len(scorecards)))),
        "issues": list(dict.fromkeys(issues))[:10],
        "suggestions": list(dict.fromkeys(suggestions))[:10],
        "blocking_issues": list(dict.fromkeys(
            issue
            for item in scorecards
            for issue in item.get("blocking_issues", [])
        )),
        "status": "poor",
        "variants": scorecards,
    }
    score = aggregate["seo_score"]
    aggregate["status"] = (
        "needs_review"
        if aggregate["blocking_issues"]
        else "excellent" if score >= 85 else "good" if score >= 70 else "needs_review" if score >= 50 else "poor"
    )

    next_analysis = dict(analysis)
    next_analysis["product_input"] = product_input.model_dump(mode="json", exclude_none=True)
    next_analysis["attribute_confidence"] = attribute_confidence
    next_analysis["seo_keyword_plan"] = seo_keyword_plan
    next_analysis["seo_score"] = aggregate
    next_analysis["seo_issues"] = aggregate["issues"]
    draft.analysis = next_analysis
    draft.card_payload = _preserve_existing_media(draft.card_payload, payload)
    db.commit()
    db.refresh(draft)
    return _draft_response(draft)


@router.post("/drafts/{draft_id}/seo/improve", response_model=DraftResponse)
async def improve_draft_seo(
    draft_id: int,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
) -> DraftResponse:
    draft = _get_owned_draft(db, user, draft_id)
    return await _recompute_draft_seo(
        draft,
        db=db,
        settings=settings,
        user=user,
        rewrite_copy=False,
        improve_only=True,
    )


@router.post("/drafts/{draft_id}/seo/regenerate-copy", response_model=DraftResponse)
async def regenerate_draft_seo_copy(
    draft_id: int,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
) -> DraftResponse:
    draft = _get_owned_draft(db, user, draft_id)
    return await _recompute_draft_seo(
        draft,
        db=db,
        settings=settings,
        user=user,
        rewrite_copy=True,
        improve_only=False,
    )


@router.post("/drafts/{draft_id}/seo/accept-low-confidence-attributes", response_model=DraftResponse)
async def accept_low_confidence_attributes(
    draft_id: int,
    payload: AcceptLowConfidenceAttributesRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
) -> DraftResponse:
    draft = _get_owned_draft(db, user, draft_id)
    runtime = get_effective_ai_runtime_settings(db, settings)
    if not runtime.seo_engine_enabled:
        raise AppError("seo_engine_disabled", "SEO engine is disabled by admin settings.", 403)

    analysis = dict(_draft_analysis(draft))
    attribute_confidence = analysis.get("attribute_confidence")
    if not isinstance(attribute_confidence, dict):
        raise AppError("attribute_confidence_missing", "Draft does not have attribute confidence data yet.", 409)
    confirmed_attributes = dict(attribute_confidence.get("confirmed_attributes") or {})
    inferred_attributes = dict(attribute_confidence.get("inferred_attributes") or {})
    low_confidence_attributes = list(attribute_confidence.get("low_confidence_attributes") or [])
    selected_keys = [str(key).strip() for key in payload.attribute_keys if str(key).strip()]

    moved_keys: list[str] = []
    for key in selected_keys:
        if key in low_confidence_attributes and key in inferred_attributes:
            confirmed_attributes[key] = inferred_attributes[key]
            inferred_attributes.pop(key, None)
            moved_keys.append(key)
    attribute_confidence["confirmed_attributes"] = confirmed_attributes
    attribute_confidence["inferred_attributes"] = inferred_attributes
    attribute_confidence["low_confidence_attributes"] = [key for key in low_confidence_attributes if key not in moved_keys]

    product_input = _draft_product_input(draft)
    analysis_model = _draft_image_analysis_model(draft)
    subject = _draft_subject_context(draft, analysis_model, product_input)
    charcs = await _draft_charcs(db, settings, user, draft, int(subject["subjectID"]))
    enricher = CardPayloadEnricher(charcs)
    next_payload = _draft_payload_copy(draft)
    alias_map = {
        "composition": "composition",
        "material": "composition",
        "color": "color",
        "gender": "gender",
        "season": "season",
        "fit": "fit",
        "pattern": "pattern",
        "purpose": "purpose",
        "lining": "lining",
        "texture": "texture",
    }
    for group in next_payload:
        for variant in group.get("variants") or []:
            for key in moved_keys:
                alias = alias_map.get(key, key)
                value = confirmed_attributes.get(alias) or confirmed_attributes.get(key)
                if value:
                    enricher._upsert_by_alias(variant, alias, value, overwrite=True)
            enricher._conform_characteristics(variant)

    accepted_history = list(analysis.get("accepted_low_confidence_attributes") or [])
    accepted_history.extend([key for key in moved_keys if key not in accepted_history])
    analysis["accepted_low_confidence_attributes"] = accepted_history
    analysis["accepted_at"] = datetime.now(timezone.utc).isoformat()
    analysis["attribute_confidence"] = attribute_confidence
    draft.analysis = analysis
    draft.card_payload = _preserve_existing_media(draft.card_payload, next_payload)
    db.commit()
    db.refresh(draft)
    return await _recompute_draft_seo(
        draft,
        db=db,
        settings=settings,
        user=user,
        rewrite_copy=False,
        improve_only=False,
    )
