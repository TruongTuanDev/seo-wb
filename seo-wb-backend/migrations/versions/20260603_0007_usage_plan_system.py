"""usage plan system

Revision ID: 20260603_0007
Revises: 20260601_0006
Create Date: 2026-06-03
"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260603_0007"
down_revision: Union[str, None] = "20260601_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _next_month_reset() -> datetime:
    now = datetime.now(timezone.utc)
    if now.month == 12:
        return now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)


def upgrade() -> None:
    op.add_column("users", sa.Column("plan_type", sa.String(length=20), nullable=False, server_default="free"))
    op.add_column("users", sa.Column("quota_reset_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("last_quota_reset_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_plan_type", "users", ["plan_type"], unique=False)
    op.create_index("ix_users_quota_reset_at", "users", ["quota_reset_at"], unique=False)

    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    next_reset = _next_month_reset()
    bind.execute(
        sa.text(
            """
            UPDATE users
            SET plan_type = COALESCE(plan_type, 'free'),
                quota_reset_at = COALESCE(quota_reset_at, :next_reset),
                last_quota_reset_at = COALESCE(last_quota_reset_at, :now)
            """
        ),
        {"next_reset": next_reset, "now": now},
    )


def downgrade() -> None:
    op.drop_index("ix_users_quota_reset_at", table_name="users")
    op.drop_index("ix_users_plan_type", table_name="users")
    op.drop_column("users", "last_quota_reset_at")
    op.drop_column("users", "quota_reset_at")
    op.drop_column("users", "plan_type")
