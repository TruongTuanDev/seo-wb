"""admin hardening

Revision ID: 20260601_0006
Revises: 20260601_0005
Create Date: 2026-06-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260601_0006"
down_revision: Union[str, None] = "20260601_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("monthly_cost_limit", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("used_cost", sa.Float(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"], unique=False)

    op.add_column("model_templates", sa.Column("quality_status", sa.String(length=20), nullable=False, server_default="draft"))
    op.add_column("model_templates", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_model_templates_quality_status", "model_templates", ["quality_status"], unique=False)
    op.create_index("ix_model_templates_deleted_at", "model_templates", ["deleted_at"], unique=False)

    op.add_column("generated_image_jobs", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_generated_image_jobs_deleted_at", "generated_image_jobs", ["deleted_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_generated_image_jobs_deleted_at", table_name="generated_image_jobs")
    op.drop_column("generated_image_jobs", "deleted_at")

    op.drop_index("ix_model_templates_deleted_at", table_name="model_templates")
    op.drop_index("ix_model_templates_quality_status", table_name="model_templates")
    op.drop_column("model_templates", "deleted_at")
    op.drop_column("model_templates", "quality_status")

    op.drop_index("ix_users_deleted_at", table_name="users")
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "used_cost")
    op.drop_column("users", "monthly_cost_limit")
