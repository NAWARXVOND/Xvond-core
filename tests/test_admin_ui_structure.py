import re
from pathlib import Path


ADMIN_DIR = Path("frontend/admin")
INDEX = ADMIN_DIR / "index.html"


def test_admin_scripts_are_loaded_once_and_workspace_is_consolidated():
    html = INDEX.read_text(encoding="utf-8-sig")
    scripts = re.findall(r'<script\s+src="([^"]+)"', html)

    assert len(scripts) == len(set(scripts))
    assert not any("pilot" in script for script in scripts)
    assert "/static/admin/company-control-center.js" in scripts
    assert "/static/admin/privacy-boundaries.js" in scripts
    assert scripts.index("/static/admin/privacy-boundaries.js") > scripts.index(
        "/static/admin/company-control-center.js"
    )
    assert "/static/admin/human-chat.js" not in scripts
    assert not any("company-control-center-runtime" in script for script in scripts)
    assert not any("employee-workspace" in script for script in scripts)
    assert not (ADMIN_DIR / "company-control-center-runtime.js").exists()
    assert not (ADMIN_DIR / "employee-workspace.js").exists()


def test_legacy_pilot_files_are_removed():
    assert not (ADMIN_DIR / "pilot.js").exists()
    assert not (ADMIN_DIR / "pilot_upgrade.js").exists()


def test_obsolete_admin_workspace_files_are_removed():
    obsolete = {
        "business.js",
        "company_workspace.js",
        "company_workspace_automation.js",
        "company_workspace_plans.js",
        "human-chat.js",
        "solutions.js",
    }
    for filename in obsolete:
        assert not (ADMIN_DIR / filename).exists(), filename


def test_ai_employee_profile_does_not_duplicate_company_or_fixed_operations():
    legacy = (ADMIN_DIR / "simple-company.js").read_text(encoding="utf-8-sig")
    profile = (ADMIN_DIR / "employee-capabilities.js").read_text(encoding="utf-8-sig")
    workspace = (ADMIN_DIR / "company-control-center.js").read_text(encoding="utf-8-sig")

    assert "simple-business-name" not in legacy
    assert "simple-business-type" not in legacy
    assert "simple-booking-system" not in legacy
    assert "simple-order-system" not in legacy
    assert "Booking System" not in profile
    assert "Xvond Orders" not in profile
    assert "Information → Knowledge → Actions → Channels → Conversations" in workspace


def test_company_profile_uses_canonical_catalog_and_service_billing():
    workspace = (ADMIN_DIR / "company-control-center.js").read_text(encoding="utf-8-sig")
    assert "p.catalog" in workspace
    assert "cp-type" in workspace and "<select" in workspace
    assert "/admin/service-billing/companies/" in workspace
    assert "/admin/billing/" not in workspace


def test_admin_shell_does_not_expose_legacy_agent_factory():
    app = (ADMIN_DIR / "app.js").read_text(encoding="utf-8-sig")
    index = INDEX.read_text(encoding="utf-8-sig")
    assert "agent-factory" not in app
    assert "openCreateAgentFromTemplate" not in app
    assert "/static/admin/services.js" not in index
    assert "/static/admin/business.js" not in index


def test_admin_privacy_boundary_keeps_customer_content_out_of_operator_ui():
    privacy = (ADMIN_DIR / "privacy-boundaries.js").read_text(encoding="utf-8-sig")

    assert "company_profile_ready" in privacy
    assert "Real Customer Operations" in privacy
    assert "requests: []" in privacy
    assert "conversations: []" in privacy
    assert "handoffs: []" in privacy
    assert "openHumanTakeover" in privacy

    # The privacy-aware loaders must not request tenant customer payloads.
    assert "/admin/agent-actions/companies/${companyId}/requests" not in privacy
    assert "/admin/operations/companies/${companyId}/conversations" not in privacy
    assert "/admin/handoff/companies/${companyId}/sessions" not in privacy


def test_admin_action_editor_preserves_intentional_state_mutations():
    privacy = (ADMIN_DIR / "privacy-boundaries.js").read_text(encoding="utf-8-sig")

    assert "renderAgentActionsAfterStateMutation" in privacy
    assert "skipCollectAfterMutation" in privacy
    assert "addCustomAgentAction = function" in privacy
    assert "removeAgentAction = function" in privacy
    assert "applySuggestedAgentActionTemplate = function" in privacy
