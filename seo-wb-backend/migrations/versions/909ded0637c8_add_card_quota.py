"""add_card_quota

Revision ID: 909ded0637c8
Revises: 20260604_0011
Create Date: 2026-06-04 22:04:29.669786+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "909ded0637c8"
down_revision: Union[str, None] = "20260604_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subscription_plans",
        sa.Column("monthly_card_quota", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column("monthly_card_quota", sa.Integer(), nullable=False, server_default="50"),
    )
    op.add_column(
        "users",
        sa.Column("used_card_quota", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "used_card_quota")
    op.drop_column("users", "monthly_card_quota")
    op.drop_column("subscription_plans", "monthly_card_quota")
