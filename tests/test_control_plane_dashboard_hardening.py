import inspect
from pathlib import Path

from backend.app.api import admin_dashboard, customer_inbox, customer_portal, usage


ROOT = Path(__file__).resolve().parents[1]


def test_admin_dashboard_exposes_operational_health_not_only_totals():
    source = inspect.getsource(admin_dashboard.summary)
    assert '"last_24h"' in source
    assert '"attention"' in source
    assert '"active_companies_without_active_employee"' in source
    assert '"active_employees_without_active_channel"' in source
    assert '"failed_ai_requests_24h"' in source
    assert '"active_handoffs"' in source
    assert '"subscriptions_expiring_7d"' in source


def test_admin_dashboard_system_assets_are_loaded():
    html = (ROOT / "frontend/admin/index.html").read_text(encoding="utf-8")
    assert "/static/admin/dashboard-system.css?v=20260914-1" in html
    assert "/static/admin/dashboard-system.js?v=20260914-1" in html
    assert "admin@xvond.com" not in html


def test_customer_overview_exposes_manager_operational_health():
    source = inspect.getsource(customer_portal.overview)
    assert '"health"' in source
    assert '"active_handoffs"' in source
    assert '"failed_ai_requests_24h"' in source
    assert '"active_agents_without_channel"' in source
    assert '"service_alerts"' in source


def test_customer_inbox_is_paginated_and_avoids_per_conversation_handoff_queries():
    source = inspect.getsource(customer_inbox.list_inbox)
    assert "Query(default=75, ge=1, le=200)" in source
    assert '"pagination"' in source
    assert ".limit(500)" not in source
    assert "message_stats" in source
    assert "session_by_conversation" in source
    assert "handoff_by_conversation" in source
    assert "_handoff_state(db" not in source


def test_customer_inbox_exposes_reply_capability_to_the_ui():
    meta = inspect.getsource(customer_inbox._conversation_meta)
    ui = (ROOT / "frontend/customer/handoff-inbox.js").read_text(encoding="utf-8")
    assert '"reply_capability"' in meta
    assert "reply_capability" in ui
    assert "inboxPageLimit" in ui
    assert "changeInboxPage" in ui


def test_customer_usage_uses_canonical_service_subscription_cycle():
    source = inspect.getsource(usage.my_usage)
    module = (ROOT / "backend/app/api/usage.py").read_text(encoding="utf-8")
    assert "ServiceSubscription" in module
    assert "ServicePlan" in module
    assert "modules.billing.models" not in module
    assert "current_billing_cycle" not in module
    assert 'ServiceSubscription.service_code == "ai_agents"' in source
    assert "ServiceSubscription.current_period_start" in source
    assert "ServiceSubscription.current_period_end" in source
    assert 'AIUsage.status != "success"' in source
    assert 'AIUsage.status == "success"' in source
