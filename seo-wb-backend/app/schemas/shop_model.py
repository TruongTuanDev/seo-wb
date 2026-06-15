from datetime import datetime

from pydantic import BaseModel, Field


class ShopModelMetadata(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    gender: str = Field(default="Unknown", max_length=32)
    body_type: str = Field(default="Unknown", max_length=64)
    height_cm: int | None = Field(default=None, ge=100, le=230)
    weight_kg: int | None = Field(default=None, ge=30, le=250)
    garment_type: str | None = Field(default=None, max_length=64)


class ShopModelResponse(BaseModel):
    id: str
    store_id: int
    name: str
    gender: str
    body_type: str
    height_cm: int | None
    weight_kg: int | None
    garment_type: str | None
    reference_image_url: str
    thumbnail_url: str | None
    poses: dict[str, str]
    created_at: datetime
    updated_at: datetime
