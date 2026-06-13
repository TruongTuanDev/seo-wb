from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.admin import AdminAiSettings, GeneratedImageJob, ModelTemplate
from app.models.user import User


@dataclass
class EffectiveAiRuntimeSettings:
    default_image_model: str
    fallback_image_model: str | None
    gemini_model: str
    max_retry: int
    default_quantity: int
    realism_threshold: int
    validation_threshold: int
    validation_failure_behavior: str
    allow_legacy_vton: bool
    seo_engine_enabled: bool
    seo_min_score: int
    description_min_chars: int
    description_max_chars: int
    seo_repair_max_attempts: int
    require_primary_keyword_in_title: bool
    warn_low_confidence_attributes: bool


def get_or_create_admin_ai_settings(db: Session) -> AdminAiSettings:
    row = db.get(AdminAiSettings, 1)
    if row:
        return row
    row = AdminAiSettings(id=1)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_effective_ai_runtime_settings(db: Session, settings: Settings) -> EffectiveAiRuntimeSettings:
    row = get_or_create_admin_ai_settings(db)
    return EffectiveAiRuntimeSettings(
        default_image_model=row.default_image_model or settings.openai_image_model or "gpt-image-2",
        fallback_image_model=row.fallback_image_model,
        gemini_model=row.gemini_model or settings.gemini_model,
        max_retry=max(0, row.max_retry),
        default_quantity=max(1, row.default_quantity),
        realism_threshold=max(0, min(100, row.realism_threshold)),
        validation_threshold=max(0, min(100, row.validation_threshold)),
        validation_failure_behavior=row.validation_failure_behavior if row.validation_failure_behavior in {"block", "warn"} else "warn",
        allow_legacy_vton=bool(row.allow_legacy_vton),
        seo_engine_enabled=bool(row.seo_engine_enabled),
        seo_min_score=max(0, min(100, row.seo_min_score)),
        description_min_chars=max(200, row.description_min_chars),
        description_max_chars=max(max(200, row.description_min_chars), row.description_max_chars),
        seo_repair_max_attempts=max(0, row.seo_repair_max_attempts),
        require_primary_keyword_in_title=bool(row.require_primary_keyword_in_title),
        warn_low_confidence_attributes=bool(row.warn_low_confidence_attributes),
    )


def list_public_model_templates(db: Session, settings: Settings, garment_type: str | None = None) -> list[dict]:
    query = select(ModelTemplate).where(
        ModelTemplate.status == "active",
        ModelTemplate.quality_status == "approved",
        ModelTemplate.deleted_at.is_(None),
    )
    if garment_type:
        from sqlalchemy import or_

        query = query.where(
            or_(
                ModelTemplate.garment_type == garment_type,
                ModelTemplate.garment_type == "full_body",
                ModelTemplate.garment_type.is_(None),
            )
        )
    rows = db.scalars(query.order_by(ModelTemplate.created_at.desc())).all()
    if rows:
        return [_public_model_item(row) for row in rows]

    if settings.app_env.lower() in {"local", "development", "dev", "test"}:
        from app.services.virtual_try_on import BUILTIN_MODELS

        items = [_public_builtin_model_item(item) for item in BUILTIN_MODELS]
        if garment_type:
            # Built-in models can default to full_body or match the requested garment_type
            items = [item for item in items if item.get("garmentType") == garment_type or item.get("garmentType") == "full_body"]
        return items
    return []


def _public_model_item(model: ModelTemplate) -> dict:
    poses = model.poses or {}
    front_image_url = model.reference_image_url or poses.get("front") or model.thumbnail_url or ""
    available_poses = [pose for pose, url in poses.items() if url] or ["front"]
    gender = model.gender.strip().capitalize() if model.gender else "Unknown"
    body_type = model.body_type.strip().capitalize() if model.body_type else "Unknown"
    description_parts = []
    if model.height_cm:
        description_parts.append(f"Height: {model.height_cm}cm")
    if model.weight_kg:
        description_parts.append(f"Weight: {model.weight_kg}kg")
    return {
        "id": model.id,
        "name": model.name,
        "gender": gender,
        "bodyType": body_type,
        "height": model.height_cm or 0,
        "weight": model.weight_kg or 0,
        "frontImageUrl": front_image_url,
        "imageUrl": front_image_url,
        "label": f"{gender} - {body_type}",
        "description": " - ".join(description_parts) if description_parts else model.name,
        "availablePoses": available_poses,
        "isAiGenerated": bool(model.is_ai_generated),
        "garmentType": model.garment_type or "full_body",
    }


def _public_builtin_model_item(model: dict) -> dict:
    front_image_url = model.get("frontImageUrl") or model.get("front_template") or model.get("imageUrl") or ""
    return {
        "id": model.get("id"),
        "name": model.get("name"),
        "gender": model.get("gender", "Unknown"),
        "bodyType": model.get("bodyType", "Unknown"),
        "height": model.get("height", 0),
        "weight": model.get("weight", 0),
        "frontImageUrl": front_image_url,
        "imageUrl": model.get("imageUrl") or front_image_url,
        "label": model.get("label") or model.get("name", ""),
        "description": model.get("description") or model.get("name", ""),
        "availablePoses": model.get("availablePoses") or ["front"],
        "isAiGenerated": bool(model.get("isAiGenerated")),
        "garmentType": model.get("garmentType") or "full_body",
    }


def soft_delete_user(user: User) -> None:
    user.deleted_at = datetime.now(timezone.utc)
    user.status = "suspended"


def soft_delete_model(model: ModelTemplate) -> None:
    model.deleted_at = datetime.now(timezone.utc)
    model.status = "inactive"


def soft_delete_job(job: GeneratedImageJob) -> None:
    job.deleted_at = datetime.now(timezone.utc)


def ensure_builtin_model_seeds(db: Session) -> None:
    from app.services.virtual_try_on import BUILTIN_MODELS

    changed = False
    for item in BUILTIN_MODELS:
        m_id = item["id"]
        existing = db.get(ModelTemplate, m_id)
        if existing is None:
            db.add(
                ModelTemplate(
                    id=m_id,
                    name=item["name"],
                    gender=item["gender"].lower(),
                    body_type=item["bodyType"].lower(),
                    height_cm=item.get("height"),
                    weight_kg=item.get("weight"),
                    garment_type=item.get("garmentType", "full_body"),
                    is_ai_generated=False,
                    status="active",
                    quality_status="approved",
                    reference_image_url=item["frontImageUrl"],
                    thumbnail_url=item["imageUrl"],
                    poses={"front": item["frontImageUrl"]},
                )
            )
            changed = True
    if changed:
        db.commit()
