"""add price_manifest to card_jobs

Revision ID: 20260619_0017
Revises: 20260619_0016
Create Date: 2026-06-19 12:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260619_0017"
down_revision = "20260619_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "card_jobs",
        sa.Column("price_manifest", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("card_jobs", "price_manifest")
