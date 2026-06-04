"""finance automation state

Revision ID: 20260518_0004
Revises: 20260518_0003
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260518_0004"
down_revision: Union[str, None] = "20260518_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "seller_finance_automation_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("seller_id", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("bootstrap_status", sa.String(length=30), nullable=False),
        sa.Column("bootstrap_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bootstrap_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bootstrap_last_error", sa.Text(), nullable=True),
        sa.Column("bootstrap_range_from", sa.Date(), nullable=True),
        sa.Column("bootstrap_range_to", sa.Date(), nullable=True),
        sa.Column("last_successful_daily_sync_date", sa.Date(), nullable=True),
        sa.Column("last_attempted_daily_sync_date", sa.Date(), nullable=True),
        sa.Column("last_daily_status", sa.String(length=30), nullable=True),
        sa.Column("last_daily_error", sa.Text(), nullable=True),
        sa.Column("last_scheduler_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["seller_id"], ["sellers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("seller_id"),
    )
    op.create_index("ix_seller_finance_automation_state_seller_id", "seller_finance_automation_state", ["seller_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_seller_finance_automation_state_seller_id", table_name="seller_finance_automation_state")
    op.drop_table("seller_finance_automation_state")
