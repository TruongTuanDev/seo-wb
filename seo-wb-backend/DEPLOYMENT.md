# Backend Deployment

This backend project is independent. Its CI/CD, Docker Compose, env files, and deploy script live inside this project.

When this folder is used as its own GitHub repository, keep these paths at the repo root:

```text
.github/workflows/backend-ci-cd.yml
.github/CODEOWNERS
Dockerfile
docker-compose.production.yml
deploy/
.gitignore
```

## VPS Setup

Install Docker and Git on the backend VPS, then clone the backend repo:

```bash
sudo mkdir -p /opt/seller-wb-ai-backend
sudo chown -R $USER:$USER /opt/seller-wb-ai-backend
git clone git@github.com:YOUR_USER/YOUR_BACKEND_REPO.git /opt/seller-wb-ai-backend
cd /opt/seller-wb-ai-backend
```

If you keep a temporary monorepo during migration, clone only this folder into the backend repo before using this guide.

## Env Files

```bash
cp deploy/env/backend.env.example deploy/env/backend.env
cp deploy/env/compose.env.example deploy/env/compose.env
nano deploy/env/backend.env
nano deploy/env/compose.env
```

Production backend env should include:

```env
APP_ENV=production
APP_SECRET_KEY=replace-with-random-secret
ENCRYPTION_KEY=replace-with-another-random-secret
CORS_ALLOW_ORIGINS=https://app.your-domain.com
COOKIE_DOMAIN=.your-domain.com
COOKIE_SECURE=true
GEMINI_API_KEY=your-gemini-key
OPENAI_API_KEY=your-openai-key
```

Generate secrets:

```bash
openssl rand -hex 32
```

## Manual Deploy

```bash
cd /opt/seller-wb-ai-backend
bash deploy/vps-deploy.sh
```

The deploy script pulls latest `main`, starts PostgreSQL, builds backend, runs Alembic migrations, and restarts backend nginx.

For finance automation, the production compose stack now includes:

- `finance-worker`: consumes automated finance bootstrap and daily sync jobs
- `finance-scheduler`: enqueues nightly catch-up jobs at the configured timezone boundary

Production env must include Redis because these finance automation services use the same Redis infrastructure pattern as the image worker.

## GitHub Secrets

Add these in the backend GitHub repo:

```text
VPS_HOST=api-server-ip-or-domain
VPS_USER=ubuntu
VPS_PORT=22
VPS_SSH_PRIVATE_KEY=private-key-content
DEPLOY_PATH=/opt/seller-wb-ai-backend
DEPLOY_BRANCH=main
```

## Public Port

Backend Compose exposes `BACKEND_HTTP_PORT`, default `8000`. Put Cloudflare/Nginx/Traefik in front for HTTPS.

## Security Note

Do not commit `.env` or `deploy/env/*.env`. Rotate any Gemini/OpenAI keys that were ever stored in a local committed workspace.
