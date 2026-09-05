from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.core.database.base import Base
from backend.app.core.ai import provider_policy
from backend.app.core.ai.routing_quality import (
    model_quality_tier,
    required_quality_tier,
)
from backend.app.modules.providers.models import (
    AIModelRecord,
    AIProviderRecord,
    CompanyAIProfile,
)


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            AIProviderRecord.__table__,
            AIModelRecord.__table__,
            CompanyAIProfile.__table__,
        ],
    )
    return engine, Session(engine)


def close_db(engine, db):
    db.close()
    engine.dispose()


def add_provider(db, provider, model, enabled=True, priority=10, input_price="0", output_price="0"):
    db.add(
        AIProviderRecord(
            name=provider,
            display_name=provider,
            enabled=enabled,
            priority=priority,
        )
    )
    db.add(
        AIModelRecord(
            provider_name=provider,
            model_name=model,
            display_name=model,
            enabled=enabled,
            input_price_per_million=Decimal(input_price),
            output_price_per_million=Decimal(output_price),
        )
    )
    db.commit()


def test_provider_model_must_be_loaded_and_enabled(monkeypatch):
    engine, db = make_db()
    try:
        add_provider(db, "openai", "model-a")
        monkeypatch.setattr(provider_policy.ai_engine, "list_providers", lambda: ["openai"])
        selected = provider_policy.require_provider_model(db, "openai", "model-a")
        assert selected.provider == "openai"
        assert selected.model == "model-a"
        assert not provider_policy.provider_model_available(db, "openai", "missing")
    finally:
        close_db(engine, db)


def test_runtime_selections_adds_enabled_company_fallback(monkeypatch):
    engine, db = make_db()
    try:
        add_provider(db, "openai", "primary-model")
        add_provider(db, "anthropic", "fallback-model")
        db.add(
            CompanyAIProfile(
                company_id=42,
                default_provider="openai",
                default_model="primary-model",
                allow_fallback=True,
                fallback_provider="anthropic",
                fallback_model="fallback-model",
            )
        )
        db.commit()
        monkeypatch.setattr(provider_policy.ai_engine, "list_providers", lambda: ["openai", "anthropic"])
        selections = provider_policy.runtime_selections(db, 42, "openai", "primary-model")
        assert [(item.provider, item.model) for item in selections] == [
            ("openai", "primary-model"),
            ("anthropic", "fallback-model"),
        ]
    finally:
        close_db(engine, db)


def test_disabled_fallback_is_not_selected(monkeypatch):
    engine, db = make_db()
    try:
        add_provider(db, "openai", "primary-model")
        add_provider(db, "anthropic", "fallback-model", enabled=False)
        db.add(
            CompanyAIProfile(
                company_id=7,
                allow_fallback=True,
                fallback_provider="anthropic",
                fallback_model="fallback-model",
            )
        )
        db.commit()
        monkeypatch.setattr(provider_policy.ai_engine, "list_providers", lambda: ["openai", "anthropic"])
        selections = provider_policy.runtime_selections(db, 7, "openai", "primary-model")
        assert len(selections) == 1
    finally:
        close_db(engine, db)


def test_runtime_selections_prefers_cheapest_reliable_candidates(monkeypatch):
    engine, db = make_db()
    try:
        add_provider(db, "openai", "openai-model", priority=10, input_price="1", output_price="2")
        add_provider(db, "anthropic", "claude-model", priority=20, input_price="1", output_price="3")
        add_provider(db, "google", "gemini-model", priority=30, input_price="0.1", output_price="0.2")
        add_provider(db, "xai", "xai-model", priority=40, input_price="0.2", output_price="0.4")
        monkeypatch.setattr(
            provider_policy.ai_engine,
            "list_providers",
            lambda: ["openai", "anthropic", "google", "xai"],
        )
        selections = provider_policy.runtime_selections(db, 99, None, None)
        assert [(item.provider, item.model) for item in selections] == [
            ("google", "gemini-model"),
            ("xai", "xai-model"),
            ("openai", "openai-model"),
            ("anthropic", "claude-model"),
        ]
        assert all(item.reason.startswith("automatic:tier") for item in selections)
    finally:
        close_db(engine, db)


def test_company_default_precedes_automatic_route(monkeypatch):
    engine, db = make_db()
    try:
        add_provider(db, "openai", "openai-model", priority=10)
        add_provider(db, "anthropic", "claude-model", priority=20)
        db.add(
            CompanyAIProfile(
                company_id=55,
                default_provider="anthropic",
                default_model="claude-model",
                allow_fallback=True,
            )
        )
        db.commit()
        monkeypatch.setattr(provider_policy.ai_engine, "list_providers", lambda: ["openai", "anthropic"])
        selections = provider_policy.runtime_selections(db, 55, "openai", "openai-model")
        assert [(item.provider, item.model) for item in selections] == [
            ("anthropic", "claude-model"),
            ("openai", "openai-model"),
        ]
        assert selections[0].reason == "company_default"
    finally:
        close_db(engine, db)


def test_quality_tiers_match_commercial_model_bands():
    assert model_quality_tier("openai", "gpt-5-mini") == 2
    assert model_quality_tier("openai", "gpt-5.6-luna") == 2
    assert model_quality_tier("openai", "gpt-5.6-terra") == 3
    assert model_quality_tier("openai", "gpt-5.6-sol") == 4


def test_message_complexity_promotes_only_when_needed():
    assert required_quality_tier("مرحبا") == 1
    assert required_quality_tier("بدي احجز موعد بكرا الساعة خمسة") == 2
    assert required_quality_tier("حلل الخيارات وقارن بينها حسب عدة شروط للعميل") == 3
    assert required_quality_tier("أريد تحليل عميق للمشكلة مع استراتيجية تفصيلية") == 4


def test_runtime_message_classifier_ignores_grounding_policy_keywords():
    runtime_message = (
        "Never claim a booking or order succeeded.\n\n"
        "CURRENT CUSTOMER MESSAGE (answer this intent directly):\nمرحبا"
    )
    assert required_quality_tier(runtime_message) == 1


def test_advanced_request_filters_out_weak_models(monkeypatch):
    engine, db = make_db()
    try:
        add_provider(db, "openai", "gpt-5.6-luna", priority=5, input_price="0.20", output_price="1.20")
        add_provider(db, "openai", "gpt-5.6-terra", priority=10, input_price="2", output_price="12")
        monkeypatch.setattr(provider_policy.ai_engine, "list_providers", lambda: ["openai"])
        selections = provider_policy.runtime_selections(
            db,
            77,
            None,
            None,
            message="حلل الخيارات وقارن بينها حسب عدة شروط للعميل",
        )
        assert [(item.provider, item.model) for item in selections] == [
            ("openai", "gpt-5.6-terra"),
        ]
    finally:
        close_db(engine, db)
