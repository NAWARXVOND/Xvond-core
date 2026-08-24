
from backend.app.core.database.connection import (
    SessionLocal,
)
from backend.app.core.database.hardening import (
    database_integrity_report,
)

from backend.app.core.ai.engine import (
    ai_engine,
)

from backend.app.modules.channels.models import (
    AgentChannel,
)

from backend.app.modules.ai_agent.models import (
    AIAgent,
)

from backend.app.modules.billing.models import (
    Subscription,
)

from backend.app.modules.audit.models import (
    AuditLog,
)


def run_system_check():

    db = SessionLocal()

    try:

        integrity = (
            database_integrity_report(
                db
            )
        )

        companies_with_active_subscription = (
            db.query(Subscription)
            .filter(
                Subscription.status
                == "active"
            )
            .count()
        )

        real_agents = (
            db.query(AIAgent)
            .filter(
                AIAgent.provider
                != "mock"
            )
            .count()
        )

        mock_agents = (
            db.query(AIAgent)
            .filter(
                AIAgent.provider
                == "mock"
            )
            .count()
        )

        enabled_channels = (
            db.query(AgentChannel)
            .filter(
                AgentChannel.enabled
                .is_(True)
            )
            .count()
        )

        return {
            "database":
                integrity,

            "providers":
                ai_engine.list_providers(),

            "agents": {
                "real":
                    real_agents,
                "mock":
                    mock_agents,
            },

            "enabled_channels":
                enabled_channels,

            "active_subscriptions":
                companies_with_active_subscription,

            "audit_logs":
                db.query(
                    AuditLog
                ).count(),
        }

    finally:
        db.close()
