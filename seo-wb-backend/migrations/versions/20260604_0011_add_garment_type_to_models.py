"""add garment_type to model_templates

Revision ID: 20260604_0011
Revises: c79a5ec758bc
Create Date: 2026-06-04 13:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260604_0011"
down_revision = "c79a5ec758bc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "model_templates",
        sa.Column("garment_type", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("model_templates", "garment_type")
