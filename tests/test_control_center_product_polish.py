from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_control_center_polish_is_loaded_last():
    html = (ROOT / "frontend/admin/index.html").read_text(encoding="utf-8")
    assert "/static/admin/control-center-polish.js" in html
    assert html.index("/static/admin/dashboard-accuracy.js") < html.index(
        "/static/admin/control-center-polish.js"
    )


def test_control_center_polish_contains_operator_product_controls():
    js = (ROOT / "frontend/admin/control-center-polish.js").read_text(encoding="utf-8")
    required = [
        "Needs Attention",
        "Live Channels",
        "limit reached",
        "WhatsApp connection needs attention",
        "External Reconciliation",
        "Company Subscription",
        "Global Package Catalog",
        "Global Xvond package",
        "Customer content is intentionally excluded",
    ]
    for value in required:
        assert value in js


def test_operator_control_center_does_not_reintroduce_tenant_customer_ops():
    js = (ROOT / "frontend/admin/control-center-polish.js").read_text(encoding="utf-8")
    assert "/admin/customer-operations/" not in js
    assert "xvondWorkspace?.data" in js
    assert "Customer payloads remain in the tenant workspace" in js
    assert "['Conversations','Customers','Notifications','Business Analytics']" in js
