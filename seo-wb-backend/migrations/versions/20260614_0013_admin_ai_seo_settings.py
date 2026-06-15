"""admin ai seo settings

Revision ID: 20260614_0013
Revises: 20260612_0012
Create Date: 2026-06-14 10:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260614_0013"
down_revision = "20260612_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("admin_ai_settings", sa.Column("seo_engine_enabled", sa.Boolean(), nullable=True))
    op.add_column("admin_ai_settings", sa.Column("seo_min_score", sa.Integer(), nullable=True))
    op.add_column("admin_ai_settings", sa.Column("description_min_chars", sa.Integer(), nullable=True))
    op.add_column("admin_ai_settings", sa.Column("description_max_chars", sa.Integer(), nullable=True))
    op.add_column("admin_ai_settings", sa.Column("seo_repair_max_attempts", sa.Integer(), nullable=True))
    op.add_column("admin_ai_settings", sa.Column("require_primary_keyword_in_title", sa.Boolean(), nullable=True))
    op.add_column("admin_ai_settings", sa.Column("warn_low_confidence_attributes", sa.Boolean(), nullable=True))
    op.execute(
        """
        UPDATE admin_ai_settings
        SET
            seo_engine_enabled = TRUE,
            seo_min_score = 70,
            description_min_chars = 600,
            description_max_chars = 900,
            seo_repair_max_attempts = 1,
            require_primary_keyword_in_title = TRUE,
            warn_low_confidence_attributes = TRUE
        WHERE seo_engine_enabled IS NULL
        """
    )
    op.alter_column("admin_ai_settings", "seo_engine_enabled", nullable=False)
    op.alter_column("admin_ai_settings", "seo_min_score", nullable=False)
    op.alter_column("admin_ai_settings", "description_min_chars", nullable=False)
    op.alter_column("admin_ai_settings", "description_max_chars", nullable=False)
    op.alter_column("admin_ai_settings", "seo_repair_max_attempts", nullable=False)
    op.alter_column("admin_ai_settings", "require_primary_keyword_in_title", nullable=False)
    op.alter_column("admin_ai_settings", "warn_low_confidence_attributes", nullable=False)


def downgrade() -> None:
    op.drop_column("admin_ai_settings", "warn_low_confidence_attributes")
    op.drop_column("admin_ai_settings", "require_primary_keyword_in_title")
    op.drop_column("admin_ai_settings", "seo_repair_max_attempts")
    op.drop_column("admin_ai_settings", "description_max_chars")
    op.drop_column("admin_ai_settings", "description_min_chars")
    op.drop_column("admin_ai_settings", "seo_min_score")
    op.drop_column("admin_ai_settings", "seo_engine_enabled")
