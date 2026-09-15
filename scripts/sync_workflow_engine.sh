#!/bin/sh
set -eu

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.production.yml}"
WORKFLOW_FILE="${WORKFLOW_FILE:-ops/n8n/xvond-actions.workflow.json}"
WORKFLOW_ID="${WORKFLOW_ID:-77dbf1b8-241b-44ec-b0f8-a16fe415490a}"

if [ ! -f "$WORKFLOW_FILE" ]; then
    echo "Workflow sync failed: $WORKFLOW_FILE not found" >&2
    exit 1
fi

compose_workflow() {
    docker compose -f "$COMPOSE_FILE" --profile workflow "$@"
}

wait_for_runtime_webhook() {
    attempts="${1:-45}"
    count=0
    while [ "$count" -lt "$attempts" ]; do
        if docker exec xvond-workflow-engine node -e '
const secret = String(process.env.N8N_SHARED_SECRET || "");
const requestId = `sync-${Date.now()}`;
fetch("http://127.0.0.1:5678/webhook/xvond-actions", {
  method: "POST",
  headers: {
    "content-type": "application/json",
    "x-xvond-n8n-secret": secret,
    "x-xvond-request-id": requestId,
  },
  body: JSON.stringify({request_id: requestId, company_id: 1, agent_id: 1, conversation_id: null, action: "health_check", data: {source: "workflow_sync"}}),
}).then(async response => {
  const text = await response.text();
  if (response.ok) process.exit(0);
  if (response.status === 404 && text.includes("webhook is not registered")) process.exit(2);
  console.error(`Workflow runtime probe failed: http_${response.status}:${text.slice(0, 300)}`);
  process.exit(1);
}).catch(error => {
  console.error(`Workflow runtime probe failed: ${String(error && error.message || "unknown")}`);
  process.exit(2);
});'; then
            return 0
        else
            code="$?"
            if [ "$code" -ne 2 ]; then
                return "$code"
            fi
        fi
        count=$((count + 1))
        sleep 1
    done
    echo "Workflow runtime webhook did not register after restart" >&2
    docker logs --tail 100 xvond-workflow-engine >&2 || true
    return 1
}

# Stop the runtime before importing so the DB and registered webhook state are
# updated as one unit. The imported workflow uses a stable source-controlled ID,
# so repeated deploys overwrite the same workflow rather than creating copies.
compose_workflow stop workflow-engine >/dev/null 2>&1 || true

compose_workflow run --rm \
    -v "$PWD/ops/n8n:/import:ro" \
    workflow-engine \
    import:workflow --input=/import/xvond-actions.workflow.json

# Publish and explicitly preserve the active flag for the pinned n8n runtime.
compose_workflow run --rm \
    workflow-engine \
    publish:workflow --id="$WORKFLOW_ID"

compose_workflow run --rm \
    workflow-engine \
    update:workflow --id="$WORKFLOW_ID" --active=true

compose_workflow up -d --no-deps workflow-engine
wait_for_runtime_webhook

echo "Workflow engine synced from Git: $WORKFLOW_ID"
