from datetime import datetime

from pydantic import BaseModel, Field


class StoreCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    wb_api_key: str = Field(min_length=20, max_length=4096)


class StoreUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    wb_api_key: str | None = Field(default=None, min_length=20, max_length=4096)


class StoreResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime
