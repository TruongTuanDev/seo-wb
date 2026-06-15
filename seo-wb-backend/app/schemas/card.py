from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ProductInput(BaseModel):
    category: str | None = Field(default=None, max_length=160)
    subject_id: int | None = None
    brand: str | None = Field(default=None, max_length=120)
    vendor_code: str | None = Field(default=None, max_length=180)
    color: str | None = Field(default=None, max_length=120)
    gender: str | None = Field(default=None, max_length=80)
    sizes: list[str] = Field(default_factory=list)
    dimensions: dict[str, Any] = Field(default_factory=dict)
    note: str | None = Field(default=None, max_length=3000)
    attributes: dict[str, Any] = Field(default_factory=dict)


class ImageAnalysis(BaseModel):
    category: str | None = None
    product_name: str | None = None
    material: str | None = None
    color: str | None = None
    gender: str | None = None
    season: str | None = None
    fit_type: str | None = None
    features: list[str] = Field(default_factory=list)
    attributes: dict[str, str] = Field(default_factory=dict)
    confidence: float = 0
    warnings: list[str] = Field(default_factory=list)
    source_image_count: int = 0
    variant_colors: list[dict[str, str]] = Field(default_factory=list)
    sizes: list[dict[str, str]] = Field(default_factory=list)
    package: dict[str, Any] = Field(default_factory=dict)
    vendor_code_base: str | None = Field(default=None, max_length=180)
    recommendations: dict[str, Any] = Field(default_factory=dict)
    garment_json: dict[str, Any] = Field(default_factory=dict)


class Dimensions(BaseModel):
    length: int | float = Field(gt=0)
    width: int | float = Field(gt=0)
    height: int | float = Field(gt=0)
    weightBrutto: int | float = Field(gt=0)


class Characteristic(BaseModel):
    id: int
    value: Any


class SizeItem(BaseModel):
    techSize: str | None = None
    wbSize: str | None = None
    price: int | None = None
    skus: list[str] = Field(default_factory=list)


class Variant(BaseModel):
    vendorCode: str = Field(min_length=1, max_length=180)
    kizMarked: bool | None = None
    title: str = Field(min_length=10, max_length=60)
    description: str = Field(min_length=100, max_length=5000)
    brand: str = Field(min_length=1, max_length=120)
    dimensions: Dimensions
    characteristics: list[Characteristic] = Field(min_length=1)
    sizes: list[SizeItem] = Field(min_length=1)


class CardUploadGroup(BaseModel):
    subjectID: int
    variants: list[Variant] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_unique_vendor_codes(self) -> "CardUploadGroup":
        vendor_codes = [variant.vendorCode.strip().casefold() for variant in self.variants]
        if len(vendor_codes) != len(set(vendor_codes)):
            raise ValueError("Variant vendor codes must be unique inside one card group.")
        return self


class CardGenerateResponse(BaseModel):
    draft_id: int
    analysis: ImageAnalysis
    card_payload: list[CardUploadGroup]
    warnings: list[str] = Field(default_factory=list)


class DraftResponse(BaseModel):
    id: int
    status: str
    subject_id: int | None = None
    vendor_code: str | None = None
    analysis: dict[str, Any]
    card_payload: Any
    wb_response: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class DraftListResponse(BaseModel):
    items: list[DraftResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0
    has_more: bool = False


class CardJobResponse(BaseModel):
    id: int
    status: str
    step: str
    draft_id: int | None = None
    mode: str
    result: dict[str, Any] | None = None
    error: str | None = None


class DraftUpdateRequest(BaseModel):
    card_payload: list[CardUploadGroup]


class ImportWbCardRequest(BaseModel):
    nm_id: int = Field(gt=0)


class PushDraftRequest(BaseModel):
    card_payload: list[CardUploadGroup] | None = None
    dry_run: bool = False


class PushMergeRequest(BaseModel):
    imtID: int
    subjectID: int | None = None
    cardsToAdd: list[Variant] = Field(min_length=1, max_length=29)
    dry_run: bool = False

    @model_validator(mode="after")
    def validate_unique_vendor_codes(self) -> "PushMergeRequest":
        vendor_codes = [variant.vendorCode.strip().casefold() for variant in self.cardsToAdd]
        if len(vendor_codes) != len(set(vendor_codes)):
            raise ValueError("Variant vendor codes must be unique when adding to an existing card.")
        return self


class MoveNmRequest(BaseModel):
    nmIDs: list[int] = Field(min_length=1, max_length=30)
    targetIMT: int | None = None
    dry_run: bool = False


class CardListRequest(BaseModel):
    textSearch: str | None = None
    vendorCode: str | None = None
    nmID: int | None = None
    withPhoto: int = -1
    limit: int = Field(default=100, ge=1, le=100)


class TnvedSuggestionRequest(BaseModel):
    subjectID: int
    search: str | None = None


class PayloadTnvedEnrichRequest(BaseModel):
    subjectID: int
    payload: Any
    search: str | None = None


class PushResponse(BaseModel):
    dry_run: bool
    request_payload: Any
    wb_response: dict[str, Any] | None = None


class MediaUploadByLinksRequest(BaseModel):
    links: list[str] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_links(self) -> "MediaUploadByLinksRequest":
        for link in self.links:
            if not link.startswith(("http://", "https://")):
                raise ValueError("Media links must be direct http(s) URLs")
        return self


class ImageGenerationJobResponse(BaseModel):
    id: str
    status: str
    step: str
    progress: int = 0
    total: int = 0
    variant_id: str | None = None
    images: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
    job_type: str | None = None
    failed_validations: list[dict[str, Any]] = Field(default_factory=list)
    quality_report: dict[str, Any] | None = None
    seller_warning: str | None = None
    final_validation_status: str | None = None
    validation_summary: dict[str, Any] | None = None
    quality_check_enabled: bool | None = None


class ImageGenerationImageActionRequest(BaseModel):
    action: str = Field(pattern="^(use_anyway|hide|approve|reject)$")
