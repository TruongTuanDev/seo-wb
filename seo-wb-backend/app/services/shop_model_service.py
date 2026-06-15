from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.admin import ModelTemplate
from app.models.shop_model import ShopModel


def get_owned_shop_model(db: Session, store_id: int, model_id: str) -> ShopModel:
    model = db.scalar(
        select(ShopModel).where(
            ShopModel.id == model_id,
            ShopModel.store_id == store_id,
        )
    )
    if model is None:
        raise AppError("shop_model_not_found", "Model was not found in this shop.", 404)
    return model


def resolve_model_reference(
    db: Session,
    *,
    store_id: int,
    model_id: str,
) -> tuple[Path, str, str, str, str]:
    shop_model = db.scalar(
        select(ShopModel).where(
            ShopModel.id == model_id,
            ShopModel.store_id == store_id,
        )
    )
    if shop_model is not None:
        path = _storage_url_to_path(shop_model.reference_image_url)
        if not path.exists():
            raise AppError("shop_model_image_missing", "The selected shop model image is missing.", 409)
        return path, shop_model.reference_image_url, shop_model.gender, shop_model.body_type, "shop"

    system_model = db.get(ModelTemplate, model_id)
    if (
        system_model is None
        or system_model.status != "active"
        or system_model.quality_status != "approved"
        or system_model.deleted_at is not None
        or not system_model.reference_image_url
    ):
        raise AppError("model_not_available", "The selected model is not available.", 404)
    path = _system_model_path(system_model.id, system_model.reference_image_url)
    if not path.exists():
        raise AppError("model_image_missing", "The selected system model image is missing.", 409)
    return path, system_model.reference_image_url, system_model.gender, system_model.body_type, "system"


def _storage_url_to_path(url: str) -> Path:
    prefix = "/storage/"
    if not url.startswith(prefix):
        raise AppError("invalid_model_image", "Model reference must be stored by this system.", 409)
    path = Path("storage") / url.removeprefix(prefix)
    resolved_storage = Path("storage").resolve()
    resolved_path = path.resolve()
    if resolved_storage not in resolved_path.parents:
        raise AppError("invalid_model_image", "Invalid model image path.", 409)
    return resolved_path


def _system_model_path(model_id: str, url: str) -> Path:
    if url.startswith("/storage/"):
        return _storage_url_to_path(url)
    clean_ids = {model_id, model_id.replace("_", "")}
    for clean_id in clean_ids:
        model_dir = Path("storage/models") / clean_id
        if model_dir.is_dir():
            for path in model_dir.iterdir():
                if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                    if path.stem.lower().startswith(("front", "reference")):
                        return path.resolve()
        for suffix in (".jpg", ".jpeg", ".png", ".webp"):
            path = Path("storage/models") / f"{clean_id}{suffix}"
            if path.exists():
                return path.resolve()
    raise AppError("model_image_missing", "The selected system model image is missing.", 409)
