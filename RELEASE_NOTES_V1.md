# AI Product Studio V1

Release date: 2026-06-03

## Core Features

- User authentication, store connection, and card workflow
- GPT-Image Catalog generation
- Legacy VTON
- `garment_json` validation support
- Admin panel
- Model approval workflow
- Quota and cost controls
- Credit foundation
- Usage reset scheduler
- Priority queues
- Marketplace export

## Verification Summary

- Docker build passed
- `alembic upgrade head` passed
- Backend tests: `37 passed`
- Frontend lint and production build passed

## Known Limitations

- Billing schema exists, but Stripe and Momo are not integrated yet
- Image realism still depends heavily on model template quality
- Full browser click-through verification has not been fully automated

## Deploy Commands

```powershell
cd c:\Users\admin\seo-wb
docker compose config
docker compose up -d --build backend worker finance-worker finance-scheduler usage-reset-scheduler frontend
docker compose exec -T backend alembic upgrade head
```

## Seed Commands

Seed admin:

```powershell
cd c:\Users\admin\seo-wb
docker compose exec -T backend sh -lc "cd /app && PYTHONPATH=/app python scripts/create_admin.py --email admin@seo.com --password 12345678 --name Admin --role super_admin --plan-type agency"
```

Seed subscription plans:

```powershell
cd c:\Users\admin\seo-wb
docker compose exec -T backend sh -lc "cd /app && PYTHONPATH=/app python scripts/seed_subscription_plans.py"
```

## Rollback Notes

- Roll back containers by redeploying the previous backend and frontend images
- Take a database backup before rolling back schema changes
- Level 3 adds billing, credits, and queue metadata; schema rollback should be planned carefully
- Re-seed subscription plans after restore if plan rows are missing or stale
