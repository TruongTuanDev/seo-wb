from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
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
        user.quota_reset_at = None
    db.commit()
    return 0
