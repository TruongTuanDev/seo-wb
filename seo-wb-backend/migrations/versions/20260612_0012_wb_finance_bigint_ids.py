"""use bigint for Wildberries finance identifiers

Revision ID: 20260612_0012
Revises: 909ded0637c8
Create Date: 2026-06-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260612_0012"
down_revision: Union[str, None] = "909ded0637c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for column_name in ("report_id", "rrd_id", "nm_id", "shk_id", "order_id"):
        op.alter_column(
            "wb_finance_report_rows",
            column_name,
            existing_type=sa.Integer(),
            type_=sa.BigInteger(),
            existing_nullable=column_name != "rrd_id",
        )
    op.alter_column(
        "wb_finance_sync_state",
        "last_rrd_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "wb_finance_sync_state",
        "last_rrd_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
    for column_name in ("order_id", "shk_id", "nm_id", "rrd_id", "report_id"):
        op.alter_column(
            "wb_finance_report_rows",
            column_name,
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            existing_nullable=column_name != "rrd_id",
        )
