# Frontend Deployment

This frontend project is independent. Its CI/CD, Docker Compose, env files, and deploy script live inside this project.

When this folder is used as its own GitHub repository, keep these paths at the repo root:

```text
.github/workflows/frontend-ci-cd.yml
.github/CODEOWNERS
Dockerfile
docker-compose.production.yml
deploy/
.gitignore
```

## VPS Setup

Install Docker and Git on the frontend VPS, then clone the frontend repo:

```bash
sudo mkdir -p /opt/seller-wb-ai-frontend
sudo chown -R $USER:$USER /opt/seller-wb-ai-frontend
git clone git@github.com:YOUR_USER/YOUR_FRONTEND_REPO.git /opt/seller-wb-ai-frontend
cd /opt/seller-wb-ai-frontend
```

If you keep a temporary monorepo during migration, clone only this folder into the frontend repo before using this guide.

## Env File

```bash
cp deploy/env/compose.env.example deploy/env/compose.env
nano deploy/env/compose.env
```

Production frontend env:

```env
NEXT_PUBLIC_API_URL=https://api.your-domain.com/api/v1
NEXT_PUBLIC_CSRF_COOKIE_NAME=seller_wb_csrf
FRONTEND_HTTP_PORT=3000
```

Backend should be configured with:

```env
CORS_ALLOW_ORIGINS=https://app.your-domain.com
COOKIE_DOMAIN=.your-domain.com
COOKIE_SECURE=true
```

## Manual Deploy

```bash
cd /opt/seller-wb-ai-frontend
bash deploy/vps-deploy.sh
```

The deploy script pulls latest `main`, builds the Next.js container, and restarts frontend nginx.

## GitHub Secrets

Add these in the frontend GitHub repo:

```text
VPS_HOST=app-server-ip-or-domain
VPS_USER=ubuntu
VPS_PORT=22
VPS_SSH_PRIVATE_KEY=private-key-content
DEPLOY_PATH=/opt/seller-wb-ai-frontend
DEPLOY_BRANCH=main
```

## Public Port

Frontend Compose exposes `FRONTEND_HTTP_PORT`, default `3000`. Put Cloudflare/Nginx/Traefik in front for HTTPS.
