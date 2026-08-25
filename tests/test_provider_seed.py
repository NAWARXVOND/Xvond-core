from decimal import Decimal

from xvond_seed_providers import MODELS, PROVIDERS


def test_provider_seed_has_unique_names():
    names = [
        name
        for name, _display_name, _priority in PROVIDERS
    ]
    assert len(names) == len(set(names))
    assert names.count("groq") == 1


def test_groq_seed_uses_current_production_models_and_prices():
    models = {
        model_name: (
            input_price,
            output_price,
        )
        for (
            provider,
            model_name,
            _display_name,
            input_price,
            output_price,
        ) in MODELS
        if provider == "groq"
    }

    assert models["openai/gpt-oss-20b"] == (
        Decimal("0.075"),
        Decimal("0.30"),
    )
    assert models["openai/gpt-oss-120b"] == (
        Decimal("0.15"),
        Decimal("0.60"),
    )
