from __future__ import annotations


CHECKS = [
    "cd c:\\Users\\admin\\seo-wb",
    "docker compose config",
    "docker compose up -d --build backend worker finance-worker finance-scheduler usage-reset-scheduler frontend",
    "docker compose exec -T backend alembic upgrade head",
    "docker compose exec -T backend python -m pytest tests/test_admin_integration.py tests/test_product_image_generation.py tests/test_auth_security.py tests/test_admin_routes.py -q",
    "docker compose exec -T backend sh -lc \"cd /app && PYTHONPATH=/app python scripts/seed_subscription_plans.py\"",
    "Open backend health: http://localhost:8081/health",
    "Open frontend: http://localhost:3030",
    "Check worker logs: docker compose logs --tail=100 worker",
    "Check scheduler logs: docker compose logs --tail=100 usage-reset-scheduler",
]


def main() -> None:
    print("AI Product Studio V1 release verification checklist")
    print()
    for index, command in enumerate(CHECKS, start=1):
        print(f"{index}. {command}")


if __name__ == "__main__":
    main()
