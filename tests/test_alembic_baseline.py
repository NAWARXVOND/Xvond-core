from pathlib import Path


BASELINE = Path(
    "migrations/versions/"
    "7b6697dc454a_baseline_existing_xvond_database.py"
).read_text(encoding="utf-8")


def test_baseline_uses_explicit_operations():
    assert "Base.metadata.create_all" not in BASELINE
    assert "Base.metadata.drop_all" not in BASELINE
    assert "from backend.app.core.database.base import Base" not in BASELINE
    assert "op.create_table(" in BASELINE
    assert "op.drop_table(" in BASELINE
    assert BASELINE.count("op.create_table(") >= 20


def test_baseline_revision_identity_is_stable():
    assert "revision: str = '7b6697dc454a'" in BASELINE
    assert (
        "down_revision: Union[str, Sequence[str], None] = None"
        in BASELINE
    )
