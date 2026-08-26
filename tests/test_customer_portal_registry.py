from pathlib import Path

from backend.app.modules.ai_agent.models import AIConversation
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
    assert next(item for item in basic if item["id"] == "conversations")["label"] == "Inbox"

    quotation = build_customer_portal_navigation(
        ["ai_agents"],
        ["quotation"],
    )
    assert _ids(quotation) == [
        "dashboard",
        "agents",
        "chat",
        "conversations",
        "requests-quotation",
        "usage",
        "billing",
    ]
    quote_page = next(item for item in quotation if item["id"] == "requests-quotation")
    assert quote_page["capability_module"] == "quotation"
    assert quote_page["label"] == "Quotation Requests"


def test_multiple_capabilities_create_separate_operation_pages():
    navigation = build_customer_portal_navigation(
        ["ai_agents"],
        ["quotation", "booking", "orders", "lead_management", "customer_support"],
    )
    ids = _ids(navigation)
    assert "requests-quotation" in ids
    assert "requests-booking" in ids
    assert "requests-orders" in ids
    assert "requests-leads" in ids
    assert "requests-support" in ids
    assert "business" not in ids


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


def test_conversations_have_generic_channel_source_fields():
    columns = AIConversation.__table__.c
    assert "channel_id" in columns
    assert "channel_type" in columns
    assert "external_contact_id" in columns


def test_customer_ui_renders_backend_navigation_and_unified_inbox():
    html = (ROOT / "frontend" / "customer" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend" / "customer" / "app.js").read_text(encoding="utf-8")
    enhancements = (
        ROOT / "frontend" / "customer" / "portal-enhancements.js"
    ).read_text(encoding="utf-8")
    api_source = (
        ROOT / "backend" / "app" / "api" / "customer_portal.py"
    ).read_text(encoding="utf-8")
    inbox_source = (
        ROOT / "backend" / "app" / "api" / "customer_inbox.py"
    ).read_text(encoding="utf-8")

    assert 'id="portal-nav"' in html
    assert 'id="page-billing"' in html
    assert "/static/customer/portal-enhancements.js" in html
    assert "portalOverview?.portal?.navigation" in js
    assert "renderPortalNavigation" in js
    assert "renderBilling" in js
    assert "/customer/inbox" in enhancements
    assert "conversation-channel" in enhancements
    assert "capability_module" in enhancements
    assert "module=${encodeURIComponent(moduleName)}" in enhancements
    assert 'router = APIRouter(prefix="/customer/inbox"' in inbox_source
    assert '"online_payments_enabled": False' in api_source
