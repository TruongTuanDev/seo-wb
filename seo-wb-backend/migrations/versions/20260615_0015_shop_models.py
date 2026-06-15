"""add shop-scoped model library

Revision ID: 20260615_0015
Revises: 20260614_0014
Create Date: 2026-06-15 20:15:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260615_0015"
down_revision = "20260614_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shop_models",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("gender", sa.String(length=32), nullable=False, server_default="Unknown"),
        sa.Column("body_type", sa.String(length=64), nullable=False, server_default="Unknown"),
        sa.Column("height_cm", sa.Integer(), nullable=True),
        sa.Column("weight_kg", sa.Integer(), nullable=True),
        sa.Column("garment_type", sa.String(length=64), nullable=True),
        sa.Column("reference_image_url", sa.String(length=1024), nullable=False),
        sa.Column("thumbnail_url", sa.String(length=1024), nullable=True),
        sa.Column("poses", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_models_store_id", "shop_models", ["store_id"])
    op.create_index("ix_shop_models_name", "shop_models", ["name"])


def downgrade() -> None:
    op.drop_index("ix_shop_models_name", table_name="shop_models")
    op.drop_index("ix_shop_models_store_id", table_name="shop_models")
    op.drop_table("shop_models")
