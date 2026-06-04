"""admin panel foundation

Revision ID: 20260601_0005
Revises: 20260518_0004
Create Date: 2026-06-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260601_0005"
down_revision: Union[str, None] = "20260518_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(length=20), nullable=False, server_default="user"))
    op.add_column("users", sa.Column("status", sa.String(length=20), nullable=False, server_default="active"))
    op.add_column("users", sa.Column("monthly_quota", sa.Integer(), nullable=False, server_default="100"))
    op.add_column("users", sa.Column("used_quota", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_users_role", "users", ["role"], unique=False)
    op.create_index("ix_users_status", "users", ["status"], unique=False)

    op.create_table(
        "model_templates",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("gender", sa.String(length=32), nullable=False),
        sa.Column("body_type", sa.String(length=64), nullable=False),
        sa.Column("height_cm", sa.Integer(), nullable=True),
        sa.Column("weight_kg", sa.Integer(), nullable=True),
        sa.Column("is_ai_generated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("thumbnail_url", sa.String(length=1024), nullable=True),
        sa.Column("reference_image_url", sa.String(length=1024), nullable=True),
        sa.Column("poses", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_templates_name", "model_templates", ["name"], unique=False)
    op.create_index("ix_model_templates_gender", "model_templates", ["gender"], unique=False)
    op.create_index("ix_model_templates_body_type", "model_templates", ["body_type"], unique=False)
    op.create_index("ix_model_templates_status", "model_templates", ["status"], unique=False)

    op.create_table(
        "admin_ai_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("default_image_model", sa.String(length=80), nullable=False),
        sa.Column("fallback_image_model", sa.String(length=80), nullable=True),
        sa.Column("gemini_model", sa.String(length=80), nullable=False),
        sa.Column("max_retry", sa.Integer(), nullable=False),
        sa.Column("default_quantity", sa.Integer(), nullable=False),
        sa.Column("realism_threshold", sa.Integer(), nullable=False),
        sa.Column("validation_threshold", sa.Integer(), nullable=False),
        sa.Column("allow_legacy_vton", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "generated_image_jobs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.Integer(), nullable=True),
        sa.Column("draft_id", sa.Integer(), nullable=True),
        sa.Column("job_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("step", sa.String(length=80), nullable=False),
        sa.Column("model_id", sa.String(length=64), nullable=True),
        sa.Column("ai_model", sa.String(length=80), nullable=True),
        sa.Column("style", sa.String(length=80), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("garment_json", sa.JSON(), nullable=False),
        sa.Column("validation_result", sa.JSON(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("images", sa.JSON(), nullable=False),
        sa.Column("estimated_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("approved", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["card_drafts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["model_id"], ["model_templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generated_image_jobs_user_id", "generated_image_jobs", ["user_id"], unique=False)
    op.create_index("ix_generated_image_jobs_store_id", "generated_image_jobs", ["store_id"], unique=False)
    op.create_index("ix_generated_image_jobs_draft_id", "generated_image_jobs", ["draft_id"], unique=False)
    op.create_index("ix_generated_image_jobs_job_type", "generated_image_jobs", ["job_type"], unique=False)
    op.create_index("ix_generated_image_jobs_status", "generated_image_jobs", ["status"], unique=False)
    op.create_index("ix_generated_image_jobs_model_id", "generated_image_jobs", ["model_id"], unique=False)
    op.create_index("ix_generated_image_jobs_ai_model", "generated_image_jobs", ["ai_model"], unique=False)

    op.create_table(
        "usage_records",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column("operation", sa.String(length=40), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("estimated_cost", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["generated_image_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_usage_records_user_id", "usage_records", ["user_id"], unique=False)
    op.create_index("ix_usage_records_job_id", "usage_records", ["job_id"], unique=False)
    op.create_index("ix_usage_records_provider", "usage_records", ["provider"], unique=False)
    op.create_index("ix_usage_records_model", "usage_records", ["model"], unique=False)
    op.create_index("ix_usage_records_operation", "usage_records", ["operation"], unique=False)
    op.create_index("ix_usage_records_created_at", "usage_records", ["created_at"], unique=False)

    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("admin_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_audit_logs_admin_id", "admin_audit_logs", ["admin_id"], unique=False)
    op.create_index("ix_admin_audit_logs_action", "admin_audit_logs", ["action"], unique=False)
    op.create_index("ix_admin_audit_logs_target_type", "admin_audit_logs", ["target_type"], unique=False)
    op.create_index("ix_admin_audit_logs_target_id", "admin_audit_logs", ["target_id"], unique=False)
    op.create_index("ix_admin_audit_logs_created_at", "admin_audit_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_admin_audit_logs_created_at", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_target_id", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_target_type", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_action", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_admin_id", table_name="admin_audit_logs")
    op.drop_table("admin_audit_logs")

    op.drop_index("ix_usage_records_created_at", table_name="usage_records")
    op.drop_index("ix_usage_records_operation", table_name="usage_records")
    op.drop_index("ix_usage_records_model", table_name="usage_records")
    op.drop_index("ix_usage_records_provider", table_name="usage_records")
    op.drop_index("ix_usage_records_job_id", table_name="usage_records")
    op.drop_index("ix_usage_records_user_id", table_name="usage_records")
    op.drop_table("usage_records")

    op.drop_index("ix_generated_image_jobs_ai_model", table_name="generated_image_jobs")
    op.drop_index("ix_generated_image_jobs_model_id", table_name="generated_image_jobs")
    op.drop_index("ix_generated_image_jobs_status", table_name="generated_image_jobs")
    op.drop_index("ix_generated_image_jobs_job_type", table_name="generated_image_jobs")
    op.drop_index("ix_generated_image_jobs_draft_id", table_name="generated_image_jobs")
    op.drop_index("ix_generated_image_jobs_store_id", table_name="generated_image_jobs")
    op.drop_index("ix_generated_image_jobs_user_id", table_name="generated_image_jobs")
    op.drop_table("generated_image_jobs")

    op.drop_table("admin_ai_settings")

    op.drop_index("ix_model_templates_status", table_name="model_templates")
    op.drop_index("ix_model_templates_body_type", table_name="model_templates")
    op.drop_index("ix_model_templates_gender", table_name="model_templates")
    op.drop_index("ix_model_templates_name", table_name="model_templates")
    op.drop_table("model_templates")

    op.drop_index("ix_users_status", table_name="users")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_column("users", "updated_at")
    op.drop_column("users", "used_quota")
    op.drop_column("users", "monthly_quota")
    op.drop_column("users", "status")
    op.drop_column("users", "role")
