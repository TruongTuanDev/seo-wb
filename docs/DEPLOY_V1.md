# Deploy V1

## Required Environment Variables

Backend:
- `APP_SECRET_KEY`
- `DATABASE_URL` or Docker default Postgres wiring
- `OPENAI_API_KEY`
- `FAL_KEY`
- `REDIS_URL` or `REDIS_HOST` plus optional auth fields
- `POSTGRES_PASSWORD` when using Docker Compose

Frontend:
- `NEXT_PUBLIC_API_URL`

Optional but recommended:
- `COOKIE_SECURE`
- `COOKIE_DOMAIN`
- `CORS_ALLOW_ORIGINS`

## Build And Start

```powershell
cd c:\Users\admin\seo-wb
docker compose up -d --build backend worker finance-worker finance-scheduler usage-reset-scheduler frontend
```

## Run Migrations

```powershell
cd c:\Users\admin\seo-wb
docker compose exec -T backend alembic upgrade head
```

## Seed Admin User

```powershell
cd c:\Users\admin\seo-wb
docker compose exec -T backend sh -lc "cd /app && PYTHONPATH=/app python scripts/create_admin.py --email admin@seo.com --password 12345678 --name Admin --role super_admin --plan-type agency"
```

## Seed Subscription Plans

```powershell
cd c:\Users\admin\seo-wb
docker compose exec -T backend sh -lc "cd /app && PYTHONPATH=/app python scripts/seed_subscription_plans.py"
```

## Health Checks

- Backend health: `http://localhost:8081/health`
- Frontend: `http://localhost:3030`
- Admin login: `http://localhost:3030/admin/login`

## Service Checks

Check runtime:

```powershell
docker compose ps
```

Check worker logs:

```powershell
docker compose logs --tail=100 worker
docker compose logs --tail=100 finance-worker
docker compose logs --tail=100 finance-scheduler
docker compose logs --tail=100 usage-reset-scheduler
```

## Test Commands

```powershell
cd c:\Users\admin\seo-wb
docker compose exec -T backend python -m pytest tests/test_admin_integration.py tests/test_product_image_generation.py tests/test_auth_security.py tests/test_admin_routes.py
```

## Rollback Notes

- Roll back app containers by redeploying the previous backend and frontend images.
- Roll back schema only with care; Level 3 adds billing and credit tables plus usage fields.
- If you must roll back migrations, take a database backup first.
- Clear stuck image jobs from Redis queues only after confirming no worker is processing them.
- Re-seed subscription plans after rollback or restore if plan rows are missing or outdated.
