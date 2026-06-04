from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ModelTemplate(Base):
    __tablename__ = "model_templates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    gender: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    body_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)
    quality_status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    reference_image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    poses: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    image_jobs = relationship("GeneratedImageJob", back_populates="model_template")


class GeneratedImageJob(Base):
    __tablename__ = "generated_image_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id", ondelete="SET NULL"), index=True, nullable=True)
    draft_id: Mapped[int | None] = mapped_column(ForeignKey("card_drafts.id", ondelete="SET NULL"), index=True, nullable=True)
    job_type: Mapped[str] = mapped_column(String(40), default="gpt_image", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False, index=True)
    step: Mapped[str] = mapped_column(String(80), default="queued", nullable=False)
    model_id: Mapped[str | None] = mapped_column(ForeignKey("model_templates.id", ondelete="SET NULL"), nullable=True, index=True)
    ai_model: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    style: Mapped[str | None] = mapped_column(String(80), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    garment_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    validation_result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    generation_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    pose: Mapped[str | None] = mapped_column(String(40), nullable=True)
    output_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    images: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    credit_cost: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    queue_name: Mapped[str] = mapped_column(String(32), default="image_jobs_normal", nullable=False, index=True)
    credits_consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    user = relationship("User", back_populates="image_jobs")
    store = relationship("Store")
    draft = relationship("CardDraft")
    model_template = relationship("ModelTemplate", back_populates="image_jobs")
    usage_records = relationship("UsageRecord", back_populates="job", cascade="all, delete-orphan")
    credit_transactions = relationship("CreditTransaction", back_populates="job", cascade="all, delete-orphan")


class AdminAiSettings(Base):
    __tablename__ = "admin_ai_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    default_image_model: Mapped[str] = mapped_column(String(80), default="gpt-image-2", nullable=False)
    fallback_image_model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    gemini_model: Mapped[str] = mapped_column(String(80), default="gemini-2.5-flash", nullable=False)
    max_retry: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    default_quantity: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    realism_threshold: Mapped[int] = mapped_column(Integer, default=80, nullable=False)
    validation_threshold: Mapped[int] = mapped_column(Integer, default=85, nullable=False)
    validation_failure_behavior: Mapped[str] = mapped_column(String(16), default="warn", nullable=False)
    allow_legacy_vton: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("generated_image_jobs.id", ondelete="SET NULL"), index=True, nullable=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    user = relationship("User", back_populates="usage_records")
    job = relationship("GeneratedImageJob", back_populates="usage_records")


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
