"""card jobs

Revision ID: 20260420_0002
Revises: 20260420_0001
Create Date: 2026-04-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260420_0002"
down_revision: Union[str, None] = "20260420_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "card_jobs",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("draft_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("step", sa.String(length=80), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("target_imt", sa.Integer(), nullable=True),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("card_payload", sa.JSON(), nullable=False),
        sa.Column("media_manifest", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["card_drafts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_card_jobs_id", "card_jobs", ["id"], unique=False)
    op.create_index("ix_card_jobs_draft_id", "card_jobs", ["draft_id"], unique=False)
    op.create_index("ix_card_jobs_status", "card_jobs", ["status"], unique=False)
    op.create_index("ix_card_jobs_store_id", "card_jobs", ["store_id"], unique=False)
    op.create_index("ix_card_jobs_user_id", "card_jobs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_card_jobs_user_id", table_name="card_jobs")
    op.drop_index("ix_card_jobs_store_id", table_name="card_jobs")
    op.drop_index("ix_card_jobs_status", table_name="card_jobs")
    op.drop_index("ix_card_jobs_draft_id", table_name="card_jobs")
    op.drop_index("ix_card_jobs_id", table_name="card_jobs")
    op.drop_table("card_jobs")
