#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/seo-wb}"
BRANCH="${BRANCH:-main}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.production.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-deploy/env/compose.env}"
BACKEND_ENV_FILE="${BACKEND_ENV_FILE:-deploy/env/backend.env}"

cd "$APP_DIR"

if [[ ! -f "$COMPOSE_ENV_FILE" ]]; then
  echo "Missing $COMPOSE_ENV_FILE"
  exit 1
fi

if [[ ! -f "$BACKEND_ENV_FILE" ]]; then
  echo "Missing $BACKEND_ENV_FILE"
  exit 1
fi

git fetch --prune origin
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

docker compose --env-file "$COMPOSE_ENV_FILE" -f "$COMPOSE_FILE" pull db redis rabbitmq || true
docker compose --env-file "$COMPOSE_ENV_FILE" -f "$COMPOSE_FILE" up -d db redis rabbitmq
docker compose --env-file "$COMPOSE_ENV_FILE" -f "$COMPOSE_FILE" build --pull backend worker finance-worker finance-scheduler usage-reset-scheduler frontend
docker compose --env-file "$COMPOSE_ENV_FILE" -f "$COMPOSE_FILE" up -d --remove-orphans backend worker finance-worker finance-scheduler usage-reset-scheduler frontend
docker image prune -f
