#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/seo-wb}"
BRANCH="${BRANCH:-main}"
DEPLOY_SHA="${DEPLOY_SHA:-}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.production.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-deploy/env/compose.env}"
BACKEND_ENV_FILE="${BACKEND_ENV_FILE:-deploy/env/backend.env}"
INFRA_SERVICES=(db redis rabbitmq)
APP_SERVICES=(backend worker sync-worker finance-worker finance-scheduler usage-reset-scheduler frontend)
DEPLOYMENT_STARTED=false

cd "$APP_DIR"

if [[ ! -f "$COMPOSE_ENV_FILE" ]]; then
  echo "Missing $COMPOSE_ENV_FILE"
  exit 1
fi

if [[ ! -f "$BACKEND_ENV_FILE" ]]; then
  echo "Missing $BACKEND_ENV_FILE"
  exit 1
fi

PREVIOUS_SHA="$(git rev-parse HEAD)"

rollback() {
  local exit_code=$?
  trap - ERR

  if [[ "$PREVIOUS_SHA" != "$(git rev-parse HEAD)" ]]; then
    echo "Deploy failed. Restoring $PREVIOUS_SHA"
    git reset --hard "$PREVIOUS_SHA"
    if [[ "$DEPLOYMENT_STARTED" == "true" ]]; then
      docker compose --env-file "$COMPOSE_ENV_FILE" -f "$COMPOSE_FILE" build "${APP_SERVICES[@]}"
      docker compose --env-file "$COMPOSE_ENV_FILE" -f "$COMPOSE_FILE" up -d --remove-orphans --wait --wait-timeout 180 "${APP_SERVICES[@]}"
    fi
  fi

  exit "$exit_code"
}

trap rollback ERR

git fetch --prune origin

if [[ -n "$DEPLOY_SHA" ]]; then
  git merge-base --is-ancestor "$DEPLOY_SHA" "origin/$BRANCH"
  if [[ "$DEPLOY_SHA" != "$(git rev-parse "origin/$BRANCH")" ]]; then
    echo "Skipping stale deploy for $DEPLOY_SHA because origin/$BRANCH has advanced."
    exit 0
  fi
fi

git checkout -B "$BRANCH" "origin/$BRANCH"
git reset --hard "${DEPLOY_SHA:-origin/$BRANCH}"

docker compose --env-file "$COMPOSE_ENV_FILE" -f "$COMPOSE_FILE" config --quiet
docker compose --env-file "$COMPOSE_ENV_FILE" -f "$COMPOSE_FILE" pull "${INFRA_SERVICES[@]}" || true
docker compose --env-file "$COMPOSE_ENV_FILE" -f "$COMPOSE_FILE" up -d --wait --wait-timeout 180 "${INFRA_SERVICES[@]}"
docker compose --env-file "$COMPOSE_ENV_FILE" -f "$COMPOSE_FILE" build --pull "${APP_SERVICES[@]}"

DEPLOYMENT_STARTED=true
docker compose --env-file "$COMPOSE_ENV_FILE" -f "$COMPOSE_FILE" up -d --remove-orphans --wait --wait-timeout 180 "${APP_SERVICES[@]}"
docker compose --env-file "$COMPOSE_ENV_FILE" -f "$COMPOSE_FILE" ps

trap - ERR
docker image prune -f
