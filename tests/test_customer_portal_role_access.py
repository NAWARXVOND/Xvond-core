from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PORTAL_API = ROOT / "backend" / "app" / "api" / "customer_portal.py"
AGENTS_API = ROOT / "backend" / "app" / "api" / "ai_agents.py"
CUSTOMER_AGENTS_API = ROOT / "backend" / "app" / "api" / "customer_agents.py"
USERS_API = ROOT / "backend" / "app" / "api" / "users.py"
MANAGER_UI = ROOT / "frontend" / "customer" / "manager-controls.js"
PORTAL_HTML = ROOT / "frontend" / "customer" / "index.html"


def test_staff_overview_is_dashboard_only_and_omits_management_payloads():
    source = PORTAL_API.read_text(encoding="utf-8-sig")
    assert '"access_level": "staff"' in source
    assert '"navigation": [' in source
    assert '"id": "dashboard"' in source
    assert '"services": []' in source
    assert '"billing": {}' in source
    assert '"channels": []' in source
    assert '"integrations": []' in source
    assert 'if current_user.role not in MANAGER_ROLES:' in source


def test_manager_overview_gets_users_navigation_and_management_access_level():
    source = PORTAL_API.read_text(encoding="utf-8-sig")
    assert '"access_level": "manager"' in source
    assert '"id": "users"' in source
    assert '"loader": "users"' in source


def test_ai_employee_portal_apis_require_customer_manager():
    source = AGENTS_API.read_text(encoding="utf-8-sig")
    assert "from backend.app.core.dependencies import require_customer_manager" in source
    assert source.count("Depends(require_customer_manager)") >= 4
    list_section = source.split('@router.get("/")', 1)[1].split('@router.post', 1)[0]
    assert '"provider"' not in list_section
    assert '"model"' not in list_section


def test_customer_agent_management_is_manager_only_and_never_exposes_provider_model():
    source = CUSTOMER_AGENTS_API.read_text(encoding="utf-8-sig")
    assert "Depends(require_customer_manager)" in source
    assert '"provider"' not in source
    assert '"model"' not in source
    assert "controls.get(\"can_enable_disable\", False)" in source
    assert "controls.get(\"can_edit_prompt\")" in source
    assert "_profile_prompt(company.name, update)" in source
    assert "_sync_channel_setup" in source


def test_company_manager_can_create_only_staff_or_manager_accounts():
    source = USERS_API.read_text(encoding="utf-8-sig")
    assert "Depends(require_customer_manager)" in source
    assert 'role not in {"manager", "employee"}' in source
    assert "User.company_id == current_user.company_id" in source
    assert 'target.role in {"owner", "admin"}' in source
    assert "You cannot disable your own account" in source


def test_customer_manager_ui_exposes_simple_behavior_and_user_controls():
    source = MANAGER_UI.read_text(encoding="utf-8-sig")
    assert "customerManagerAccess" in source
    assert "Staff — Overview only" in source
    assert "Manager — Management access" in source
    assert "/customer/agents/${agentId}" in source
    assert 'customerSelect("ca-length"' in source
    assert 'customerSelect("ca-clarification"' in source
    assert 'customerSelect("ca-off-topic"' in source
    assert "controls.can_edit_prompt" in source
    assert 'api("/users/")' in source
    assert "loadCompanyUsers" in source


def test_manager_controls_load_after_portal_enhancements_and_before_session_start():
    html = PORTAL_HTML.read_text(encoding="utf-8-sig")
    enhancements = html.index("/static/customer/portal-enhancements.js")
    manager = html.index("/static/customer/manager-controls.js")
    session = html.index("/static/customer/session-security.js")
    assert enhancements < manager < session
