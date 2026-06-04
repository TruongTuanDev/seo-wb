from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.db.types import JSONBType


class WbProduct(Base):
    __tablename__ = "wb_products"
    __table_args__ = (UniqueConstraint("seller_id", "nm_id", name="uq_wb_products_seller_nm"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False, index=True)
    nm_id: Mapped[int] = mapped_column(nullable=False, index=True)
    imt_id: Mapped[int | None] = mapped_column(nullable=True)
    nm_uuid: Mapped[str | None] = mapped_column(String(120), nullable=True)
    subject_id: Mapped[int | None] = mapped_column(nullable=True)
    subject_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vendor_code: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    need_kiz: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    kiz_marked: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    photo_big_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_square_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    length: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    width: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    height: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    weight_brutto: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    dimensions_valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    characteristics: Mapped[list[dict[str, Any]]] = mapped_column(JSONBType, default=list)
    sizes: Mapped[list[dict[str, Any]]] = mapped_column(JSONBType, default=list)
    skus: Mapped[list[str]] = mapped_column(JSONBType, default=list)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSONBType, default=dict)
    wb_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    seller = relationship("Seller", back_populates="products")


class WbProductSyncState(Base):
    __tablename__ = "wb_product_sync_state"
    __table_args__ = (UniqueConstraint("seller_id", "sync_type", name="uq_wb_product_sync_state"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False, index=True)
    sync_type: Mapped[str] = mapped_column(String(30), default="active_cards", nullable=False)
    cursor_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cursor_nm_id: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="idle", nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_synced: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
