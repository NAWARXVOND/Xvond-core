from pathlib import Path


WORKFLOW = Path("ops/n8n/xvond-actions.workflow.json").read_text(encoding="utf-8")
COMPOSE = Path("docker-compose.production.yml").read_text(encoding="utf-8")
ENV_EXAMPLE = Path(".env.example").read_text(encoding="utf-8")
DOC = Path("ops/n8n/CONNECTED_INTEGRATIONS.md").read_text(encoding="utf-8")


def test_connected_integration_routes_by_company_and_integration_id():
    assert "destinationType === 'integration'" in WORKFLOW
    assert "destination.integration_id" in WORKFLOW
    assert "`${body.company_id}:${integrationId}`" in WORKFLOW
    assert "connected_integration" in WORKFLOW


def test_workflow_registry_is_owned_by_execution_plane():
    assert "XVOND_WORKFLOW_INTEGRATIONS_JSON" in WORKFLOW
    assert "XVOND_WORKFLOW_INTEGRATIONS_JSON" in COMPOSE
    assert "XVOND_WORKFLOW_INTEGRATIONS_JSON" in ENV_EXAMPLE
    assert "Core never sends the webhook URL or secret" in DOC


def test_webhook_route_fails_closed_when_missing_or_unsafe():
    assert "target.type !== 'webhook'" in WORKFLOW
    assert "!target.url.startsWith('https://')" in WORKFLOW
    assert "Connected integration route is not configured" in WORKFLOW
    assert "provider_not_configured" in WORKFLOW


def test_connected_webhook_preserves_execution_identity():
    assert '"X-Xvond-Request-ID"' in WORKFLOW
    assert '"Idempotency-Key"' in WORKFLOW
    assert "$json.data.idempotency_key" in WORKFLOW
    assert "X-Xvond-Integration-Secret" in WORKFLOW
