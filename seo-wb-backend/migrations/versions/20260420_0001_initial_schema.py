"""initial schema

Revision ID: 20260420_0001
Revises:
Create Date: 2026-04-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260420_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "stores",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("wb_api_key_encrypted", sa.String(length=4096), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stores_id", "stores", ["id"], unique=False)
    op.create_index("ix_stores_user_id", "stores", ["user_id"], unique=False)

    op.create_table(
        "card_drafts",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("vendor_code", sa.String(length=180), nullable=True),
        sa.Column("analysis", sa.JSON(), nullable=False),
        sa.Column("card_payload", sa.JSON(), nullable=False),
        sa.Column("wb_response", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_card_drafts_id", "card_drafts", ["id"], unique=False)
    op.create_index("ix_card_drafts_status", "card_drafts", ["status"], unique=False)
    op.create_index("ix_card_drafts_store_id", "card_drafts", ["store_id"], unique=False)
    op.create_index("ix_card_drafts_subject_id", "card_drafts", ["subject_id"], unique=False)
    op.create_index("ix_card_drafts_user_id", "card_drafts", ["user_id"], unique=False)
    op.create_index("ix_card_drafts_vendor_code", "card_drafts", ["vendor_code"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_card_drafts_vendor_code", table_name="card_drafts")
    op.drop_index("ix_card_drafts_user_id", table_name="card_drafts")
    op.drop_index("ix_card_drafts_subject_id", table_name="card_drafts")
    op.drop_index("ix_card_drafts_store_id", table_name="card_drafts")
    op.drop_index("ix_card_drafts_status", table_name="card_drafts")
    op.drop_index("ix_card_drafts_id", table_name="card_drafts")
    op.drop_table("card_drafts")

    op.drop_index("ix_stores_user_id", table_name="stores")
    op.drop_index("ix_stores_id", table_name="stores")
    op.drop_table("stores")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
