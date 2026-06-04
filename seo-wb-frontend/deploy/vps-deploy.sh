#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/seller-wb-ai-frontend}"
BRANCH="${BRANCH:-main}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.production.yml}"
ENV_FILE="${ENV_FILE:-deploy/env/compose.env}"

cd "$APP_DIR"

git fetch --prune origin
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build --pull
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --remove-orphans
docker image prune -f
