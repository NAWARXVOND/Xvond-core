
from backend.app.core.database.connection import SessionLocal
from backend.app.modules.providers.models import AIProviderRecord

PROVIDERS = [
    ("openai", "OpenAI", 10),
    ("anthropic", "Anthropic", 20),
    ("google", "Google Gemini", 30),
    ("xai", "xAI", 40),
    ("mock", "Mock Development", 999),
]

db = SessionLocal()

try:
    for name, display_name, priority in PROVIDERS:

        item = (
            db.query(AIProviderRecord)
            .filter(
                AIProviderRecord.name == name
            )
            .first()
        )

        if item is None:
            item = AIProviderRecord(
                name=name,
                display_name=display_name,
                priority=priority,
                enabled=True,
            )
            db.add(item)

        else:
            item.display_name = display_name
            item.priority = priority

    db.commit()

    print("XVOND PROVIDER CATALOG SEEDED")

finally:
    db.close()
