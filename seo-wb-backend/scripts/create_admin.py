from __future__ import annotations

import argparse

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User
from app.services.usage_plans import apply_plan_defaults


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or update an admin account.")
    parser.add_argument("--email", required=True, help="Admin email")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument("--name", default="Admin", help="Display name")
    parser.add_argument("--role", choices=["admin", "super_admin"], default="admin", help="Admin role")
    parser.add_argument("--status", choices=["active", "suspended"], default="active", help="Account status")
    parser.add_argument("--plan-type", choices=["free", "pro", "agency"], default="agency", help="Usage plan")
    parser.add_argument("--monthly-quota", type=int, default=None, help="Optional monthly generation quota override")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == args.email.lower()))
        if user is None:
            user = User(
                name=args.name,
                email=args.email.lower(),
                password_hash=hash_password(args.password),
                role=args.role,
                status=args.status,
            )
            apply_plan_defaults(user, args.plan_type)
            if args.monthly_quota is not None:
                user.monthly_quota = max(0, args.monthly_quota)
            user.used_quota = 0
            db.add(user)
            action = "created"
        else:
            user.name = args.name
            user.password_hash = hash_password(args.password)
            user.role = args.role
            user.status = args.status
            apply_plan_defaults(user, args.plan_type)
            if args.monthly_quota is not None:
                user.monthly_quota = max(0, args.monthly_quota)
            action = "updated"
        db.commit()
        db.refresh(user)
        print(f"{action}: id={user.id} email={user.email} role={user.role} status={user.status}")


if __name__ == "__main__":
    main()
