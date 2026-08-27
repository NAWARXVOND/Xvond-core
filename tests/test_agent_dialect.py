import pytest

from backend.app.modules.ai_agent.dialect import dialect_prompt, normalize_dialect


def test_auto_dialect_matches_customer_and_avoids_default_fusha():
    prompt = dialect_prompt("auto")
    assert "closest matching colloquial dialect" in prompt
    assert "Do not default to Modern Standard Arabic" in prompt


def test_fixed_levantine_dialect_is_explicit():
    prompt = dialect_prompt("levantine")
    assert "Levantine/Shami Arabic" in prompt
    assert "consistently" in prompt


def test_supported_dialects_include_gulf_and_fusha():
    assert normalize_dialect("gulf") == "gulf"
    assert normalize_dialect("msa") == "msa"


def test_invalid_dialect_rejected():
    with pytest.raises(ValueError):
        normalize_dialect("martian")
