from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.billing_foundation import reset_user_usage_and_credits


def run_monthly_usage_reset_cycle(db: Session) -> int:
    now = datetime.now(timezone.utc)
    due_users = db.scalars(
        select(User).where(
            User.deleted_at.is_(None),
            User.quota_reset_at.is_not(None),
            User.quota_reset_at <= now,
        )
    ).all()
    if not due_users:
        return 0
    for user in due_users:
        reset_user_usage_and_credits(db, user, actor_type="system", actor_id="usage-reset-scheduler")
    db.commit()
    return len(due_users)
