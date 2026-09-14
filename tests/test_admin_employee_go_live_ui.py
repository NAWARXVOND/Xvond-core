from pathlib import Path


INDEX = Path("frontend/admin/index.html").read_text(encoding="utf-8")
GO_LIVE = Path("frontend/admin/employee-go-live-controls.js").read_text(encoding="utf-8")


def test_admin_loads_employee_go_live_controls_after_workspace_layers():
    assert "/static/admin/employee-go-live-controls.js" in INDEX
    assert INDEX.index("company-control-center.js") < INDEX.index("employee-go-live-controls.js")
    assert INDEX.index("company-lifecycle-controls.js") < INDEX.index("employee-go-live-controls.js")


def test_employee_go_live_uses_delivery_readiness_authority():
    assert "/admin/delivery-readiness/companies/${xvondWorkspace.companyId}/agents/${agentId}/go-live" in GO_LIVE
    assert "/admin/delivery-readiness/companies/${xvondWorkspace.companyId}/agents/${agentId}/deactivate" in GO_LIVE
    assert "Delivery Readiness owns Go Live" in GO_LIVE


def test_employee_production_ui_distinguishes_setup_from_customer_traffic():
    assert "Setup Ready" in GO_LIVE
    assert "Customer Traffic Live" in GO_LIVE
    assert "Employee Live · Channel Pending" in GO_LIVE
    assert "Draft" in GO_LIVE
    assert "Open Channels" in GO_LIVE
