import re
from pathlib import Path


ADMIN_DIR = Path("frontend/admin")
INDEX = ADMIN_DIR / "index.html"


def test_admin_scripts_are_loaded_once():
    html = INDEX.read_text(encoding="utf-8-sig")
    scripts = re.findall(r'<script\\s+src="([^"]+)"', html)

    assert len(scripts) == len(set(scripts))
    assert not any("pilot" in script for script in scripts)


def test_legacy_pilot_files_are_removed():
    assert not (ADMIN_DIR / "pilot.js").exists()
    assert not (ADMIN_DIR / "pilot_upgrade.js").exists()
