#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/seller-wb-ai-backend}"
BRANCH="${BRANCH:-main}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.production.yml}"
ENV_FILE="${ENV_FILE:-deploy/env/compose.env}"
BACKEND_RUNTIME_ENV_FILE="${BACKEND_RUNTIME_ENV_FILE:-deploy/env/backend.runtime.env}"

cd "$APP_DIR"

git fetch --prune origin
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

touch "$BACKEND_RUNTIME_ENV_FILE"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d db
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build --pull backend
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm backend python scripts/migrate.py
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build worker
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --remove-orphans backend worker nginx
docker image prune -f
