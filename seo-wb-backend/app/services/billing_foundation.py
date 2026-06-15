from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.admin import GeneratedImageJob
from app.models.billing import CreditTransaction, PlatformAuditLog, SubscriptionPlan
from app.models.user import User
from app.services.usage_plans import get_usage_plan, next_quota_reset_after


IMAGE_JOB_QUEUE_HIGH = "image_jobs_high"
IMAGE_JOB_QUEUE_NORMAL = "image_jobs_normal"
IMAGE_JOB_QUEUE_LOW = "image_jobs_low"
IMAGE_JOB_PRIORITY_QUEUES = [IMAGE_JOB_QUEUE_HIGH, IMAGE_JOB_QUEUE_NORMAL, IMAGE_JOB_QUEUE_LOW]


@dataclass(frozen=True)
class SubscriptionPlanSeed:
    code: str
    name: str
    price: float
    currency: str
    monthly_credits: int
    monthly_quota: int
    monthly_card_quota: int
    monthly_cost_limit: float | None
    max_images_per_job: int
    allow_legacy_vton: bool
    allow_gpt_image: bool
    priority_queue: bool


SUBSCRIPTION_PLAN_SEEDS = [
    SubscriptionPlanSeed(
        code="free",
        name="Free",
        price=0.0,
        currency="USD",
        monthly_credits=30,
        monthly_quota=30,
        monthly_card_quota=10,
        monthly_cost_limit=5.0,
        max_images_per_job=4,
        allow_legacy_vton=False,
        allow_gpt_image=True,
        priority_queue=False,
    ),
    SubscriptionPlanSeed(
        code="pro",
        name="Pro",
        price=29.0,
        currency="USD",
        monthly_credits=500,
        monthly_quota=500,
        monthly_card_quota=50,
        monthly_cost_limit=50.0,
        max_images_per_job=8,
        allow_legacy_vton=True,
        allow_gpt_image=True,
        priority_queue=False,
    ),
    SubscriptionPlanSeed(
        code="agency",
        name="Agency",
        price=149.0,
        currency="USD",
        monthly_credits=3000,
        monthly_quota=3000,
        monthly_card_quota=500,
        monthly_cost_limit=300.0,
        max_images_per_job=12,
        allow_legacy_vton=True,
        allow_gpt_image=True,
        priority_queue=True,
    ),
]

SUBSCRIPTION_PLAN_BY_CODE = {plan.code: plan for plan in SUBSCRIPTION_PLAN_SEEDS}


def monthly_credits_for_plan(plan_type: str | None) -> int:
    return SUBSCRIPTION_PLAN_BY_CODE[get_usage_plan(plan_type).plan_type].monthly_credits


def queue_name_for_plan(plan_type: str | None) -> str:
    normalized = get_usage_plan(plan_type).plan_type
    if normalized == "agency":
        return IMAGE_JOB_QUEUE_HIGH
    if normalized == "pro":
        return IMAGE_JOB_QUEUE_NORMAL
    return IMAGE_JOB_QUEUE_LOW


def credit_cost_for_job(job_type: str, quantity: int) -> int:
    total = max(1, int(quantity or 1))
    if job_type == "try_on":
        return total * 2
    if job_type in {"gpt_image", "gpt_image_openai"}:
        return total
    return total


def ensure_subscription_plan_seeds(db: Session) -> None:
    existing = {
        row.code: row
        for row in db.scalars(select(SubscriptionPlan).where(SubscriptionPlan.code.in_(list(SUBSCRIPTION_PLAN_BY_CODE)))).all()
    }
    changed = False
    for plan_seed in SUBSCRIPTION_PLAN_SEEDS:
        row = existing.get(plan_seed.code)
        payload = {
            "name": plan_seed.name,
            "price": plan_seed.price,
            "currency": plan_seed.currency,
            "monthly_credits": plan_seed.monthly_credits,
            "monthly_quota": plan_seed.monthly_quota,
            "monthly_card_quota": plan_seed.monthly_card_quota,
            "monthly_cost_limit": plan_seed.monthly_cost_limit,
            "max_images_per_job": plan_seed.max_images_per_job,
            "allow_legacy_vton": plan_seed.allow_legacy_vton,
            "allow_gpt_image": plan_seed.allow_gpt_image,
            "priority_queue": plan_seed.priority_queue,
            "is_active": True,
        }
        if row is None:
            db.add(SubscriptionPlan(code=plan_seed.code, **payload))
            changed = True
            continue
        for key, value in payload.items():
            if getattr(row, key) != value:
                setattr(row, key, value)
                changed = True
    if changed:
        db.commit()


def initialize_user_credits(user: User) -> None:
    if int(getattr(user, "credits_granted", 0) or 0) > 0:
        return
    monthly_credits = monthly_credits_for_plan(getattr(user, "plan_type", None))
    user.credit_balance = monthly_credits
    user.credits_granted = monthly_credits
    user.credits_used = 0


def reset_user_usage_and_credits(db: Session, user: User, *, actor_type: str = "system", actor_id: str | None = None) -> None:
    now = datetime.now(timezone.utc)
    monthly_credits = monthly_credits_for_plan(user.plan_type)
    previous_quota = int(user.used_quota or 0)
    previous_cost = float(user.used_cost or 0.0)
    previous_balance = int(user.credit_balance or 0)
    user.used_quota = 0
    user.used_cost = 0.0
    user.credits_used = 0
    user.credit_balance = monthly_credits
    user.credits_granted = max(0, int(user.credits_granted or 0)) + monthly_credits
    user.last_quota_reset_at = now
    user.quota_reset_at = next_quota_reset_after(now)
    db.add(
        CreditTransaction(
            id=uuid4().hex,
            user_id=user.id,
            job_id=None,
            transaction_type="monthly_reset",
            credits=monthly_credits,
            balance_after=user.credit_balance,
            description="Monthly credit reset",
            metadata_json={"previous_balance": previous_balance},
        )
    )
    log_platform_audit(
        db,
        action="MONTHLY_USAGE_RESET",
        target_type="user",
        target_id=str(user.id),
        metadata={
            "previous_used_quota": previous_quota,
            "previous_used_cost": round(previous_cost, 4),
            "new_credit_balance": user.credit_balance,
            "actor_type": actor_type,
            "actor_id": actor_id,
        },
        actor_type=actor_type,
        actor_id=actor_id,
    )


def log_platform_audit(
    db: Session,
    *,
    action: str,
    target_type: str,
    target_id: str | None,
    metadata: dict,
    actor_type: str = "system",
    actor_id: str | None = None,
) -> None:
    db.add(
        PlatformAuditLog(
            id=uuid4().hex,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_json=metadata,
        )
    )


def pending_credit_reservations(db: Session, user_id: int) -> int:
    pending_statuses = ("pending", "running")
    rows = db.scalars(
        select(GeneratedImageJob).where(
            GeneratedImageJob.user_id == user_id,
            GeneratedImageJob.status.in_(pending_statuses),
        )
    ).all()
    return sum(max(0, int(row.credit_cost or 0)) for row in rows)


def record_credit_transaction(
    db: Session,
    *,
    user: User,
    transaction_type: str,
    credits: int,
    balance_after: int,
    job_id: str | None = None,
    description: str | None = None,
    metadata: dict | None = None,
) -> None:
    db.add(
        CreditTransaction(
            id=uuid4().hex,
            user_id=user.id,
            job_id=job_id,
            transaction_type=transaction_type,
            credits=credits,
            balance_after=balance_after,
            description=description,
            metadata_json=metadata or {},
        )
    )
