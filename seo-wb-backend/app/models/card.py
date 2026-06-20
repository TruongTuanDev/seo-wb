from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class CardDraft(Base):
    __tablename__ = "card_drafts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    subject_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    vendor_code: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    analysis: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    garment_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    card_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    wb_response: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="drafts")
    store = relationship("Store", back_populates="drafts")


class CardJob(Base):
    __tablename__ = "card_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True, nullable=False)
    draft_id: Mapped[int | None] = mapped_column(ForeignKey("card_drafts.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    step: Mapped[str] = mapped_column(String(80), default="queued")
    mode: Mapped[str] = mapped_column(String(40), default="create_new")
    target_imt: Mapped[int | None] = mapped_column(nullable=True)
    subject_id: Mapped[int | None] = mapped_column(nullable=True)
    card_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    media_manifest: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    price_manifest: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    warehouse_id: Mapped[int | None] = mapped_column(nullable=True)
    stock_manifest: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User")
    store = relationship("Store")
    draft = relationship("CardDraft")
