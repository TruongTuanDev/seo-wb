from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.billing import SubscriptionPlan
from app.services.admin_runtime import get_effective_ai_runtime_settings, list_public_model_templates


router = APIRouter(tags=["public"])


@router.get("/plans")
def list_plans(db: Session = Depends(get_db)) -> list[dict]:
    """Active subscription plans for display. Sourced from the editable DB rows
    so admin changes show up for users immediately."""
    rows = db.scalars(
        select(SubscriptionPlan).where(SubscriptionPlan.is_active.is_(True)).order_by(SubscriptionPlan.price.asc())
    ).all()
    return [
        {
            "value": plan.code,
            "label": plan.name,
            "priceRub": int(round(float(plan.price or 0))),
            "currency": plan.currency,
            "cards": int(plan.monthly_quota or 0),
            "images": int(plan.monthly_credits or 0),
            "maxImagesPerJob": int(plan.max_images_per_job or 0),
            "allowGptImage": bool(plan.allow_gpt_image),
            "allowLegacyVton": bool(plan.allow_legacy_vton),
            "priorityQueue": bool(plan.priority_queue),
        }
        for plan in rows
    ]


@router.get("/models")
def list_models(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    return list_public_model_templates(db, settings)


@router.get("/settings/ai/runtime")
def get_runtime_ai_settings(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    runtime = get_effective_ai_runtime_settings(db, settings)
    return {
        "default_image_model": runtime.default_image_model,
        "default_quantity": runtime.default_quantity,
        "max_retry": runtime.max_retry,
        "realism_threshold": runtime.realism_threshold,
        "validation_threshold": runtime.validation_threshold,
        "validation_failure_behavior": runtime.validation_failure_behavior,
        "allow_legacy_vton": runtime.allow_legacy_vton,
    }
