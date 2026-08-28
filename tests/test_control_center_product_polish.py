from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_control_center_polish_is_loaded_last():
    html = (ROOT / "frontend/admin/index.html").read_text(encoding="utf-8")
    assert "/static/admin/control-center-polish.js" in html
    assert html.index("/static/admin/dashboard-accuracy.js") < html.index(
        "/static/admin/control-center-polish.js"
    )


def test_control_center_polish_contains_core_product_controls():
    js = (ROOT / "frontend/admin/control-center-polish.js").read_text(encoding="utf-8")
    required = [
        "Needs Attention",
        "Active Channel",
        "Limit exceeded",
        "All modes",
        "All channels",
        "Search name, phone, email, tag",
        "All types",
        "Mark all read",
        "previous-period comparison",
        "External delivery not connected",
    ]
    for value in required:
        assert value in js


def test_customer_ops_filters_keep_company_scope():
    js = (ROOT / "frontend/admin/control-center-polish.js").read_text(encoding="utf-8")
    assert "/admin/customer-operations/companies/${xvondWorkspace.companyId}/analytics" in js
    assert "xvondWorkspace.data" in js
