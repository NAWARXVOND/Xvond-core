#!/bin/sh
set -eu

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.production.yml}"
ACCEPTANCE_COMPANY_ID="${ACCEPTANCE_COMPANY_ID:-}"
ACCEPTANCE_AGENT_ID="${ACCEPTANCE_AGENT_ID:-}"
ACCEPTANCE_LIVE_AI="${ACCEPTANCE_LIVE_AI:-false}"
ACCEPTANCE_REQUIRE_LIVE="${ACCEPTANCE_REQUIRE_LIVE:-false}"

compose() {
    docker compose -f "$COMPOSE_FILE" "$@"
}

wait_healthy() {
    container="$1"
    attempts="${2:-60}"
    count=0
    while [ "$count" -lt "$attempts" ]; do
        status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dev/null || true)"
        if [ "$status" = "healthy" ] || [ "$status" = "running" ]; then
            return 0
        fi
        if [ "$status" = "unhealthy" ] || [ "$status" = "exited" ] || [ "$status" = "dead" ]; then
            echo "Container $container entered unsafe state: $status" >&2
            docker logs --tail 100 "$container" >&2 || true
            return 1
        fi
        count=$((count + 1))
        sleep 2
    done
    echo "Container $container did not become healthy" >&2
    docker logs --tail 100 "$container" >&2 || true
    return 1
}

case "$(git status --porcelain 2>/dev/null || true)" in
    "") ;;
    *)
        echo "Refusing production deploy from a dirty Git working tree" >&2
        exit 1
        ;;
esac

release_sha="$(git rev-parse HEAD)"
release_short="$(git rev-parse --short HEAD)"
echo "Deploying Xvond release $release_short"

compose config >/dev/null

# Bring durable dependencies up first so a release backup can be taken even if
# the application containers are currently stopped.
compose up -d postgres redis
wait_healthy xvond-postgres
wait_healthy xvond-redis

# Always take a fresh database backup before a production image/schema change.
# A one-shot service uses the same production credentials, network and backup
# volumes without racing the long-running backup loop entrypoint.
compose run --rm --no-deps \
    --entrypoint /bin/sh \
    postgres-backup \
    /opt/xvond/scripts/backup_postgres.sh

# No old worker may process inbound events while the new app image runs schema
# migrations and startup hardening.
compose stop whatsapp-worker >/dev/null 2>&1 || true

# Build the canonical image once. Both API and WhatsApp worker must run this
# exact image ID; the post-start assertion below fails the release otherwise.
compose build app

compose up -d --no-deps --force-recreate app
wait_healthy xvond-core

# The application container owns the authoritative parsed production settings.
# If customer business actions are enabled globally, bring the external
# execution plane up as part of the same release instead of relying on a second
# forgotten operator command. Workflow import/publish is intentionally not
# fabricated here: production acceptance below will fail for action-enabled
# employees unless the documented health_check workflow is actually active.
workflow_enabled="$(compose exec -T app python -c "from backend.app.core.config.settings import settings; print('true' if settings.N8N_ENABLED else 'false')" | tr -d '\r\n')"
if [ "$workflow_enabled" = "true" ]; then
    docker compose -f "$COMPOSE_FILE" --profile workflow up -d workflow-postgres workflow-engine
    wait_healthy xvond-workflow-postgres
    wait_healthy xvond-workflow-engine
fi

compose up -d --no-deps --force-recreate whatsapp-worker

app_image="$(docker inspect --format '{{.Image}}' xvond-core)"
worker_image="$(docker inspect --format '{{.Image}}' xvond-whatsapp-worker)"
if [ -z "$app_image" ] || [ "$app_image" != "$worker_image" ]; then
    echo "Release rejected: API and WhatsApp worker are not running the same image" >&2
    echo "app=$app_image worker=$worker_image" >&2
    exit 1
fi

# Keep the continuous local backup service running after the release backup.
compose up -d postgres-backup

# Basic application readiness is mandatory for every release.
compose exec -T app python -c \
    "import json, urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=5)); assert data.get('status') == 'healthy', data"

# Customer/employee acceptance is optional at script level because a platform
# release may serve multiple tenants. When IDs are supplied, it becomes a hard
# release gate and includes Workflow Engine health for action-enabled employees.
if [ -n "$ACCEPTANCE_COMPANY_ID" ]; then
    set -- python scripts/production_acceptance.py --company-id "$ACCEPTANCE_COMPANY_ID"
    if [ -n "$ACCEPTANCE_AGENT_ID" ]; then
        set -- "$@" --agent-id "$ACCEPTANCE_AGENT_ID"
    fi
    if [ "$ACCEPTANCE_LIVE_AI" = "true" ]; then
        set -- "$@" --live-ai
    fi
    if [ "$ACCEPTANCE_REQUIRE_LIVE" = "true" ]; then
        set -- "$@" --require-live
    fi
    compose exec -T app "$@"
fi

printf 'Xvond release complete: %s\n' "$release_sha"
printf 'API image: %s\n' "$app_image"
printf 'WhatsApp worker image: %s\n' "$worker_image"
printf 'Workflow engine enabled: %s\n' "$workflow_enabled"
