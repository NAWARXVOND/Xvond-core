from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.core.database.base import Base
from backend.app.core.ai import provider_policy
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
    return Session(engine)


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
    db = make_db()
    try:
        add_provider(db, "groq", "model-a")
        monkeypatch.setattr(provider_policy.ai_engine, "list_providers", lambda: ["groq"])
        selected = provider_policy.require_provider_model(db, "groq", "model-a")
        assert selected.provider == "groq"
        assert selected.model == "model-a"
        assert not provider_policy.provider_model_available(db, "groq", "missing")
    finally:
        db.close()


def test_runtime_selections_adds_enabled_company_fallback(monkeypatch):
    db = make_db()
    try:
        add_provider(db, "groq", "primary-model")
        add_provider(db, "openai", "fallback-model")
        db.add(
            CompanyAIProfile(
                company_id=42,
                default_provider="groq",
                default_model="primary-model",
                allow_fallback=True,
                fallback_provider="openai",
                fallback_model="fallback-model",
            )
        )
        db.commit()
        monkeypatch.setattr(provider_policy.ai_engine, "list_providers", lambda: ["groq", "openai"])
        selections = provider_policy.runtime_selections(db, 42, "groq", "primary-model")
        assert [(item.provider, item.model) for item in selections] == [
            ("groq", "primary-model"),
            ("openai", "fallback-model"),
        ]
    finally:
        db.close()


def test_disabled_fallback_is_not_selected(monkeypatch):
    db = make_db()
    try:
        add_provider(db, "groq", "primary-model")
        add_provider(db, "openai", "fallback-model", enabled=False)
        db.add(
            CompanyAIProfile(
                company_id=7,
                allow_fallback=True,
                fallback_provider="openai",
                fallback_model="fallback-model",
            )
        )
        db.commit()
        monkeypatch.setattr(provider_policy.ai_engine, "list_providers", lambda: ["groq", "openai"])
        selections = provider_policy.runtime_selections(db, 7, "groq", "primary-model")
        assert len(selections) == 1
    finally:
        db.close()


def test_runtime_selections_include_all_loaded_enabled_providers(monkeypatch):
    db = make_db()
    try:
        add_provider(db, "groq", "groq-model", priority=40, input_price="0.2", output_price="0.4")
        add_provider(db, "openai", "openai-model", priority=10, input_price="1", output_price="2")
        add_provider(db, "anthropic", "claude-model", priority=20, input_price="1", output_price="3")
        add_provider(db, "google", "gemini-model", priority=30, input_price="0.1", output_price="0.2")
        monkeypatch.setattr(
            provider_policy.ai_engine,
            "list_providers",
            lambda: ["groq", "openai", "anthropic", "google"],
        )
        selections = provider_policy.runtime_selections(db, 99, None, None)
        assert [(item.provider, item.model) for item in selections] == [
            ("openai", "openai-model"),
            ("anthropic", "claude-model"),
            ("google", "gemini-model"),
            ("groq", "groq-model"),
        ]
        assert all(item.reason == "automatic" for item in selections)
    finally:
        db.close()


def test_company_default_precedes_automatic_route(monkeypatch):
    db = make_db()
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
        db.close()
