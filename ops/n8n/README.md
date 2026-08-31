# Xvond Workflow Engine Runbook

This directory contains the self-hosted workflow runtime used as Xvond's external execution plane.

## Architecture

- Xvond Core is the control plane.
- The workflow engine executes external business actions.
- The workflow engine has its own PostgreSQL database.
- The workflow engine does not read or write the Xvond application database directly.
- Xvond communicates with the workflow engine only through the gateway webhook contract.
- The vendor name is infrastructure-only and should not be exposed in customer or admin product UI.

## Required environment values

Set these in `.env` before enabling the workflow profile:

- `WORKFLOW_ENGINE_VERSION`
- `WORKFLOW_DB_USER`
- `WORKFLOW_DB_PASSWORD`
- `WORKFLOW_DB_NAME`
- `WORKFLOW_ENCRYPTION_KEY`
- `WORKFLOW_HOST`
- `WORKFLOW_PUBLIC_URL`
- `WORKFLOW_PORT`
- `WORKFLOW_TIMEZONE`
- `N8N_SHARED_SECRET`
- `N8N_ENABLED=true`
- `N8N_WEBHOOK_URL=http://workflow-engine:5678/webhook/xvond-actions`

`N8N_SHARED_SECRET` must be identical in Xvond Core and the workflow-engine container.

## Safe startup

The workflow services are isolated behind the Docker Compose `workflow` profile. Normal Xvond startup is unchanged until that profile is explicitly enabled.

Run:

```sh
sh scripts/workflow_engine_up.sh
```

Equivalent command:

```sh
docker compose -f docker-compose.production.yml --profile workflow up -d workflow-postgres workflow-engine
```

## Master workflow

Import:

`ops/n8n/xvond-actions.workflow.json`

The first supported action is intentionally non-destructive:

`health_check`

Expected request contract:

```json
{
  "request_id": "stable-request-id",
  "company_id": 1,
  "agent_id": 1,
  "conversation_id": null,
  "action": "health_check",
  "data": {}
}
```

Required headers:

- `X-Xvond-N8N-Secret`
- `X-Xvond-Request-ID`

Expected response contract:

```json
{
  "success": true,
  "request_id": "stable-request-id",
  "action": "health_check",
  "data": {
    "status": "ok"
  },
  "error": null
}
```

## Canonical business-action contracts

The authoritative action contract catalog is:

`ops/n8n/action-contracts.json`

Initial contracts:

- `create_booking.check_availability`
- `create_booking.execute`
- `create_booking.cancel`
- `send_email.execute`

Every side-effecting action must carry a stable `idempotency_key`. Xvond generates and persists that identity before dispatch. The workflow must reuse it when calling the third-party provider and must not invent a new request identity on retry.

Provider credentials are intentionally not stored in Git. Attach real credentials only inside the workflow engine when configuring the target provider. Examples include Google Calendar / Microsoft Calendar for booking and SMTP / transactional-email provider credentials for email. Switching providers must not require a Xvond Core code change as long as the workflow preserves the canonical request/response contract.

A successful side-effect response must only be returned after the external provider confirms success. The canonical response shape remains:

```json
{
  "success": true,
  "request_id": "same-stable-request-id",
  "action": "create_booking.execute",
  "data": {
    "provider_reference": "external-id"
  },
  "error": null
}
```

Failures must return `success: false` and an error message without pretending the business operation succeeded.

## Production promotion checklist

1. Keep the workflow engine bound to localhost and expose it only through the reverse proxy.
2. Use HTTPS for the public editor/webhook origin.
3. Use unique strong values for the workflow database password, encryption key, and shared secret.
4. Never reuse the Xvond application database credentials.
5. Activate the imported workflow only after the secret and webhook endpoint are configured.
6. Verify `health_check` end-to-end before enabling any business action.
7. For every mutating action, use the Xvond request identity as the workflow idempotency key.
8. Store third-party OAuth/API credentials in the workflow engine when that engine performs the external operation.
9. Do not give workflows direct database access to Xvond Core.
10. Run the workflow engine security audit after initial setup and after material configuration changes.

## Rollback

To stop the workflow runtime without affecting Xvond Core:

```sh
docker compose -f docker-compose.production.yml --profile workflow stop workflow-engine workflow-postgres
```

Set `N8N_ENABLED=false` in Xvond and restart the app. The preserved legacy implementation remains in the repository, but it is not the registered runtime path.
