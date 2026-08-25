import re
from pathlib import Path


ADMIN_DIR = Path("frontend/admin")
INDEX = ADMIN_DIR / "index.html"


def test_admin_scripts_are_loaded_once():
    html = INDEX.read_text(encoding="utf-8-sig")
    scripts = re.findall(r'<script\s+src="([^"]+)"', html)

    assert len(scripts) == len(set(scripts))
    assert not any("pilot" in script for script in scripts)
    assert "/static/admin/company-control-center-runtime.js" in scripts
    assert "/static/admin/employee-workspace.js" in scripts
    assert scripts.index("/static/admin/employee-workspace.js") > scripts.index(
        "/static/admin/company-control-center-runtime.js"
    )


def test_legacy_pilot_files_are_removed():
    assert not (ADMIN_DIR / "pilot.js").exists()
    assert not (ADMIN_DIR / "pilot_upgrade.js").exists()


def test_ai_employee_profile_does_not_duplicate_company_or_fixed_operations():
    legacy = (ADMIN_DIR / "simple-company.js").read_text(encoding="utf-8-sig")
    profile = (ADMIN_DIR / "employee-capabilities.js").read_text(encoding="utf-8-sig")
    workspace = (ADMIN_DIR / "employee-workspace.js").read_text(encoding="utf-8-sig")

    assert "simple-business-name" not in legacy
    assert "simple-business-type" not in legacy
    assert "simple-booking-system" not in legacy
    assert "simple-order-system" not in legacy
    assert "Booking System" not in profile
    assert "Xvond Orders" not in profile
    assert "Information → Knowledge → Actions → Channels → Conversations" in workspace
