import json
from pathlib import Path


WORKFLOW_PATH = Path("ops/n8n/xvond-actions.workflow.json")


def test_workflow_template_is_valid_and_uses_expected_webhook_contract():
    payload = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    assert payload["name"] == "Xvond Actions Gateway"
    nodes = {node["name"]: node for node in payload["nodes"]}
    webhook = nodes["Xvond Webhook"]
    assert webhook["parameters"]["httpMethod"] == "POST"
    assert webhook["parameters"]["path"] == "xvond-actions"
    assert webhook["parameters"]["responseMode"] == "responseNode"
    code = nodes["Validate and Dispatch"]["parameters"]["jsCode"]
    assert "N8N_SHARED_SECRET" in code
    assert "health_check" in code
    assert "request_id" in code
    assert "company_id" in code
    assert "agent_id" in code
    assert "action" in code
    assert "Return to Xvond" in nodes
