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
    assert "/static/admin/company-control-center-runtime.js" not in scripts
    assert "/static/admin/employee-workspace.js" not in scripts
    assert not (ADMIN_DIR / "company-control-center-runtime.js").exists()
    assert not (ADMIN_DIR / "employee-workspace.js").exists()


def test_legacy_pilot_files_are_removed():
    assert not (ADMIN_DIR / "pilot.js").exists()
    assert not (ADMIN_DIR / "pilot_upgrade.js").exists()


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
    assert "openEditAgent" not in app
    assert "/static/admin/services.js" not in index
    assert "/static/admin/business.js" not in index
