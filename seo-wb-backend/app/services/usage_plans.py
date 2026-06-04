from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.errors import AppError


@dataclass(frozen=True)
class UsagePlan:
    plan_type: str
    monthly_quota: int
    monthly_cost_limit: float | None
    max_images_per_job: int
    allow_legacy_vton: bool
    allow_gpt_image: bool
    priority_queue: bool


FREE_PLAN = UsagePlan(
    plan_type="free",
    monthly_quota=30,
    monthly_cost_limit=5.0,
    max_images_per_job=4,
    allow_legacy_vton=False,
    allow_gpt_image=True,
    priority_queue=False,
)

PRO_PLAN = UsagePlan(
    plan_type="pro",
    monthly_quota=500,
    monthly_cost_limit=50.0,
    max_images_per_job=8,
    allow_legacy_vton=True,
    allow_gpt_image=True,
    priority_queue=False,
)

AGENCY_PLAN = UsagePlan(
    plan_type="agency",
    monthly_quota=3000,
    monthly_cost_limit=300.0,
    max_images_per_job=12,
    allow_legacy_vton=True,
    allow_gpt_image=True,
    priority_queue=True,
)

USAGE_PLANS: dict[str, UsagePlan] = {
    FREE_PLAN.plan_type: FREE_PLAN,
    PRO_PLAN.plan_type: PRO_PLAN,
    AGENCY_PLAN.plan_type: AGENCY_PLAN,
}


def normalize_plan_type(value: str | None) -> str:
    plan_type = (value or FREE_PLAN.plan_type).strip().lower()
    if plan_type not in USAGE_PLANS:
        raise AppError("invalid_plan_type", "Plan type must be free, pro, or agency.", 400)
    return plan_type


def get_usage_plan(plan_type: str | None) -> UsagePlan:
    return USAGE_PLANS[normalize_plan_type(plan_type)]


def next_quota_reset_after(reference: datetime | None = None) -> datetime:
    current = reference.astimezone(timezone.utc) if reference else datetime.now(timezone.utc)
    if current.month == 12:
        return current.replace(year=current.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return current.replace(month=current.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)


def apply_plan_defaults(user, plan_type: str | None = None, *, reference: datetime | None = None) -> UsagePlan:
    plan = get_usage_plan(plan_type or getattr(user, "plan_type", None))
    user.plan_type = plan.plan_type
    user.monthly_quota = plan.monthly_quota
    user.monthly_cost_limit = plan.monthly_cost_limit
    now = reference.astimezone(timezone.utc) if reference else datetime.now(timezone.utc)
    if getattr(user, "quota_reset_at", None) is None:
        user.quota_reset_at = next_quota_reset_after(now)
    if getattr(user, "last_quota_reset_at", None) is None:
        user.last_quota_reset_at = now
    try:
        from app.services.billing_foundation import initialize_user_credits

        initialize_user_credits(user)
    except Exception:
        pass
    return plan


def reset_usage_cycle(user, *, reference: datetime | None = None) -> datetime:
    now = reference.astimezone(timezone.utc) if reference else datetime.now(timezone.utc)
    user.used_quota = 0
    user.used_cost = 0.0
    try:
        from app.services.billing_foundation import monthly_credits_for_plan

        monthly_credits = monthly_credits_for_plan(getattr(user, "plan_type", None))
        user.credit_balance = monthly_credits
        user.credits_used = 0
        user.credits_granted = max(0, int(getattr(user, "credits_granted", 0) or 0)) + monthly_credits
    except Exception:
        pass
    user.last_quota_reset_at = now
    user.quota_reset_at = next_quota_reset_after(now)
    return now


def reset_usage_if_due(user, *, reference: datetime | None = None) -> bool:
    now = reference.astimezone(timezone.utc) if reference else datetime.now(timezone.utc)
    if getattr(user, "quota_reset_at", None) is None and getattr(user, "last_quota_reset_at", None) is None:
        apply_plan_defaults(user, getattr(user, "plan_type", None), reference=now)
        return True
    if int(getattr(user, "credits_granted", 0) or 0) == 0:
        try:
            from app.services.billing_foundation import initialize_user_credits

            initialize_user_credits(user)
        except Exception:
            pass
    quota_reset_at = getattr(user, "quota_reset_at", None)
    if quota_reset_at is None:
        user.quota_reset_at = next_quota_reset_after(now)
        return True
    quota_reset_at_utc = quota_reset_at.astimezone(timezone.utc) if quota_reset_at.tzinfo else quota_reset_at.replace(tzinfo=timezone.utc)
    if quota_reset_at_utc <= now:
        reset_usage_cycle(user, reference=now)
        return True
    return False


def quota_ratio(user) -> float:
    quota = max(0, int(getattr(user, "monthly_quota", 0) or 0))
    used = max(0, int(getattr(user, "used_quota", 0) or 0))
    return (used / quota) if quota > 0 else 0.0


def cost_ratio(user) -> float:
    cost_limit = getattr(user, "monthly_cost_limit", None)
    if cost_limit is None or float(cost_limit) <= 0:
        return 0.0
    return float(getattr(user, "used_cost", 0.0) or 0.0) / float(cost_limit)
