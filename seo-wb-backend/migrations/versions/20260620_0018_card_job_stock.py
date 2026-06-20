"""add warehouse_id and stock_manifest to card_jobs

Revision ID: 20260620_0018
Revises: 20260619_0017
Create Date: 2026-06-20 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260620_0018"
down_revision = "20260619_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("card_jobs", sa.Column("warehouse_id", sa.Integer(), nullable=True))
    op.add_column(
        "card_jobs",
        sa.Column("stock_manifest", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("card_jobs", "stock_manifest")
    op.drop_column("card_jobs", "warehouse_id")
