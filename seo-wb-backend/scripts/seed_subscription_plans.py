from __future__ import annotations

from app.db.session import SessionLocal
from app.services.billing_foundation import ensure_subscription_plan_seeds


def main() -> None:
    with SessionLocal() as db:
        ensure_subscription_plan_seeds(db)
        print("seeded subscription plans: free, pro, agency")


if __name__ == "__main__":
    main()
