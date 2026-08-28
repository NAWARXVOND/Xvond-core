from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.core.ai import provider_policy
from backend.app.core.ai.routing_quality import (
    current_quality_tier_cap,
    effective_required_quality_tier,
    set_quality_tier_cap,
)
from backend.app.core.database.base import Base
from backend.app.modules.providers.models import (
    AIModelRecord,
    AIProviderRecord,
    CompanyAIProfile,
)
from backend.app.modules.solutions.catalog import AI_AGENT_PACKAGE_QUALITY_CAPS


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


def add_model(db, provider, model, input_price, output_price, priority=10):
    if db.query(AIProviderRecord).filter(AIProviderRecord.name == provider).first() is None:
        db.add(
            AIProviderRecord(
                name=provider,
                display_name=provider,
                enabled=True,
                priority=priority,
            )
        )
    db.add(
        AIModelRecord(
            provider_name=provider,
            model_name=model,
            display_name=model,
            enabled=True,
            input_price_per_million=Decimal(str(input_price)),
            output_price_per_million=Decimal(str(output_price)),
        )
    )
    db.commit()


def seed_quality_models(db):
    add_model(db, "groq", "openai/gpt-oss-20b", "0.075", "0.30", priority=5)
    add_model(db, "groq", "openai/gpt-oss-120b", "0.15", "0.60", priority=5)
    add_model(db, "openai", "gpt-5.6-luna", "0.20", "1.20", priority=10)
    add_model(db, "openai", "gpt-5.6-terra", "2.00", "12.00", priority=10)
    add_model(db, "openai", "gpt-5.6-sol", "4.00", "20.00", priority=10)


def test_commercial_tiers_have_safe_quality_defaults():
    assert AI_AGENT_PACKAGE_QUALITY_CAPS == {
        "starter": 2,
        "business": 3,
        "enterprise": 4,
    }


def test_starter_cap_never_routes_to_advanced_or_premium(monkeypatch):
    engine, db = make_db()
    try:
        seed_quality_models(db)
        monkeypatch.setattr(provider_policy.ai_engine, "list_providers", lambda: ["groq", "openai"])
        set_quality_tier_cap(2)
        selections = provider_policy.runtime_selections(
            db,
            1,
            None,
            None,
            message="أريد تحليل عميق للمشكلة مع استراتيجية تفصيلية",
        )
        assert selections
        assert all(item.model not in {"gpt-5.6-terra", "gpt-5.6-sol"} for item in selections)
        assert selections[0].model == "openai/gpt-oss-120b"
        assert current_quality_tier_cap() is None
        assert effective_required_quality_tier("تحليل عميق للمشكلة") == 4
    finally:
        set_quality_tier_cap(None)
        db.close()
        engine.dispose()


def test_business_cap_allows_advanced_but_not_premium(monkeypatch):
    engine, db = make_db()
    try:
        seed_quality_models(db)
        monkeypatch.setattr(provider_policy.ai_engine, "list_providers", lambda: ["groq", "openai"])
        set_quality_tier_cap(3)
        selections = provider_policy.runtime_selections(
            db,
            2,
            None,
            None,
            message="حلل الخيارات وقارن بينها حسب عدة شروط للعميل",
        )
        assert selections[0].model == "gpt-5.6-terra"
        assert all(item.model != "gpt-5.6-sol" for item in selections)
        assert current_quality_tier_cap() is None
    finally:
        set_quality_tier_cap(None)
        db.close()
        engine.dispose()


def test_enterprise_cap_allows_premium(monkeypatch):
    engine, db = make_db()
    try:
        seed_quality_models(db)
        monkeypatch.setattr(provider_policy.ai_engine, "list_providers", lambda: ["groq", "openai"])
        set_quality_tier_cap(4)
        selections = provider_policy.runtime_selections(
            db,
            3,
            None,
            None,
            message="أريد تحليل عميق للمشكلة مع استراتيجية تفصيلية",
        )
        assert selections[0].model == "gpt-5.6-sol"
        assert current_quality_tier_cap() is None
    finally:
        set_quality_tier_cap(None)
        db.close()
        engine.dispose()


def test_company_default_above_plan_cap_is_skipped(monkeypatch):
    engine, db = make_db()
    try:
        seed_quality_models(db)
        db.add(
            CompanyAIProfile(
                company_id=44,
                default_provider="openai",
                default_model="gpt-5.6-sol",
                allow_fallback=True,
            )
        )
        db.commit()
        monkeypatch.setattr(provider_policy.ai_engine, "list_providers", lambda: ["groq", "openai"])
        set_quality_tier_cap(2)
        selections = provider_policy.runtime_selections(db, 44, None, None, message="مرحبا")
        assert all(item.model != "gpt-5.6-sol" for item in selections)
        assert selections[0].model == "openai/gpt-oss-20b"
        assert current_quality_tier_cap() is None
    finally:
        set_quality_tier_cap(None)
        db.close()
        engine.dispose()


def test_invalid_quality_cap_is_rejected_and_resettable():
    set_quality_tier_cap(None)
    with pytest.raises(ValueError):
        set_quality_tier_cap(5)
    set_quality_tier_cap(3)
    assert current_quality_tier_cap() == 3
    set_quality_tier_cap(None)
    assert current_quality_tier_cap() is None
