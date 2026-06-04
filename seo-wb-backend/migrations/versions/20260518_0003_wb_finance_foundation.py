"""wildberries finance foundation

Revision ID: 20260518_0003
Revises: 20260420_0002
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260518_0003"
down_revision: Union[str, None] = "20260420_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sellers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("external_sid", sa.String(length=120), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("trade_mark", sa.String(length=255), nullable=True),
        sa.Column("tin", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("store_id"),
    )
    op.create_index("ix_sellers_store_id", "sellers", ["store_id"], unique=False)

    op.create_table(
        "api_diagnostic_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("seller_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("request_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("response_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["seller_id"], ["sellers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_diagnostic_logs_seller_id", "api_diagnostic_logs", ["seller_id"], unique=False)

    op.create_table(
        "wb_products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("seller_id", sa.Integer(), nullable=False),
        sa.Column("nm_id", sa.Integer(), nullable=False),
        sa.Column("imt_id", sa.Integer(), nullable=True),
        sa.Column("nm_uuid", sa.String(length=120), nullable=True),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("subject_name", sa.String(length=255), nullable=True),
        sa.Column("vendor_code", sa.String(length=255), nullable=True),
        sa.Column("brand", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=1000), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("need_kiz", sa.Boolean(), nullable=True),
        sa.Column("kiz_marked", sa.Boolean(), nullable=True),
        sa.Column("photo_big_url", sa.Text(), nullable=True),
        sa.Column("photo_square_url", sa.Text(), nullable=True),
        sa.Column("length", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("width", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("height", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("weight_brutto", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("dimensions_valid", sa.Boolean(), nullable=True),
        sa.Column("characteristics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sizes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("skus", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("wb_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["seller_id"], ["sellers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("seller_id", "nm_id", name="uq_wb_products_seller_nm"),
    )
    op.create_index("ix_wb_products_seller_id", "wb_products", ["seller_id"], unique=False)
    op.create_index("ix_wb_products_nm_id", "wb_products", ["nm_id"], unique=False)
    op.create_index("ix_wb_products_vendor_code", "wb_products", ["vendor_code"], unique=False)

    op.create_table(
        "wb_product_sync_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("seller_id", sa.Integer(), nullable=False),
        sa.Column("sync_type", sa.String(length=30), nullable=False),
        sa.Column("cursor_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cursor_nm_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("total_synced", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["seller_id"], ["sellers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("seller_id", "sync_type", name="uq_wb_product_sync_state"),
    )
    op.create_index("ix_wb_product_sync_state_seller_id", "wb_product_sync_state", ["seller_id"], unique=False)

    op.create_table(
        "seller_finance_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("seller_id", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("default_tax_mode", sa.String(length=50), nullable=False),
        sa.Column("default_tax_rate", sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column("tax_base", sa.String(length=50), nullable=False),
        sa.Column("default_packaging_cost", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("default_labeling_cost", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("default_shipping_to_warehouse_cost", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("default_other_unit_cost", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["seller_id"], ["sellers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("seller_id"),
    )

    op.create_table(
        "product_finance_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("seller_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("cost_price", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("cost_currency", sa.String(length=10), nullable=False),
        sa.Column("packaging_cost", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("labeling_cost", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("shipping_to_warehouse_cost", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("other_unit_cost", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("tax_mode", sa.String(length=50), nullable=True),
        sa.Column("tax_rate", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("tax_base", sa.String(length=50), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["wb_products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["seller_id"], ["sellers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_finance_settings_seller_id", "product_finance_settings", ["seller_id"], unique=False)
    op.create_index("ix_product_finance_settings_product_id", "product_finance_settings", ["product_id"], unique=False)

    op.create_table(
        "external_costs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("seller_id", sa.Integer(), nullable=False),
        sa.Column("cost_date", sa.Date(), nullable=False),
        sa.Column("period_from", sa.Date(), nullable=True),
        sa.Column("period_to", sa.Date(), nullable=True),
        sa.Column("cost_type", sa.String(length=100), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("allocation_method", sa.String(length=50), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["wb_products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["seller_id"], ["sellers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_external_costs_seller_id", "external_costs", ["seller_id"], unique=False)

    op.create_table(
        "wb_finance_report_rows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("seller_id", sa.Integer(), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=True),
        sa.Column("date_from", sa.Date(), nullable=True),
        sa.Column("date_to", sa.Date(), nullable=True),
        sa.Column("create_date", sa.Date(), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("report_type", sa.Integer(), nullable=True),
        sa.Column("rrd_id", sa.Integer(), nullable=False),
        sa.Column("nm_id", sa.Integer(), nullable=True),
        sa.Column("brand_name", sa.Text(), nullable=True),
        sa.Column("vendor_code", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("subject_name", sa.Text(), nullable=True),
        sa.Column("tech_size", sa.Text(), nullable=True),
        sa.Column("sku", sa.Text(), nullable=True),
        sa.Column("doc_type_name", sa.Text(), nullable=True),
        sa.Column("seller_oper_name", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("retail_price", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("retail_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("retail_price_with_disc", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("sale_percent", sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column("commission_percent", sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column("office_name", sa.Text(), nullable=True),
        sa.Column("order_dt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sale_dt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rr_date", sa.Date(), nullable=True),
        sa.Column("shk_id", sa.Integer(), nullable=True),
        sa.Column("delivery_amount", sa.Integer(), nullable=False),
        sa.Column("return_amount", sa.Integer(), nullable=False),
        sa.Column("delivery_service", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("ppvz_sales_commission", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("for_pay", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("acquiring_fee", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("acquiring_percent", sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column("payment_processing", sa.Text(), nullable=True),
        sa.Column("acquiring_bank", sa.Text(), nullable=True),
        sa.Column("penalty", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("additional_payment", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("rebill_logistic_cost", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("paid_storage", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("deduction", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("paid_acceptance", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("order_uid", sa.Text(), nullable=True),
        sa.Column("srid", sa.Text(), nullable=True),
        sa.Column("kiz", sa.Text(), nullable=True),
        sa.Column("is_b2b", sa.Boolean(), nullable=True),
        sa.Column("delivery_method", sa.Text(), nullable=True),
        sa.Column("cashback_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("cashback_discount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("cashback_commission_change", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("agency_vat", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["wb_products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["seller_id"], ["sellers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("seller_id", "rrd_id", name="uq_wb_finance_rows_seller_rrd"),
    )
    op.create_index("ix_wb_finance_report_rows_seller_id", "wb_finance_report_rows", ["seller_id"], unique=False)
    op.create_index("ix_wb_finance_report_rows_rrd_id", "wb_finance_report_rows", ["rrd_id"], unique=False)
    op.create_index("ix_wb_finance_report_rows_nm_id", "wb_finance_report_rows", ["nm_id"], unique=False)
    op.create_index("ix_wb_finance_report_rows_vendor_code", "wb_finance_report_rows", ["vendor_code"], unique=False)
    op.create_index("ix_wb_finance_report_rows_sku", "wb_finance_report_rows", ["sku"], unique=False)
    op.create_index("ix_wb_finance_report_rows_doc_type_name", "wb_finance_report_rows", ["doc_type_name"], unique=False)
    op.create_index("ix_wb_finance_report_rows_sale_dt", "wb_finance_report_rows", ["sale_dt"], unique=False)
    op.create_index("ix_wb_finance_report_rows_rr_date", "wb_finance_report_rows", ["rr_date"], unique=False)

    op.create_table(
        "wb_finance_sync_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("seller_id", sa.Integer(), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("period", sa.String(length=20), nullable=False),
        sa.Column("last_rrd_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["seller_id"], ["sellers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("seller_id", "date_from", "date_to", "period", name="uq_wb_finance_sync_state"),
    )
    op.create_index("ix_wb_finance_sync_state_seller_id", "wb_finance_sync_state", ["seller_id"], unique=False)

    op.create_table(
        "finance_analysis_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("seller_id", sa.Integer(), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("group_by", sa.String(length=20), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("product_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("cost_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("insights", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ai_analysis", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["seller_id"], ["sellers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_finance_analysis_snapshots_seller_id", "finance_analysis_snapshots", ["seller_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_finance_analysis_snapshots_seller_id", table_name="finance_analysis_snapshots")
    op.drop_table("finance_analysis_snapshots")
    op.drop_index("ix_wb_finance_sync_state_seller_id", table_name="wb_finance_sync_state")
    op.drop_table("wb_finance_sync_state")
    op.drop_index("ix_wb_finance_report_rows_rr_date", table_name="wb_finance_report_rows")
    op.drop_index("ix_wb_finance_report_rows_sale_dt", table_name="wb_finance_report_rows")
    op.drop_index("ix_wb_finance_report_rows_doc_type_name", table_name="wb_finance_report_rows")
    op.drop_index("ix_wb_finance_report_rows_sku", table_name="wb_finance_report_rows")
    op.drop_index("ix_wb_finance_report_rows_vendor_code", table_name="wb_finance_report_rows")
    op.drop_index("ix_wb_finance_report_rows_nm_id", table_name="wb_finance_report_rows")
    op.drop_index("ix_wb_finance_report_rows_rrd_id", table_name="wb_finance_report_rows")
    op.drop_index("ix_wb_finance_report_rows_seller_id", table_name="wb_finance_report_rows")
    op.drop_table("wb_finance_report_rows")
    op.drop_index("ix_external_costs_seller_id", table_name="external_costs")
    op.drop_table("external_costs")
    op.drop_index("ix_product_finance_settings_product_id", table_name="product_finance_settings")
    op.drop_index("ix_product_finance_settings_seller_id", table_name="product_finance_settings")
    op.drop_table("product_finance_settings")
    op.drop_table("seller_finance_settings")
    op.drop_index("ix_wb_product_sync_state_seller_id", table_name="wb_product_sync_state")
    op.drop_table("wb_product_sync_state")
    op.drop_index("ix_wb_products_vendor_code", table_name="wb_products")
    op.drop_index("ix_wb_products_nm_id", table_name="wb_products")
    op.drop_index("ix_wb_products_seller_id", table_name="wb_products")
    op.drop_table("wb_products")
    op.drop_index("ix_api_diagnostic_logs_seller_id", table_name="api_diagnostic_logs")
    op.drop_table("api_diagnostic_logs")
    op.drop_index("ix_sellers_store_id", table_name="sellers")
    op.drop_table("sellers")
