import shutil
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_store
from app.core.errors import AppError
from app.db.session import get_db
from app.models.shop_model import ShopModel
from app.models.user import User
from app.schemas.shop_model import ShopModelMetadata, ShopModelResponse
from app.services.shop_model_service import get_owned_shop_model


router = APIRouter(prefix="/shop-models", tags=["shop-models"])
MODEL_STORAGE_DIR = Path("storage/shop_models")
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_IMAGE_BYTES = 10 * 1024 * 1024


@router.get("", response_model=list[ShopModelResponse])
def list_shop_models(
    store_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[ShopModelResponse]:
    get_owned_store(db, user, store_id)
    models = db.scalars(
        select(ShopModel)
        .where(ShopModel.store_id == store_id)
        .order_by(ShopModel.created_at.desc())
    ).all()
    return [_response(model) for model in models]


@router.post("", response_model=ShopModelResponse, status_code=status.HTTP_201_CREATED)
async def create_shop_model(
    store_id: int = Form(...),
    metadata_json: str = Form(...),
    reference_image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ShopModelResponse:
    get_owned_store(db, user, store_id)
    metadata = ShopModelMetadata.model_validate_json(metadata_json)
    model_id = uuid4().hex
    target_dir = MODEL_STORAGE_DIR / str(store_id) / model_id
    reference_url = await _save_image(reference_image, target_dir, "reference", store_id, model_id)
    model = ShopModel(
        id=model_id,
        store_id=store_id,
        name=metadata.name,
        gender=metadata.gender,
        body_type=metadata.body_type,
        height_cm=metadata.height_cm,
        weight_kg=metadata.weight_kg,
        garment_type=metadata.garment_type,
        reference_image_url=reference_url,
        thumbnail_url=reference_url,
        poses={"front": reference_url},
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return _response(model)


@router.put("/{model_id}", response_model=ShopModelResponse)
async def update_shop_model(
    model_id: str,
    store_id: int = Form(...),
    metadata_json: str = Form(...),
    reference_image: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ShopModelResponse:
    get_owned_store(db, user, store_id)
    model = get_owned_shop_model(db, store_id, model_id)
    metadata = ShopModelMetadata.model_validate_json(metadata_json)
    model.name = metadata.name
    model.gender = metadata.gender
    model.body_type = metadata.body_type
    model.height_cm = metadata.height_cm
    model.weight_kg = metadata.weight_kg
    model.garment_type = metadata.garment_type
    if reference_image is not None:
        target_dir = MODEL_STORAGE_DIR / str(store_id) / model.id
        reference_url = await _save_image(reference_image, target_dir, "reference", store_id, model.id)
        model.reference_image_url = reference_url
        model.thumbnail_url = reference_url
        model.poses = {**(model.poses or {}), "front": reference_url}
    db.commit()
    db.refresh(model)
    return _response(model)


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shop_model(
    model_id: str,
    store_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    get_owned_store(db, user, store_id)
    model = get_owned_shop_model(db, store_id, model_id)
    target_dir = MODEL_STORAGE_DIR / str(store_id) / model.id
    db.delete(model)
    db.commit()
    if target_dir.exists():
        shutil.rmtree(target_dir)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _save_image(
    upload: UploadFile,
    target_dir: Path,
    stem: str,
    store_id: int,
    model_id: str,
) -> str:
    extension = ALLOWED_IMAGE_TYPES.get(upload.content_type or "")
    if extension is None:
        raise AppError("invalid_image_type", "Images must be JPG, PNG, or WEBP.", 400)
    content = await upload.read()
    if len(content) > MAX_IMAGE_BYTES:
        raise AppError("image_too_large", "Images must be 10MB or smaller.", 413)
    target_dir.mkdir(parents=True, exist_ok=True)
    for old_file in target_dir.glob(f"{stem}.*"):
        old_file.unlink(missing_ok=True)
    path = target_dir / f"{stem}{extension}"
    path.write_bytes(content)
    return f"/storage/shop_models/{store_id}/{model_id}/{path.name}"


def _response(model: ShopModel) -> ShopModelResponse:
    return ShopModelResponse.model_validate(model, from_attributes=True)
