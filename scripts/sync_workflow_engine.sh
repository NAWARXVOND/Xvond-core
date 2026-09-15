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

# Stop the runtime before importing so the DB and registered webhook state are
# updated as one unit. The imported workflow uses a stable source-controlled ID,
# so repeated deploys overwrite the same workflow rather than creating copies.
compose_workflow stop workflow-engine >/dev/null 2>&1 || true

compose_workflow run --rm \
    -v "$PWD/ops/n8n:/import:ro" \
    workflow-engine \
    import:workflow --input=/import/xvond-actions.workflow.json

compose_workflow run --rm \
    workflow-engine \
    publish:workflow --id="$WORKFLOW_ID"

compose_workflow up -d --no-deps workflow-engine

echo "Workflow engine synced from Git: $WORKFLOW_ID"
