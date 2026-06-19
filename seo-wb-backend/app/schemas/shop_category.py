from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TnvedOption(BaseModel):
    code: str
    count: int = 0


class StoreCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_id: int
    subject_name: str | None = None
    tnved: str | None = None
    tnved_options: list[TnvedOption] = Field(default_factory=list)
    source: str
    locked: bool
    product_count: int
    last_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class StoreCategoryCreateRequest(BaseModel):
    subject_id: int = Field(gt=0)
    subject_name: str | None = Field(default=None, max_length=255)
    tnved: str | None = Field(default=None, max_length=20)


class StoreCategoryUpdateRequest(BaseModel):
    subject_name: str | None = Field(default=None, max_length=255)
    tnved: str | None = Field(default=None, max_length=20)
    locked: bool | None = None


class StoreCategorySyncResponse(BaseModel):
    synced_categories: int
    products_scanned: int
    categories: list[StoreCategoryResponse]


class StoreCategorySyncStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str = "idle"
    total_scanned: int = 0
    categories_found: int = 0
    last_error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
