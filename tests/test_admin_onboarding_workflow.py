from pathlib import Path


INDEX = Path("frontend/admin/index.html").read_text(encoding="utf-8")
WORKFLOW = Path("frontend/admin/company-onboarding-workflow.js").read_text(encoding="utf-8")


def test_admin_loads_operational_onboarding_workflow():
    assert "/static/admin/company-onboarding-workflow.js" in INDEX
    assert "Customer Onboarding" in WORKFLOW
    assert "Service package assigned" in WORKFLOW
    assert "Business Profile complete" in WORKFLOW
    assert "AI Employee created" in WORKFLOW
    assert "Knowledge ready" in WORKFLOW
    assert "Production channel connected" in WORKFLOW
    assert "Production Readiness passed" in WORKFLOW


def test_onboarding_workflow_uses_canonical_lifecycle_actions():
    # The generated HTML escapes quotes inside JavaScript string literals, so
    # assert the operator actions and canonical lifecycle function separately
    # instead of depending on one exact source-escaping form.
    assert "setWorkspaceLifecycle" in WORKFLOW
    assert "Move to Testing" in WORKFLOW
    assert "Go Live" in WORKFLOW
    assert "'onboarding'" in WORKFLOW
    assert "'testing'" in WORKFLOW
    assert "'live'" in WORKFLOW
    assert "readinessReady" in WORKFLOW


def test_agent_templates_are_operable_from_admin_ui():
    assert "/admin/agent-factory/templates" in WORKFLOW
    assert "/admin/agent-factory/companies/${xvondWorkspace.companyId}/from-template" in WORKFLOW
    assert "Create AI Employee from Template" in WORKFLOW
    assert "Manage Templates" in WORKFLOW
