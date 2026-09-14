import inspect
from pathlib import Path

from backend.app.api import customer_agents


MANAGER_UI = Path("frontend/customer/manager-controls.js").read_text(encoding="utf-8")


def test_customer_cannot_activate_draft_employee_directly():
    source = inspect.getsource(customer_agents.update_agent)
    assert "AI employee activation is managed by Xvond Delivery Readiness" in source
    assert "if data.enabled is True and agent.enabled is False" in source


def test_customer_may_pause_live_employee_when_allowed():
    source = inspect.getsource(customer_agents.update_agent)
    assert "if data.enabled is False" in source
    assert "agent.enabled = False" in source


def test_customer_ui_does_not_offer_enable_control_for_draft_employee():
    assert "Awaiting Xvond Go-Live" in MANAGER_UI
    assert "Re-activation is performed by Xvond after Delivery Readiness checks" in MANAGER_UI
    assert "const runtimeCheckbox" in MANAGER_UI
    assert "if (runtimeCheckbox) payload.enabled" in MANAGER_UI
