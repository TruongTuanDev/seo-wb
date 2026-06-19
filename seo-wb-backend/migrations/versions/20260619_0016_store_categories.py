"""add per-store category catalog with default TN VED

Revision ID: 20260619_0016
Revises: 20260615_0015
Create Date: 2026-06-19 10:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260619_0016"
down_revision = "20260615_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "store_categories",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("subject_name", sa.String(length=255), nullable=True),
        sa.Column("tnved", sa.String(length=20), nullable=True),
        sa.Column(
            "tnved_options",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="auto"),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("product_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("store_id", "subject_id", name="uq_store_categories_store_subject"),
    )
    op.create_index("ix_store_categories_store_id", "store_categories", ["store_id"])
    op.create_index("ix_store_categories_subject_id", "store_categories", ["subject_id"])

    op.create_table(
        "store_category_sync_state",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="idle"),
        sa.Column("total_scanned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("categories_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("store_id", name="uq_store_category_sync_state_store"),
    )
    op.create_index(
        "ix_store_category_sync_state_store_id", "store_category_sync_state", ["store_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_store_category_sync_state_store_id", table_name="store_category_sync_state")
    op.drop_table("store_category_sync_state")
    op.drop_index("ix_store_categories_subject_id", table_name="store_categories")
    op.drop_index("ix_store_categories_store_id", table_name="store_categories")
    op.drop_table("store_categories")
