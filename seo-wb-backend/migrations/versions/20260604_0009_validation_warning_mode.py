"""validation warning mode

Revision ID: 20260604_0009
Revises: 20260603_0008
Create Date: 2026-06-04 10:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260604_0009"
down_revision = "20260603_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "admin_ai_settings",
        sa.Column("validation_failure_behavior", sa.String(length=16), nullable=False, server_default="warn"),
    )
    op.alter_column("admin_ai_settings", "validation_failure_behavior", server_default=None)


def downgrade() -> None:
    op.drop_column("admin_ai_settings", "validation_failure_behavior")
