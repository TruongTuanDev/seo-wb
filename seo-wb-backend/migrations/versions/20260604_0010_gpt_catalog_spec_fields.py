"""gpt catalog spec fields

Revision ID: 20260604_0010
Revises: 20260604_0009
Create Date: 2026-06-04 12:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260604_0010"
down_revision = "20260604_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "card_drafts",
        sa.Column("garment_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "generated_image_jobs",
        sa.Column("generation_prompt", sa.Text(), nullable=True),
    )
    op.add_column(
        "generated_image_jobs",
        sa.Column("pose", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "generated_image_jobs",
        sa.Column("output_type", sa.String(length=40), nullable=True),
    )
    op.execute("UPDATE card_drafts SET garment_json = '{}' WHERE garment_json IS NULL")
    op.alter_column("card_drafts", "garment_json", nullable=False)


def downgrade() -> None:
    op.drop_column("generated_image_jobs", "output_type")
    op.drop_column("generated_image_jobs", "pose")
    op.drop_column("generated_image_jobs", "generation_prompt")
    op.drop_column("card_drafts", "garment_json")
