"""usage level3 foundation

Revision ID: 20260603_0008
Revises: 20260603_0007
Create Date: 2026-06-03 18:15:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260603_0008"
down_revision = "20260603_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("credit_balance", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("credits_used", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("credits_granted", sa.Integer(), nullable=False, server_default="0"))

    op.add_column("generated_image_jobs", sa.Column("credit_cost", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("generated_image_jobs", sa.Column("queue_name", sa.String(length=32), nullable=False, server_default="image_jobs_normal"))
    op.add_column("generated_image_jobs", sa.Column("credits_consumed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_generated_image_jobs_queue_name", "generated_image_jobs", ["queue_name"])

    op.create_table(
        "subscription_plans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("monthly_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("monthly_quota", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("monthly_cost_limit", sa.Float(), nullable=True),
        sa.Column("max_images_per_job", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("allow_legacy_vton", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("allow_gpt_image", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("priority_queue", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_subscription_plans_code", "subscription_plans", ["code"], unique=True)

    op.create_table(
        "user_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("subscription_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_user_subscriptions_user_id", "user_subscriptions", ["user_id"])
    op.create_index("ix_user_subscriptions_plan_id", "user_subscriptions", ["plan_id"])
    op.create_index("ix_user_subscriptions_status", "user_subscriptions", ["status"])

    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("user_subscriptions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=120), nullable=True),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_payment_transactions_user_id", "payment_transactions", ["user_id"])
    op.create_index("ix_payment_transactions_subscription_id", "payment_transactions", ["subscription_id"])
    op.create_index("ix_payment_transactions_provider", "payment_transactions", ["provider"])
    op.create_index("ix_payment_transactions_provider_payment_id", "payment_transactions", ["provider_payment_id"])
    op.create_index("ix_payment_transactions_status", "payment_transactions", ["status"])

    op.create_table(
        "credit_transactions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.String(length=64), sa.ForeignKey("generated_image_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("transaction_type", sa.String(length=20), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("balance_after", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_credit_transactions_user_id", "credit_transactions", ["user_id"])
    op.create_index("ix_credit_transactions_job_id", "credit_transactions", ["job_id"])
    op.create_index("ix_credit_transactions_transaction_type", "credit_transactions", ["transaction_type"])
    op.create_index("ix_credit_transactions_created_at", "credit_transactions", ["created_at"])

    op.create_table(
        "platform_audit_logs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("actor_type", sa.String(length=20), nullable=False, server_default="system"),
        sa.Column("actor_id", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_platform_audit_logs_actor_type", "platform_audit_logs", ["actor_type"])
    op.create_index("ix_platform_audit_logs_actor_id", "platform_audit_logs", ["actor_id"])
    op.create_index("ix_platform_audit_logs_action", "platform_audit_logs", ["action"])
    op.create_index("ix_platform_audit_logs_target_type", "platform_audit_logs", ["target_type"])
    op.create_index("ix_platform_audit_logs_target_id", "platform_audit_logs", ["target_id"])
    op.create_index("ix_platform_audit_logs_created_at", "platform_audit_logs", ["created_at"])

    op.execute(
        """
        INSERT INTO subscription_plans
            (code, name, price, currency, monthly_credits, monthly_quota, monthly_cost_limit, max_images_per_job, allow_legacy_vton, allow_gpt_image, priority_queue, is_active)
        VALUES
            ('free', 'Free', 0, 'USD', 30, 30, 5, 4, false, true, false, true),
            ('pro', 'Pro', 29, 'USD', 500, 500, 50, 8, true, true, false, true),
            ('agency', 'Agency', 149, 'USD', 3000, 3000, 300, 12, true, true, true, true)
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE users
        SET
            credit_balance = CASE plan_type WHEN 'agency' THEN 3000 WHEN 'pro' THEN 500 ELSE 30 END,
            credits_granted = CASE plan_type WHEN 'agency' THEN 3000 WHEN 'pro' THEN 500 ELSE 30 END,
            credits_used = 0
        WHERE credit_balance = 0 AND credits_granted = 0
        """
    )

    op.alter_column("users", "credit_balance", server_default=None)
    op.alter_column("users", "credits_used", server_default=None)
    op.alter_column("users", "credits_granted", server_default=None)
    op.alter_column("generated_image_jobs", "credit_cost", server_default=None)
    op.alter_column("generated_image_jobs", "queue_name", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_platform_audit_logs_created_at", table_name="platform_audit_logs")
    op.drop_index("ix_platform_audit_logs_target_id", table_name="platform_audit_logs")
    op.drop_index("ix_platform_audit_logs_target_type", table_name="platform_audit_logs")
    op.drop_index("ix_platform_audit_logs_action", table_name="platform_audit_logs")
    op.drop_index("ix_platform_audit_logs_actor_id", table_name="platform_audit_logs")
    op.drop_index("ix_platform_audit_logs_actor_type", table_name="platform_audit_logs")
    op.drop_table("platform_audit_logs")

    op.drop_index("ix_credit_transactions_created_at", table_name="credit_transactions")
    op.drop_index("ix_credit_transactions_transaction_type", table_name="credit_transactions")
    op.drop_index("ix_credit_transactions_job_id", table_name="credit_transactions")
    op.drop_index("ix_credit_transactions_user_id", table_name="credit_transactions")
    op.drop_table("credit_transactions")

    op.drop_index("ix_payment_transactions_status", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_provider_payment_id", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_provider", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_subscription_id", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_user_id", table_name="payment_transactions")
    op.drop_table("payment_transactions")

    op.drop_index("ix_user_subscriptions_status", table_name="user_subscriptions")
    op.drop_index("ix_user_subscriptions_plan_id", table_name="user_subscriptions")
    op.drop_index("ix_user_subscriptions_user_id", table_name="user_subscriptions")
    op.drop_table("user_subscriptions")

    op.drop_index("ix_subscription_plans_code", table_name="subscription_plans")
    op.drop_table("subscription_plans")

    op.drop_index("ix_generated_image_jobs_queue_name", table_name="generated_image_jobs")
    op.drop_column("generated_image_jobs", "credits_consumed_at")
    op.drop_column("generated_image_jobs", "queue_name")
    op.drop_column("generated_image_jobs", "credit_cost")

    op.drop_column("users", "credits_granted")
    op.drop_column("users", "credits_used")
    op.drop_column("users", "credit_balance")
