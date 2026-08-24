from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKUP = (ROOT / "scripts" / "backup_postgres.sh").read_text()
RESTORE = (ROOT / "scripts" / "restore_postgres.sh").read_text()


def test_backup_is_private_atomic_and_checksummed():
    assert "umask 077" in BACKUP
    assert ".partial" in BACKUP
    assert 'mv "$partial_path" "$final_path"' in BACKUP
    assert 'sha256sum "$final_path"' in BACKUP


def test_backup_has_retention_policy():
    assert "BACKUP_RETENTION_DAYS" in BACKUP
    assert "-mtime" in BACKUP
    assert "-delete" in BACKUP


def test_restore_requires_explicit_confirmation():
    assert "CONFIRM_RESTORE" in RESTORE
    assert "RESTORE_XVOND_DATABASE" in RESTORE


def test_restore_verifies_checksum_before_running():
    checksum_position = RESTORE.index('sha256sum --check')
    restore_position = RESTORE.index('pg_restore')
    assert checksum_position < restore_position


def test_restore_is_transactional_and_stops_on_error():
    assert "--single-transaction" in RESTORE
    assert "--exit-on-error" in RESTORE
