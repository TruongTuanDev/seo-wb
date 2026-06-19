from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.db.types import JSONBType


class StoreCategory(Base):
    """A Wildberries subject (category) the shop actually uses, with its default TN VED code.

    Rows are derived automatically from the shop's synced products and may be
    extended/edited manually. When ``locked`` is set, an auto-sync keeps the
    manually chosen ``tnved`` instead of overwriting it with the most-used code.
    """

    __tablename__ = "store_categories"
    __table_args__ = (UniqueConstraint("store_id", "subject_id", name="uq_store_categories_store_subject"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    subject_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tnved: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tnved_options: Mapped[list[dict[str, Any]]] = mapped_column(JSONBType, default=list)
    source: Mapped[str] = mapped_column(String(16), default="auto", nullable=False)
    locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    product_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    store = relationship("Store", back_populates="categories")


class StoreCategorySyncState(Base):
    """Tracks the progress of a (background) shop-category sync so large shops can
    sync without blocking an HTTP request and the UI can poll for status."""

    __tablename__ = "store_category_sync_state"
    __table_args__ = (UniqueConstraint("store_id", name="uq_store_category_sync_state_store"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="idle", nullable=False)
    total_scanned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    categories_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
