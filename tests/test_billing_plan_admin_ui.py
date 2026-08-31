from pathlib import Path


def test_admin_loads_billing_package_management_after_company_workspace():
    index = Path("frontend/admin/index.html").read_text(encoding="utf-8")
    workspace_pos = index.index('/static/admin/company-control-center.js')
    billing_pos = index.index('/static/admin/billing-plan-management.js')
    assert billing_pos > workspace_pos


def test_billing_package_ui_can_create_assign_and_edit_packages():
    script = Path("frontend/admin/billing-plan-management.js").read_text(encoding="utf-8")
    assert "openWorkspaceCreateServicePlan" in script
    assert "saveWorkspaceNewServicePlan" in script
    assert "openWorkspaceServiceForm" in script
    assert "openWorkspaceEditServicePlan" in script
    assert "'/admin/service-billing/plans'" in script
    assert "['agents', 'Active AI Employees']" in script
    assert "['channels', 'Active Channels']" in script
    assert "['tokens', 'AI tokens / month']" in script
    assert "['requests', 'AI requests / month']" in script
