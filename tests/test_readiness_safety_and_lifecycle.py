import inspect

from backend.app.core import readiness


def test_provider_readiness_uses_safe_error_label():
    source = inspect.getsource(readiness._provider_runtime)
    assert "safe_error_label(exc)" in source
    assert "str(exc)" not in source


def test_company_readiness_exposes_lifecycle_and_runtime_separately():
    source = inspect.getsource(readiness.company_readiness)
    assert '"active": company.active' in source
    assert '"lifecycle_status": company.lifecycle_status' in source
    assert '"lifecycle_updated_at": company.lifecycle_updated_at' in source


def test_readiness_language_distinguishes_runtime_from_commercial_state():
    source = inspect.getsource(readiness.company_readiness)
    assert "Company runtime is currently stopped" in source


def test_company_readiness_blocks_only_unusable_business_action_state():
    source = inspect.getsource(readiness.company_readiness)
    assert 'action_request_assigned = "action_request" in enabled_tool_names' in source
    assert "legacy_business_tools" in source
    assert "tools_ready = bool(" in source
    assert "not action_request_assigned or ready_action" in source
    assert "Legacy business tools are still enabled" in source
    assert "Business Actions are enabled, but no configured customer action is runtime-ready" in source
    assert "and tools_ready" in source
    assert '"tools_ready": tools_ready' in source


def test_human_handoff_is_not_treated_as_a_missing_business_action():
    source = inspect.getsource(readiness.company_readiness)
    assert 'if tools and not ready_action:' not in source
    assert 'action_request_assigned and not ready_action' in source
