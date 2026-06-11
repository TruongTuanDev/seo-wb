from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import JSONBType


class SellerFinanceSettings(Base):
    __tablename__ = "seller_finance_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="CASCADE"), unique=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="RUB", nullable=False)
    default_tax_mode: Mapped[str] = mapped_column(String(50), default="NONE", nullable=False)
    default_tax_rate: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0"), nullable=False)
    tax_base: Mapped[str] = mapped_column(String(50), default="PROFIT", nullable=False)
    default_packaging_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    default_labeling_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    default_shipping_to_warehouse_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    default_other_unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ProductFinanceSetting(Base):
    __tablename__ = "product_finance_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("wb_products.id", ondelete="CASCADE"), nullable=False, index=True)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    cost_currency: Mapped[str] = mapped_column(String(10), default="RUB", nullable=False)
    packaging_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    labeling_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    shipping_to_warehouse_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    other_unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    tax_mode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    tax_base: Mapped[str | None] = mapped_column(String(50), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ExternalCost(Base):
    __tablename__ = "external_costs"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False, index=True)
    cost_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    cost_type: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="RUB", nullable=False)
    allocation_method: Mapped[str] = mapped_column(String(50), default="BY_REVENUE", nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("wb_products.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class WbFinanceReportRow(Base):
    __tablename__ = "wb_finance_report_rows"
    __table_args__ = (UniqueConstraint("seller_id", "rrd_id", name="uq_wb_finance_rows_seller_rrd"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False, index=True)
    report_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    date_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    create_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    report_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rrd_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    nm_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    brand_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    vendor_code: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    tech_size: Mapped[str | None] = mapped_column(Text, nullable=True)
    sku: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    doc_type_name: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    seller_oper_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retail_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    retail_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    retail_price_with_disc: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    sale_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0"), nullable=False)
    commission_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0"), nullable=False)
    office_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_dt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sale_dt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    rr_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    shk_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    delivery_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    return_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivery_service: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    ppvz_sales_commission: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    for_pay: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    acquiring_fee: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    acquiring_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0"), nullable=False)
    payment_processing: Mapped[str | None] = mapped_column(Text, nullable=True)
    acquiring_bank: Mapped[str | None] = mapped_column(Text, nullable=True)
    penalty: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    additional_payment: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    rebill_logistic_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    paid_storage: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    deduction: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    paid_acceptance: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    order_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    order_uid: Mapped[str | None] = mapped_column(Text, nullable=True)
    srid: Mapped[str | None] = mapped_column(Text, nullable=True)
    kiz: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_b2b: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    delivery_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    cashback_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    cashback_discount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    cashback_commission_change: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    agency_vat: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("wb_products.id", ondelete="SET NULL"), nullable=True)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSONBType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class WbFinanceSyncState(Base):
    __tablename__ = "wb_finance_sync_state"
    __table_args__ = (UniqueConstraint("seller_id", "date_from", "date_to", "period", name="uq_wb_finance_sync_state"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False, index=True)
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    period: Mapped[str] = mapped_column(String(20), default="daily", nullable=False)
    last_rrd_id: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="idle", nullable=False)
    total_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class SellerFinanceAutomationState(Base):
    __tablename__ = "seller_finance_automation_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow", nullable=False)
    bootstrap_status: Mapped[str] = mapped_column(String(30), default="idle", nullable=False)
    bootstrap_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bootstrap_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bootstrap_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    bootstrap_range_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    bootstrap_range_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_successful_daily_sync_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_attempted_daily_sync_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_daily_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_daily_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_scheduler_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class FinanceAnalysisSnapshot(Base):
    __tablename__ = "finance_analysis_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False, index=True)
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    group_by: Mapped[str] = mapped_column(String(20), nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONBType, default=dict)
    product_breakdown: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONBType, nullable=True)
    cost_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    insights: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONBType, nullable=True)
    ai_analysis: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ApiDiagnosticLog(Base):
    __tablename__ = "api_diagnostic_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int | None] = mapped_column(ForeignKey("sellers.id", ondelete="SET NULL"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(50), default="wildberries", nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    status_code: Mapped[int | None] = mapped_column(nullable=True)
    request_meta: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    response_meta: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class WbFinancialDailySummary(Base):
    __tablename__ = "wb_financial_daily_summary"
    __table_args__ = (UniqueConstraint("seller_id", "summary_date", name="uq_wb_financial_daily_summary"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False, index=True)
    summary_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    gross_revenue: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    for_pay: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    wb_costs: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    cogs: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    profit_before_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    profit_after_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    raw_row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class WbFinancialMonthlySummary(Base):
    __tablename__ = "wb_financial_monthly_summary"
    __table_args__ = (UniqueConstraint("seller_id", "summary_month", name="uq_wb_financial_monthly_summary"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False, index=True)
    summary_month: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    gross_revenue: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    for_pay: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    wb_costs: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    cogs: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    profit_before_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    profit_after_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    raw_row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

