from pathlib import Path

from xvond_seed_providers import MODELS, PROVIDERS, RETIRED_PROVIDERS


SOURCE = Path("xvond_seed_providers.py").read_text(encoding="utf-8")


def test_provider_seed_has_unique_supported_names():
    names = [
        name
        for name, _display_name, _priority in PROVIDERS
    ]
    assert len(names) == len(set(names))
    assert "groq" not in names
    assert "groq" in RETIRED_PROVIDERS


def test_provider_seed_never_advertises_models_for_retired_providers():
    assert all(provider not in RETIRED_PROVIDERS for provider, *_rest in MODELS)


def test_existing_retired_provider_and_model_rows_are_disabled_not_deleted():
    assert "def _disable_retired_provider_rows" in SOURCE
    assert "AIProviderRecord.name.in_(RETIRED_PROVIDERS)" in SOURCE
    assert "AIModelRecord.provider_name.in_(RETIRED_PROVIDERS)" in SOURCE
    assert "AIProviderRecord.enabled: False" in SOURCE
    assert "AIModelRecord.enabled: False" in SOURCE
    assert "db.delete(" not in SOURCE
