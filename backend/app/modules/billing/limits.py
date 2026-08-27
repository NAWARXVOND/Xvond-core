from sqlalchemy import func

from backend.app.core.ai.routing_quality import set_quality_tier_cap
from backend.app.core.config.settings import settings
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.billing.service_limits import service_limits
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.solutions.catalog import AI_AGENT_PACKAGE_QUALITY_CAPS


class LimitsService:
    """Compatibility facade backed only by per-service billing."""

    def check_agent_limit(self, db, company_id: int):
        if not settings.is_production:
            return
        current = db.query(func.count(AIAgent.id)).filter(
            AIAgent.company_id == company_id,
            AIAgent.enabled.is_(True),
        ).scalar() or 0
        service_limits.check_current(
            db, company_id, "ai_agents", "agents", current, quantity=1
        )

    def check_channel_limit(self, db, company_id: int):
        if not settings.is_production:
            return
        current = db.query(func.count(AgentChannel.id)).filter(
            AgentChannel.company_id == company_id,
            AgentChannel.enabled.is_(True),
        ).scalar() or 0
        service_limits.check_current(
            db, company_id, "ai_agents", "channels", current, quantity=1
        )

    def check_token_limit(self, db, company_id: int):
        if not settings.is_production:
            # Development/test must never inherit a package cap from another request.
            set_quality_tier_cap(None)
            return

        # Resolve the active plan once per chat and expose its model-quality ceiling
        # to the request-local Smart Router context. Plans may explicitly override
        # max_quality_tier; otherwise their commercial tier supplies the safe default.
        _subscription, plan = service_limits.entitlement(db, company_id, "ai_agents")
        explicit_cap = (plan.limits or {}).get("max_quality_tier")
        quality_cap = (
            explicit_cap
            if explicit_cap not in (None, "", 0, "0")
            else AI_AGENT_PACKAGE_QUALITY_CAPS.get(str(plan.tier or "").strip().lower())
        )
        try:
            set_quality_tier_cap(quality_cap)
        except ValueError as exc:
            raise RuntimeError(
                f"Invalid max_quality_tier in AI Agents plan {plan.id}: {exc}"
            ) from exc

        # Actual token usage is read from successful AIUsage rows. A request is
        # rejected once the current period has reached its configured token cap.
        service_limits.check(
            db,
            company_id,
            "ai_agents",
            "tokens",
            quantity=0,
        )
        # Requests are counted independently and transactionally. Provider
        # failures roll this event back with the chat transaction.
        service_limits.record(
            db,
            company_id,
            "ai_agents",
            "requests",
            quantity=1,
        )


limits_service = LimitsService()
