from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str = "user"
    status: str = "active"
    plan_type: str = "free"


class TokenResponse(BaseModel):
    access_token: str | None = None
    token_type: str = "bearer"
    user: UserResponse


class UsageSummaryResponse(BaseModel):
    plan_type: str
    monthly_quota: int
    used_quota: int
    remaining_quota: int
    quota_percent: float
    monthly_cost_limit: float | None
    used_cost: float
    remaining_cost: float | None
    cost_percent: float | None
    max_images_per_job: int
    allow_legacy_vton: bool
    allow_gpt_image: bool
    priority_queue: bool
    credit_balance: int = 0
    credits_used: int = 0
    credits_granted: int = 0
    remaining_cards: int = 0
    remaining_images: int = 0
    quota_reset_at: datetime | None = None
    last_quota_reset_at: datetime | None = None
