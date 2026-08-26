from pathlib import Path

from backend.app.modules.solutions.portal import build_customer_portal_navigation


ROOT = Path(__file__).resolve().parents[1]


def _ids(items):
    return [item["id"] for item in items]


def test_ai_agents_portal_is_capability_aware():
    basic = build_customer_portal_navigation(["ai_agents"], [])
    assert _ids(basic) == [
        "dashboard",
        "agents",
        "chat",
        "conversations",
        "usage",
        "billing",
    ]

    with_operations = build_customer_portal_navigation(
        ["ai_agents"],
        ["quotation"],
    )
    assert _ids(with_operations) == [
        "dashboard",
        "agents",
        "chat",
        "conversations",
        "business",
        "usage",
        "billing",
    ]


def test_portal_separates_active_services_and_keeps_billing_core():
    navigation = build_customer_portal_navigation(
        ["automation", "analytics", "integrations"],
        [],
    )
    ids = _ids(navigation)
    assert ids == [
        "dashboard",
        "service-automation",
        "service-analytics",
        "integrations",
        "billing",
    ]
    assert "agents" not in ids


def test_customer_ui_renders_navigation_from_backend_contract():
    html = (ROOT / "frontend" / "customer" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend" / "customer" / "app.js").read_text(encoding="utf-8")
    api_source = (ROOT / "backend" / "app" / "api" / "customer_portal.py").read_text(encoding="utf-8")

    assert 'id="portal-nav"' in html
    assert 'id="page-billing"' in html
    assert "portalOverview?.portal?.navigation" in js
    assert "renderPortalNavigation" in js
    assert "renderBilling" in js
    assert '"online_payments_enabled": False' in api_source
