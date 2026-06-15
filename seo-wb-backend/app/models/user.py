from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user", index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True, nullable=False)
    plan_type: Mapped[str] = mapped_column(String(20), default="free", index=True, nullable=False)
    monthly_quota: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    used_quota: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    monthly_cost_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    used_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    credit_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    credits_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    credits_granted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quota_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_quota_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    stores = relationship("Store", back_populates="user", cascade="all, delete-orphan")
    drafts = relationship("CardDraft", back_populates="user", cascade="all, delete-orphan")
    image_jobs = relationship("GeneratedImageJob", back_populates="user", cascade="all, delete-orphan")
    usage_records = relationship("UsageRecord", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("UserSubscription", back_populates="user", cascade="all, delete-orphan")
    payment_transactions = relationship("PaymentTransaction", back_populates="user", cascade="all, delete-orphan")
    credit_transactions = relationship("CreditTransaction", back_populates="user", cascade="all, delete-orphan")
