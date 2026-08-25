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


def add_provider(db, provider, model, enabled=True):
    db.add(
        AIProviderRecord(
            name=provider,
            display_name=provider,
            enabled=enabled,
            priority=10,
        )
    )
    db.add(
        AIModelRecord(
            provider_name=provider,
            model_name=model,
            display_name=model,
            enabled=enabled,
        )
    )
    db.commit()


def test_provider_model_must_be_loaded_and_enabled(monkeypatch):
    db = make_db()
    try:
        add_provider(db, "groq", "model-a")
        monkeypatch.setattr(
            provider_policy.ai_engine,
            "list_providers",
            lambda: ["groq"],
        )

        selected = provider_policy.require_provider_model(
            db,
            "groq",
            "model-a",
        )
        assert selected.provider == "groq"
        assert selected.model == "model-a"

        assert not provider_policy.provider_model_available(
            db,
            "groq",
            "missing",
        )
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

        monkeypatch.setattr(
            provider_policy.ai_engine,
            "list_providers",
            lambda: ["groq", "openai"],
        )

        selections = provider_policy.runtime_selections(
            db,
            42,
            "groq",
            "primary-model",
        )
        assert [
            (item.provider, item.model)
            for item in selections
        ] == [
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

        monkeypatch.setattr(
            provider_policy.ai_engine,
            "list_providers",
            lambda: ["groq", "openai"],
        )

        selections = provider_policy.runtime_selections(
            db,
            7,
            "groq",
            "primary-model",
        )
        assert len(selections) == 1
    finally:
        db.close()
