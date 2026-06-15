"""wb marketplace quality settings

Revision ID: 20260614_0014
Revises: 20260614_0013
Create Date: 2026-06-14 16:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260614_0014"
down_revision = "20260614_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("admin_ai_settings", sa.Column("enable_russian_grammar_validation", sa.Boolean(), nullable=True))
    op.add_column("admin_ai_settings", sa.Column("enable_keyword_stuffing_detection", sa.Boolean(), nullable=True))
    op.add_column("admin_ai_settings", sa.Column("enable_subject_title_templates", sa.Boolean(), nullable=True))
    op.add_column("admin_ai_settings", sa.Column("include_gender_in_title", sa.Boolean(), nullable=True))
    op.add_column("admin_ai_settings", sa.Column("minimum_grammar_score", sa.Integer(), nullable=True))
    op.add_column("admin_ai_settings", sa.Column("minimum_marketplace_score", sa.Integer(), nullable=True))
    op.add_column("admin_ai_settings", sa.Column("minimum_critical_attribute_score", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE admin_ai_settings
        SET
            enable_russian_grammar_validation = TRUE,
            enable_keyword_stuffing_detection = TRUE,
            enable_subject_title_templates = TRUE,
            include_gender_in_title = FALSE,
            minimum_grammar_score = 70,
            minimum_marketplace_score = 70,
            minimum_critical_attribute_score = 80
        WHERE enable_russian_grammar_validation IS NULL
        """
    )
    op.alter_column("admin_ai_settings", "enable_russian_grammar_validation", nullable=False)
    op.alter_column("admin_ai_settings", "enable_keyword_stuffing_detection", nullable=False)
    op.alter_column("admin_ai_settings", "enable_subject_title_templates", nullable=False)
    op.alter_column("admin_ai_settings", "include_gender_in_title", nullable=False)
    op.alter_column("admin_ai_settings", "minimum_grammar_score", nullable=False)
    op.alter_column("admin_ai_settings", "minimum_marketplace_score", nullable=False)
    op.alter_column("admin_ai_settings", "minimum_critical_attribute_score", nullable=False)


def downgrade() -> None:
    op.drop_column("admin_ai_settings", "minimum_critical_attribute_score")
    op.drop_column("admin_ai_settings", "minimum_marketplace_score")
    op.drop_column("admin_ai_settings", "minimum_grammar_score")
    op.drop_column("admin_ai_settings", "include_gender_in_title")
    op.drop_column("admin_ai_settings", "enable_subject_title_templates")
    op.drop_column("admin_ai_settings", "enable_keyword_stuffing_detection")
    op.drop_column("admin_ai_settings", "enable_russian_grammar_validation")
