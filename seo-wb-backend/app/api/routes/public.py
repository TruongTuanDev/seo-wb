from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.services.admin_runtime import get_effective_ai_runtime_settings, list_public_model_templates


router = APIRouter(tags=["public"])


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
