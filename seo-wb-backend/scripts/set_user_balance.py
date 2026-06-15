from __future__ import annotations

import argparse

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.user import User
from app.services.usage_plans import get_usage_plan, normalize_plan_type


def main() -> None:
    parser = argparse.ArgumentParser(description="Set prepaid card/image balances for one user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--plan", default=None, help="Optional plan: free, basic, plus, premium")
    parser.add_argument("--remaining-cards", type=int, required=True)
    parser.add_argument("--remaining-images", type=int, required=True)
    args = parser.parse_args()

    if args.remaining_cards < 0 or args.remaining_images < 0:
        raise SystemExit("remaining cards/images must be >= 0")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == args.email.lower(), User.deleted_at.is_(None)))
        if not user:
            raise SystemExit(f"user not found: {args.email}")

        if args.plan:
            plan = get_usage_plan(normalize_plan_type(args.plan))
            user.plan_type = plan.plan_type
            user.monthly_cost_limit = plan.monthly_cost_limit

        used_cards = max(0, int(user.used_quota or 0))
        used_images = max(0, int(user.credits_used or 0))

        user.monthly_quota = used_cards + args.remaining_cards
        user.credit_balance = args.remaining_images
        user.credits_granted = max(int(user.credits_granted or 0), used_images + args.remaining_images)
        db.commit()
        print(
            f"updated {user.email}: plan={user.plan_type}, "
            f"remaining_cards={args.remaining_cards}, remaining_images={args.remaining_images}"
        )


if __name__ == "__main__":
    main()
