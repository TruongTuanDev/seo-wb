# Deploy V1

Tai lieu nay dung cho monorepo hien tai khi deploy toan bo du an len mot VPS bang Docker Compose.

## 1. Thanh phan se chay tren VPS

- `db`: PostgreSQL
- `redis`: queue va cache cho image jobs, finance jobs
- `rabbitmq`: publisher cho `card.push`
- `backend`: FastAPI + tu dong chay migration khi start
- `worker`: image generation worker
- `sync-worker`: RabbitMQ consumer cho `card.push`, `product.sync`, `finance.sync`
- `finance-worker`: finance queue consumer
- `finance-scheduler`: finance nightly scheduler
- `usage-reset-scheduler`: reset usage hang thang
- `frontend`: Next.js production server

Compose production nam o [docker-compose.production.yml](/c:/Users/admin/seo-wb/docker-compose.production.yml).

## 2. File can chuan bi

Tu root repo:

```bash
cp deploy/env/compose.env.example deploy/env/compose.env
cp deploy/env/backend.env.example deploy/env/backend.env
```

Neu muon lay cau hinh tu may local cho nhanh, dung script:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sync-production-env.ps1 `
  -AppDomain "app.tenmien.com" `
  -ApiDomain "api.tenmien.com" `
  -CookieDomain ".tenmien.com" `
  -KeepExistingSecrets
```

Script se:

- doc [seo-wb-backend/.env](/c:/Users/admin/seo-wb/seo-wb-backend/.env)
- sinh lai [deploy/env/backend.env](/c:/Users/admin/seo-wb/deploy/env/backend.env)
- sinh lai [deploy/env/compose.env](/c:/Users/admin/seo-wb/deploy/env/compose.env)
- ep cac gia tri production-safe nhu `APP_ENV=production`, `COOKIE_SECURE=true`, `NEXT_PUBLIC_API_URL=https://api...`

`-KeepExistingSecrets` giu lai password/secrets dang co trong `deploy/env/*.env` neu ban da chinh truoc do.

Can dien it nhat:

### `deploy/env/compose.env`

- `POSTGRES_PASSWORD`
- `RABBITMQ_PASSWORD`
- `NEXT_PUBLIC_API_URL`
- Neu reverse proxy tren cung VPS: giu
  - `BACKEND_BIND_ADDRESS=127.0.0.1`
  - `FRONTEND_BIND_ADDRESS=127.0.0.1`

### `deploy/env/backend.env`

- `APP_SECRET_KEY`
- `ENCRYPTION_KEY`
- `CORS_ALLOW_ORIGINS=https://app.ten-mien-cua-ban`
- `COOKIE_DOMAIN=.ten-mien-cua-ban`
- `COOKIE_SECURE=true`
- `OPENAI_API_KEY` va/hoac `GEMINI_API_KEY`
- `CLOUDINARY_*` neu can luu media len Cloudinary

Generate secret:

```bash
openssl rand -hex 32
```

Neu ban dang co gia tri dung trong [seo-wb-backend/.env](/c:/Users/admin/seo-wb/seo-wb-backend/.env), copy thu cong cac secret can thiet sang `deploy/env/backend.env`. Khong copy file local `.env` len server nguyen xi.

## 3. Chuan bi VPS

Vi du Ubuntu:

```bash
sudo apt update
sudo apt install -y git docker.io docker-compose-plugin nginx certbot python3-certbot-nginx
sudo systemctl enable --now docker
sudo mkdir -p /opt/seo-wb
sudo chown -R $USER:$USER /opt/seo-wb
git clone <repo-url> /opt/seo-wb
cd /opt/seo-wb
```

Neu server su dung user khac `root`, them user vao group docker:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

## 4. Deploy lan dau

```bash
cd /opt/seo-wb
cp deploy/env/compose.env.example deploy/env/compose.env
cp deploy/env/backend.env.example deploy/env/backend.env
nano deploy/env/compose.env
nano deploy/env/backend.env
bash deploy/vps-deploy.sh
```

Script deploy nam o [deploy/vps-deploy.sh](/c:/Users/admin/seo-wb/deploy/vps-deploy.sh).

## 5. Reverse proxy bang Nginx

File mau nam o [deploy/nginx/seo-wb.conf.example](/c:/Users/admin/seo-wb/deploy/nginx/seo-wb.conf.example).

Copy len Nginx host:

```bash
sudo cp deploy/nginx/seo-wb.conf.example /etc/nginx/sites-available/seo-wb.conf
sudo nano /etc/nginx/sites-available/seo-wb.conf
sudo ln -s /etc/nginx/sites-available/seo-wb.conf /etc/nginx/sites-enabled/seo-wb.conf
sudo nginx -t
sudo systemctl reload nginx
```

Sau do cap SSL:

```bash
sudo certbot --nginx -d app.your-domain.com -d api.your-domain.com
```

## 6. Lenh van hanh can dung

Trang thai container:

```bash
docker compose --env-file deploy/env/compose.env -f docker-compose.production.yml ps
```

Xem log:

```bash
docker compose --env-file deploy/env/compose.env -f docker-compose.production.yml logs --tail=100 backend
docker compose --env-file deploy/env/compose.env -f docker-compose.production.yml logs --tail=100 worker
docker compose --env-file deploy/env/compose.env -f docker-compose.production.yml logs --tail=100 sync-worker
docker compose --env-file deploy/env/compose.env -f docker-compose.production.yml logs --tail=100 finance-worker
docker compose --env-file deploy/env/compose.env -f docker-compose.production.yml logs --tail=100 finance-scheduler
docker compose --env-file deploy/env/compose.env -f docker-compose.production.yml logs --tail=100 usage-reset-scheduler
docker compose --env-file deploy/env/compose.env -f docker-compose.production.yml logs --tail=100 frontend
```

Tao admin:

```bash
docker compose --env-file deploy/env/compose.env -f docker-compose.production.yml exec -T backend \
  sh -lc "cd /app && PYTHONPATH=/app python scripts/create_admin.py --email admin@seo.com --password 'doi-mat-khau-ngay' --name Admin --role super_admin --plan-type agency"
```

Seed subscription plans thu cong neu can:

```bash
docker compose --env-file deploy/env/compose.env -f docker-compose.production.yml exec -T backend \
  sh -lc "cd /app && PYTHONPATH=/app python scripts/seed_subscription_plans.py"
```

## 7. Health check sau deploy

- Backend: `https://api.your-domain.com/health`
- Frontend: `https://app.your-domain.com`
- Admin login: `https://app.your-domain.com/admin/login`

Neu chua gan domain, kiem tra tam:

- `http://SERVER_IP:3000`
- `http://SERVER_IP:8000/health`

Muốn cho phep truy cap truc tiep bang IP thi doi `BACKEND_BIND_ADDRESS` va `FRONTEND_BIND_ADDRESS` thanh `0.0.0.0` trong `deploy/env/compose.env`.

## 8. Update phien ban moi

Moi lan deploy lai:

```bash
cd /opt/seo-wb
bash deploy/vps-deploy.sh
```

Script se:

- fetch code moi
- reset server ve dung branch dich
- start ha tang `db`, `redis`, `rabbitmq`
- build lai backend/frontend/workers
- restart stack production

## 9. GitHub Actions CI/CD

Workflow da duoc tao tai:

- [.github/workflows/ci.yml](/c:/Users/admin/seo-wb/.github/workflows/ci.yml)
- [.github/workflows/cd.yml](/c:/Users/admin/seo-wb/.github/workflows/cd.yml)

### CI

Chay khi `push` va `pull_request`:

- backend pytest
- frontend lint
- frontend build
- `docker compose config` cho production stack

### CD

Chay sau khi workflow CI cua branch `main` thanh cong.

CD se:

- chi deploy dung commit SHA da vuot qua CI
- bo qua workflow cu neu branch production da co commit moi hon
- fail neu thieu GitHub Secrets bat buoc
- SSH vao VPS
- tao/ghi de `deploy/env/compose.env`
- tao/ghi de `deploy/env/backend.env`
- upload va chay [deploy/vps-deploy.sh](/c:/Users/admin/seo-wb/deploy/vps-deploy.sh) tu commit da vuot qua CI
- build va restart day du backend, frontend va cac worker, bao gom `sync-worker`
- cho health check hoan tat; neu deploy loi thi rollback best-effort ve commit truoc

### GitHub Secrets toi thieu

Bat buoc:

- `VPS_HOST`
- `VPS_USER`
- `VPS_SSH_PRIVATE_KEY`
- `POSTGRES_PASSWORD`
- `RABBITMQ_PASSWORD`
- `APP_SECRET_KEY`
- `ENCRYPTION_KEY`
- `NEXT_PUBLIC_API_URL`

Rat nen co:

- `VPS_PORT`
- `DEPLOY_PATH`
- `DEPLOY_BRANCH`
- `CORS_ALLOW_ORIGINS`
- `COOKIE_DOMAIN`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`

Secrets co default neu bo trong:

- `POSTGRES_DB=seo_wb_db`
- `POSTGRES_USER=postgres`
- `RABBITMQ_USERNAME=sellerwb`
- `RABBITMQ_VHOST=sellerwb`
- `BACKEND_BIND_ADDRESS=127.0.0.1`
- `BACKEND_HTTP_PORT=8000`
- `FRONTEND_BIND_ADDRESS=127.0.0.1`
- `FRONTEND_HTTP_PORT=3000`
- nhieu bien backend runtime khac theo file example

### Luu y

- Workflow CD dang target `environment: production`, nen ban co the dat environment secrets/approval trong GitHub de chan deploy nham.
- `DEPLOY_PATH` mac dinh la `/opt/seo-wb`.
- Khi deploy loi, rerun CD tu GitHub Actions de van giu rang buoc commit da vuot qua CI.

## 10. Luu y quan trong

- `redis` la bat buoc cho image jobs va finance jobs.
- `rabbitmq` va `sync-worker` phai cung chay trong production; neu thieu `sync-worker`, queue `wb.sync.jobs` se khong co consumer.
- Khong commit `deploy/env/*.env`.
- Truoc khi rollback database, backup Postgres truoc.
