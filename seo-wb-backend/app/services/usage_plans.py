from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.errors import AppError


@dataclass(frozen=True)
class UsagePlan:
    plan_type: str
    name: str
    price_rub: int
    monthly_credits: int
    monthly_quota: int
    monthly_cost_limit: float | None
    max_images_per_job: int
    allow_legacy_vton: bool
    allow_gpt_image: bool
    priority_queue: bool


FREE_PLAN = UsagePlan(
    plan_type="free",
    name="Free",
    price_rub=0,
    monthly_credits=9,
    monthly_quota=3,
    monthly_cost_limit=None,
    max_images_per_job=8,
    allow_legacy_vton=False,
    allow_gpt_image=True,
    priority_queue=False,
)

BASIC_PLAN = UsagePlan(
    plan_type="basic",
    name="Basic",
    price_rub=3000,
    monthly_credits=60,
    monthly_quota=10,
    monthly_cost_limit=None,
    max_images_per_job=8,
    allow_legacy_vton=True,
    allow_gpt_image=True,
    priority_queue=False,
)

PLUS_PLAN = UsagePlan(
    plan_type="plus",
    name="Plus",
    price_rub=5500,
    monthly_credits=120,
    monthly_quota=20,
    monthly_cost_limit=None,
    max_images_per_job=8,
    allow_legacy_vton=True,
    allow_gpt_image=True,
    priority_queue=True,
)

PREMIUM_PLAN = UsagePlan(
    plan_type="premium",
    name="Premium",
    price_rub=8000,
    monthly_credits=180,
    monthly_quota=30,
    monthly_cost_limit=None,
    max_images_per_job=8,
    allow_legacy_vton=True,
    allow_gpt_image=True,
    priority_queue=True,
)

USAGE_PLANS: dict[str, UsagePlan] = {
    FREE_PLAN.plan_type: FREE_PLAN,
    BASIC_PLAN.plan_type: BASIC_PLAN,
    PLUS_PLAN.plan_type: PLUS_PLAN,
    PREMIUM_PLAN.plan_type: PREMIUM_PLAN,
}

PLAN_ALIASES = {
    "pro": "plus",
    "agency": "premium",
}


def normalize_plan_type(value: str | None) -> str:
    plan_type = (value or FREE_PLAN.plan_type).strip().lower()
    plan_type = PLAN_ALIASES.get(plan_type, plan_type)
    if plan_type not in USAGE_PLANS:
        raise AppError("invalid_plan_type", "Plan type must be free, basic, plus, or premium.", 400)
    return plan_type


def _plan_from_row(row) -> UsagePlan:
    return UsagePlan(
        plan_type=row.code,
        name=row.name,
        price_rub=int(round(float(row.price or 0))),
        monthly_credits=int(row.monthly_credits or 0),
        monthly_quota=int(row.monthly_quota or 0),
        monthly_cost_limit=row.monthly_cost_limit,
        max_images_per_job=int(row.max_images_per_job or 1),
        allow_legacy_vton=bool(row.allow_legacy_vton),
        allow_gpt_image=bool(row.allow_gpt_image),
        priority_queue=bool(row.priority_queue),
    )


def get_usage_plan(plan_type: str | None, db=None) -> UsagePlan:
    """Resolve a plan. When a DB session is given, the editable DB row is the
    source of truth (admin edits take effect); otherwise fall back to the
    hardcoded defaults."""
    code = normalize_plan_type(plan_type)
    if db is not None:
        try:
            from sqlalchemy import select

            from app.models.billing import SubscriptionPlan

            row = db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.code == code))
            if row is not None:
                return _plan_from_row(row)
        except Exception:
            pass
    return USAGE_PLANS[code]


def next_quota_reset_after(reference: datetime | None = None) -> datetime:
    current = reference.astimezone(timezone.utc) if reference else datetime.now(timezone.utc)
    if current.month == 12:
        return current.replace(year=current.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return current.replace(month=current.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)


def apply_plan_defaults(user, plan_type: str | None = None, *, reference: datetime | None = None, db=None) -> UsagePlan:
    plan = get_usage_plan(plan_type or getattr(user, "plan_type", None), db=db)
    user.plan_type = plan.plan_type
    user.monthly_quota = plan.monthly_quota
    user.monthly_cost_limit = plan.monthly_cost_limit
    if getattr(user, "quota_reset_at", None) is None:
        user.quota_reset_at = None
    if getattr(user, "last_quota_reset_at", None) is None:
        user.last_quota_reset_at = None
    try:
        from app.services.billing_foundation import initialize_user_credits

        initialize_user_credits(user, db=db)
    except Exception:
        pass
    return plan


def reset_usage_cycle(user, *, reference: datetime | None = None, db=None) -> datetime:
    now = reference.astimezone(timezone.utc) if reference else datetime.now(timezone.utc)
    user.used_quota = 0
    user.used_cost = 0.0
    try:
        monthly_credits = get_usage_plan(getattr(user, "plan_type", None), db=db).monthly_credits
        user.credit_balance = monthly_credits
        user.credits_used = 0
        user.credits_granted = max(0, int(getattr(user, "credits_granted", 0) or 0)) + monthly_credits
    except Exception:
        pass
    user.last_quota_reset_at = now
    user.quota_reset_at = next_quota_reset_after(now)
    return now


def reset_usage_if_due(user, *, reference: datetime | None = None, db=None) -> bool:
    now = reference.astimezone(timezone.utc) if reference else datetime.now(timezone.utc)
    if getattr(user, "quota_reset_at", None) is None and getattr(user, "last_quota_reset_at", None) is None:
        if int(getattr(user, "credits_granted", 0) or 0) == 0:
            try:
                from app.services.billing_foundation import initialize_user_credits

                initialize_user_credits(user, db=db)
                return True
            except Exception:
                return False
        return False
    if int(getattr(user, "credits_granted", 0) or 0) == 0:
        try:
            from app.services.billing_foundation import initialize_user_credits

            initialize_user_credits(user, db=db)
        except Exception:
            pass
    quota_reset_at = getattr(user, "quota_reset_at", None)
    if quota_reset_at is None:
        return False
    quota_reset_at_utc = quota_reset_at.astimezone(timezone.utc) if quota_reset_at.tzinfo else quota_reset_at.replace(tzinfo=timezone.utc)
    if quota_reset_at_utc <= now:
        reset_usage_cycle(user, reference=now, db=db)
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
