import json
from pathlib import Path


WORKFLOW_PATH = Path("ops/n8n/xvond-actions.workflow.json")
CONTRACTS_PATH = Path("ops/n8n/action-contracts.json")


def _workflow_code() -> str:
    payload = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    nodes = {node["name"]: node for node in payload["nodes"]}
    return nodes["Validate and Dispatch"]["parameters"]["jsCode"]


def test_workflow_template_is_valid_and_uses_expected_webhook_contract():
    payload = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    assert payload["name"] == "Xvond Actions Gateway"
    nodes = {node["name"]: node for node in payload["nodes"]}
    webhook = nodes["Xvond Webhook"]
    assert webhook["parameters"]["httpMethod"] == "POST"
    assert webhook["parameters"]["path"] == "xvond-actions"
    assert webhook["parameters"]["responseMode"] == "responseNode"
    code = _workflow_code()
    assert "N8N_SHARED_SECRET" in code
    assert "health_check" in code
    assert "request_id" in code
    assert "company_id" in code
    assert "agent_id" in code
    assert "action" in code
    assert "provider_not_configured" in code
    assert "missing_idempotency_key" in code
    assert "Return to Xvond" in nodes


def test_registered_actions_are_declared_in_master_workflow():
    contracts = json.loads(CONTRACTS_PATH.read_text(encoding="utf-8"))
    code = _workflow_code()
    for action_name in contracts["actions"]:
        assert action_name in code, f"{action_name} is missing from master workflow routing"


def test_mutating_actions_require_idempotency():
    contracts = json.loads(CONTRACTS_PATH.read_text(encoding="utf-8"))
    assert contracts["policy"]["mutating_actions_require_idempotency"] is True
    for name, spec in contracts["actions"].items():
        if spec.get("side_effect"):
            assert "idempotency_key" in spec.get("required_data", []), name


def test_workflow_fail_closed_policy_is_explicit():
    contracts = json.loads(CONTRACTS_PATH.read_text(encoding="utf-8"))
    policy = contracts["policy"]
    assert policy["provider_success_required_before_success_true"] is True
    assert policy["credentials_live_in_workflow_engine"] is True
    assert policy["xvond_database_access_from_workflows"] is False


def test_generic_employee_actions_are_supported_by_contract_and_gateway():
    contracts = json.loads(CONTRACTS_PATH.read_text(encoding="utf-8"))
    generic = contracts["generic_business_action"]
    code = _workflow_code()
    assert generic["adapter"] == "business"
    assert generic["pattern"] == "<action_key>.(check_availability|execute|cancel)"
    assert contracts["policy"]["generic_employee_actions_are_config_driven"] is True
    assert "check_availability|execute|cancel" in code
    assert "action_config" in code
    assert "declaredActionType !== actionKey" in code
    assert "moduleName" in code
    assert "destination_type" in code


def test_generic_mutating_operations_require_stable_idempotency():
    contracts = json.loads(CONTRACTS_PATH.read_text(encoding="utf-8"))
    generic = contracts["generic_business_action"]
    assert generic["mutating_operations"] == ["execute", "cancel"]
    assert generic["mutating_operations_require_idempotency"] is True
    code = _workflow_code()
    assert "operation !== 'check_availability'" in code
    assert "route.mutates && !idempotencyKey" in code


def test_generic_action_key_is_not_hardcoded_to_business_templates():
    code = _workflow_code()
    assert "action.match" in code
    assert "action_key: actionKey" in code
    assert "Unsupported workflow action" in code
