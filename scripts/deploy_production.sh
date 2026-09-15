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

probe_workflow_contract() {
    docker exec xvond-workflow-engine node -e '
const url = "http://127.0.0.1:5678/webhook/xvond-actions";
const secret = String(process.env.N8N_SHARED_SECRET || "");
if (!secret) { console.error("Workflow contract probe failed: shared secret missing"); process.exit(1); }
const requestId = `release-${Date.now()}`;
fetch(url, {
  method: "POST",
  headers: {
    "content-type": "application/json",
    "x-xvond-n8n-secret": secret,
    "x-xvond-request-id": requestId,
  },
  body: JSON.stringify({request_id: requestId, company_id: 1, agent_id: 1, conversation_id: null, action: "health_check", data: {source: "production_release"}}),
}).then(async response => {
  if (!response.ok) throw new Error(`http_${response.status}`);
  const result = await response.json();
  if (!result || result.success !== true || !result.data || String(result.data.status || "").toLowerCase() !== "ok") throw new Error("invalid_contract_response");
}).catch(error => {
  console.error(`Workflow contract probe failed: ${String(error && error.message || "unknown")}`);
  process.exit(1);
});'
}

case "$(git status --porcelain 2>/dev/null || true)" in
    "") ;;
    *) echo "Refusing production deploy from a dirty Git working tree" >&2; exit 1 ;;
esac

if [ ! -f .env ]; then
    echo "Refusing production deploy: .env is missing" >&2
    exit 1
fi

placeholder_key="$(awk -F= '
    /^[[:space:]]*#/ || !/=/{next}
    {
        key=$1
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", key)
        value=substr($0, index($0, "=") + 1)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
        upper=toupper(value)
        lower=tolower(value)
        if (upper ~ /GENERATE_/) { print key; exit }
        if (upper ~ /CHANGE_TO_/) { print key; exit }
        if (upper ~ /URL_ENCODED_PASSWORD/) { print key; exit }
        if (upper ~ /REPLACE_ME/) { print key; exit }
        if (upper ~ /YOUR_SECRET/) { print key; exit }
        if (upper ~ /YOUR_PASSWORD/) { print key; exit }
        if (upper ~ /EXAMPLE_SECRET/) { print key; exit }
        if (key == "SUPERADMIN_EMAIL" && lower == "admin@example.com") { print key; exit }
    }
' .env)"
if [ -n "$placeholder_key" ]; then
    echo "Refusing production deploy: placeholder value remains for $placeholder_key" >&2
    exit 1
fi

release_sha="$(git rev-parse HEAD)"
release_short="$(git rev-parse --short HEAD)"
echo "Deploying Xvond release $release_short"

compose config >/dev/null
compose up -d postgres redis
wait_healthy xvond-postgres
wait_healthy xvond-redis
compose run --rm --no-deps --entrypoint /bin/sh postgres-backup /opt/xvond/scripts/backup_postgres.sh
compose build app
workflow_enabled="$(compose run --rm --no-deps --entrypoint python app -c "from backend.app.core.config.settings import settings; print('true' if settings.N8N_ENABLED else 'false')" | tr -d '\r\n')"

if [ "$workflow_enabled" = "true" ]; then
    docker compose -f "$COMPOSE_FILE" --profile workflow up -d workflow-postgres
    wait_healthy xvond-workflow-postgres
    docker compose -f "$COMPOSE_FILE" --profile workflow up -d --no-deps workflow-engine
    wait_healthy xvond-workflow-engine
    probe_workflow_contract
fi

compose stop whatsapp-worker >/dev/null 2>&1 || true
compose up -d --no-deps --force-recreate app
wait_healthy xvond-core
compose up -d --no-deps --force-recreate whatsapp-worker

app_image="$(docker inspect --format '{{.Image}}' xvond-core)"
worker_image="$(docker inspect --format '{{.Image}}' xvond-whatsapp-worker)"
if [ -z "$app_image" ] || [ "$app_image" != "$worker_image" ]; then
    echo "Release rejected: API and WhatsApp worker are not running the same image" >&2
    echo "app=$app_image worker=$worker_image" >&2
    exit 1
fi

compose up -d postgres-backup
compose exec -T app python -c "import json, urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=5)); assert data.get('status') == 'healthy', data"

if [ -n "$ACCEPTANCE_COMPANY_ID" ]; then
    set -- python scripts/production_acceptance.py --company-id "$ACCEPTANCE_COMPANY_ID"
    if [ -n "$ACCEPTANCE_AGENT_ID" ]; then set -- "$@" --agent-id "$ACCEPTANCE_AGENT_ID"; fi
    if [ "$ACCEPTANCE_LIVE_AI" = "true" ]; then set -- "$@" --live-ai; fi
    if [ "$ACCEPTANCE_REQUIRE_LIVE" = "true" ]; then set -- "$@" --require-live; fi
    compose exec -T app "$@"
fi

printf 'Xvond release complete: %s\n' "$release_sha"
printf 'API image: %s\n' "$app_image"
printf 'WhatsApp worker image: %s\n' "$worker_image"
printf 'Workflow engine enabled: %s\n' "$workflow_enabled"
