"""Encrypt existing JSON configuration secrets in place.

Set CONFIG_ENCRYPTION_KEY before running this script. Keep the same key for the
lifetime of the environment; changing it makes existing encrypted values
unreadable.

Usage:
    python scripts/encrypt_existing_configs.py
"""

from backend.app.core.config.settings import settings
from backend.app.core.config_secrets import protect_config
from backend.app.core.database.connection import SessionLocal
from backend.app.modules.analytics.models import AnalyticsSource
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.integrations.models import CompanyIntegration
from backend.app.modules.tools.models import AgentToolAssignment


MODELS = (
    AgentChannel,
    CompanyIntegration,
    AgentToolAssignment,
    AnalyticsSource,
)


def encrypt_existing_configs() -> int:
    if not settings.CONFIG_ENCRYPTION_KEY:
        raise RuntimeError(
            "CONFIG_ENCRYPTION_KEY must be set before encrypting stored configs"
        )

    db = SessionLocal()
    updated = 0

    try:
        for model in MODELS:
            for item in db.query(model).all():
                current = dict(item.config or {})
                protected = protect_config(current)

                if protected != current:
                    item.config = protected
                    updated += 1

        db.commit()
        return updated
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    count = encrypt_existing_configs()
    print(f"Encrypted configuration for {count} record(s)")
