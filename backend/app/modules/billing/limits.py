from sqlalchemy import func

from backend.app.core.config.settings import settings
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.billing.service_limits import service_limits
from backend.app.modules.channels.models import AgentChannel


class LimitsService:
    """Compatibility facade backed only by per-service billing.

    Legacy umbrella Plan/Subscription rows are no longer runtime authority.
    """

    def check_agent_limit(self, db, company_id: int):
        if not settings.is_production:
            return
        current = (
            db.query(func.count(AIAgent.id))
            .filter(
                AIAgent.company_id == company_id,
                AIAgent.enabled.is_(True),
            )
            .scalar()
            or 0
        )
        service_limits.check_current(
            db,
            company_id,
            "ai_agents",
            "agents",
            current,
            quantity=1,
        )

    def check_channel_limit(self, db, company_id: int):
        if not settings.is_production:
            return
        current = (
            db.query(func.count(AgentChannel.id))
            .filter(
                AgentChannel.company_id == company_id,
                AgentChannel.enabled.is_(True),
            )
            .scalar()
            or 0
        )
        service_limits.check_current(
            db,
            company_id,
            "ai_agents",
            "channels",
            current,
            quantity=1,
        )

    def check_token_limit(self, db, company_id: int):
        if not settings.is_production:
            return
        service_limits.record(
            db,
            company_id,
            "ai_agents",
            "requests",
            quantity=1,
        )


limits_service = LimitsService()
