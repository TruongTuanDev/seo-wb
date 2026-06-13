from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.schemas.auth import LoginRequest, UserResponse


class AdminLoginRequest(LoginRequest):
    pass


class AdminUserCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = "user"
    status: str = "active"
    plan_type: str = "free"
    monthly_quota: int | None = None
    monthly_card_quota: int | None = None
    monthly_cost_limit: float | None = None


class AdminUserUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: str | None = None
    status: str | None = None
    plan_type: str | None = None
    monthly_quota: int | None = None
    used_quota: int | None = None
    monthly_card_quota: int | None = None
    used_card_quota: int | None = None
    monthly_cost_limit: float | None = None
    used_cost: float | None = None
    credit_balance: int | None = None
    credits_used: int | None = None
    credits_granted: int | None = None


class AdminUserResponse(UserResponse):
    max_images_per_job: int
    allow_legacy_vton: bool
    allow_gpt_image: bool
    priority_queue: bool
    monthly_quota: int
    used_quota: int
    monthly_card_quota: int
    used_card_quota: int
    monthly_cost_limit: float | None
    used_cost: float
    credit_balance: int
    credits_used: int
    credits_granted: int
    quota_reset_at: datetime | None
    last_quota_reset_at: datetime | None
    close_to_quota_limit: bool
    close_to_cost_limit: bool
    created_at: datetime
    updated_at: datetime


class AdminDashboardResponse(BaseModel):
    total_users: int
    total_models: int
    total_generated_images: int
    total_failed_jobs: int
    total_api_cost_estimate: float
    images_generated_today: int
    validation_failed_count: int
    active_users: int
    users_over_quota_80: int
    users_over_cost_80: int
    users_over_quota: int
    users_over_cost: int
    top_usage_users: list["AdminDashboardUserMetric"]
    top_cost_users: list["AdminDashboardUserMetric"]


class AdminDashboardUserMetric(BaseModel):
    user_id: int
    name: str
    email: str
    plan_type: str
    used_quota: int
    monthly_quota: int
    quota_percent: float
    used_cost: float
    monthly_cost_limit: float | None
    cost_percent: float | None


class ModelTemplateResponse(BaseModel):
    id: str
    name: str
    gender: str
    body_type: str
    height_cm: int | None
    weight_kg: int | None
    garment_type: str | None = None
    is_ai_generated: bool
    status: str
    quality_status: str
    thumbnail_url: str | None
    reference_image_url: str | None
    poses: dict[str, str]
    created_at: datetime
    updated_at: datetime


class ModelTemplateUpsertRequest(BaseModel):
    id: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=120)
    gender: str = Field(min_length=1, max_length=32)
    body_type: str = Field(min_length=1, max_length=64)
    height_cm: int | None = None
    weight_kg: int | None = None
    garment_type: str | None = None
    is_ai_generated: bool = False
    status: str = "active"
    quality_status: str = "draft"
    poses: dict[str, str] = Field(default_factory=dict)


class GeneratedImageJobResponse(BaseModel):
    id: str
    user_id: int
    store_id: int | None
    draft_id: int | None
    job_type: str
    status: str
    step: str
    model_id: str | None
    ai_model: str | None
    style: str | None
    quantity: int
    garment_json: dict[str, Any]
    validation_result: dict[str, Any]
    prompt: str | None
    retry_count: int
    error_message: str | None
    metadata_json: dict[str, Any]
    images: list[dict[str, Any]]
    estimated_cost: float
    approved: bool | None
    created_at: datetime
    completed_at: datetime | None
    updated_at: datetime


class GeneratedImageJobDetailResponse(GeneratedImageJobResponse):
    input_images: list[dict[str, Any]]
    selected_model_image: dict[str, Any] | None
    usage_records: list["UsageRecordResponse"]


class AdminAiSettingsResponse(BaseModel):
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
    openai_configured: bool
    fal_configured: bool
    gemini_configured: bool


class AdminAiSettingsUpdateRequest(BaseModel):
    default_image_model: str
    fallback_image_model: str | None = None
    gemini_model: str
    max_retry: int = Field(ge=0, le=10)
    default_quantity: int = Field(ge=1, le=10)
    realism_threshold: int = Field(ge=0, le=100)
    validation_threshold: int = Field(ge=0, le=100)
    validation_failure_behavior: str = Field(default="warn", pattern="^(block|warn)$")
    allow_legacy_vton: bool
    seo_engine_enabled: bool = True
    seo_min_score: int = Field(default=70, ge=0, le=100)
    description_min_chars: int = Field(default=600, ge=200, le=2000)
    description_max_chars: int = Field(default=900, ge=200, le=3000)
    seo_repair_max_attempts: int = Field(default=1, ge=0, le=3)
    require_primary_keyword_in_title: bool = True
    warn_low_confidence_attributes: bool = True


class UsageRecordResponse(BaseModel):
    id: str
    user_id: int
    job_id: str | None
    provider: str
    model: str
    operation: str
    quantity: int
    estimated_cost: float
    created_at: datetime


class AdminUsageSummaryResponse(BaseModel):
    total_estimated_cost: float
    total_quantity: int
    successful_generations: int
    failed_generations: int
    by_provider: dict[str, float]
    items: list[UsageRecordResponse]


GeneratedImageJobDetailResponse.model_rebuild()
