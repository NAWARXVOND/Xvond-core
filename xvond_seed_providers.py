from decimal import Decimal

from backend.app.core.database.connection import SessionLocal
from backend.app.modules.providers.models import (
    AIModelRecord,
    AIProviderRecord,
)


PROVIDERS = [
    ("groq", "Groq", 5),
    ("openai", "OpenAI", 10),
    ("anthropic", "Anthropic", 20),
    ("google", "Google Gemini", 30),
    ("xai", "xAI", 40),
    ("mock", "Mock Development", 999),
]

MODELS = [
    (
        "groq",
        "openai/gpt-oss-20b",
        "GPT OSS 20B",
        Decimal("0.075"),
        Decimal("0.30"),
    ),
    (
        "groq",
        "openai/gpt-oss-120b",
        "GPT OSS 120B",
        Decimal("0.15"),
        Decimal("0.60"),
    ),
    (
        "openai",
        "gpt-5.6-luna",
        "GPT-5.6 Luna",
        Decimal("0.20"),
        Decimal("1.20"),
    ),
    (
        "openai",
        "gpt-5.6-terra",
        "GPT-5.6 Terra",
        Decimal("2.00"),
        Decimal("12.00"),
    ),
    (
        "openai",
        "gpt-5.6-sol",
        "GPT-5.6 Sol",
        Decimal("4.00"),
        Decimal("20.00"),
    ),
]


def seed_provider_catalog() -> tuple[int, int]:
    db = SessionLocal()
    providers_seeded = 0
    models_seeded = 0

    try:
        for name, display_name, priority in PROVIDERS:
            item = (
                db.query(AIProviderRecord)
                .filter(AIProviderRecord.name == name)
                .first()
            )

            if item is None:
                item = AIProviderRecord(name=name)
                db.add(item)
                providers_seeded += 1

            item.display_name = display_name
            item.priority = priority
            item.enabled = True

        db.flush()

        for (
            provider_name,
            model_name,
            display_name,
            input_price,
            output_price,
        ) in MODELS:
            item = (
                db.query(AIModelRecord)
                .filter(
                    AIModelRecord.provider_name == provider_name,
                    AIModelRecord.model_name == model_name,
                )
                .first()
            )

            if item is None:
                item = AIModelRecord(
                    provider_name=provider_name,
                    model_name=model_name,
                )
                db.add(item)
                models_seeded += 1

            item.display_name = display_name
            item.input_price_per_million = input_price
            item.output_price_per_million = output_price
            item.enabled = True

        db.commit()
        return providers_seeded, models_seeded
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    provider_count, model_count = seed_provider_catalog()
    print(
        "XVOND PROVIDER CATALOG SEEDED "
        f"(providers={provider_count}, models={model_count})"
    )
