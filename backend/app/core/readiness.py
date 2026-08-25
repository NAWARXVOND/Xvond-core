from datetime import UTC, datetime

from backend.app.core.ai.provider_policy import runtime_selections
from backend.app.core.config.settings import settings
from backend.app.core.config_secrets import (
    configured_secret_fields,
    public_config,
    reveal_config,
)
from backend.app.models.company import Company
from backend.app.models.company_module import CompanyModule
from backend.app.models.company_profile import CompanyProfile
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.ai_agent.profile_models import AIAgentProfile
from backend.app.modules.billing.service_models import ServicePlan, ServiceSubscription
from backend.app.modules.channels.catalog import validate_channel_config
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.integrations.catalog import validate_integration_config
from backend.app.modules.integrations.models import CompanyIntegration
from backend.app.modules.knowledge.models import AgentKnowledge, KnowledgeDocument
from backend.app.modules.tools.executor import tool_executor
from backend.app.modules.tools.models import AgentToolAssignment


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def validate_config(
    validator,
    item_type: str,
    config: dict,
) -> tuple[bool, str | None]:
    try:
        validator(item_type, config or {})
        return True, None
    except ValueError as exc:
        return False, str(exc)


def _service_subscription(db, company_id: int):
    subscription = (
        db.query(ServiceSubscription)
        .filter(
            ServiceSubscription.company_id == company_id,
            ServiceSubscription.service_code == "ai_agents",
        )
        .first()
    )
    if subscription is None:
        return None, None, False
    plan = (
        db.query(ServicePlan)
        .filter(
            ServicePlan.id == subscription.plan_id,
            ServicePlan.service_code == "ai_agents",
            ServicePlan.enabled.is_(True),
        )
        .first()
    )
    now = _utcnow_naive()
    active = bool(
        subscription.status == "active"
        and subscription.current_period_start <= now < subscription.current_period_end
        and plan is not None
    )
    return subscription, plan, active


def _provider_runtime(db, company_id: int, agent: AIAgent):
    try:
        selections = runtime_selections(
            db,
            company_id,
            agent.provider,
            agent.model,
        )
    except Exception as exc:
        return [], str(exc)
    real = [selection for selection in selections if selection.provider != "mock"]
    return real, None


def company_readiness(db, company_id: int):
    company = db.query(Company).filter(Company.id == company_id).first()
    if company is None:
        return None

    company_profile = (
        db.query(CompanyProfile)
        .filter(CompanyProfile.company_id == company_id)
        .first()
    )
    profile_missing = []
    if company_profile is None:
        profile_missing = [
            "business_type",
            "country",
            "timezone",
            "primary_language",
        ]
    else:
        for field in (
            "business_type",
            "country",
            "timezone",
            "primary_language",
        ):
            if not str(getattr(company_profile, field, None) or "").strip():
                profile_missing.append(field)
    company_profile_ready = not profile_missing

    modules = (
        db.query(CompanyModule)
        .filter(
            CompanyModule.company_id == company_id,
            CompanyModule.enabled.is_(True),
        )
        .all()
    )

    subscription, subscription_plan, subscription_ready = _service_subscription(
        db, company_id
    )

    agents = (
        db.query(AIAgent)
        .filter(AIAgent.company_id == company_id)
        .order_by(AIAgent.id.asc())
        .all()
    )

    integrations = (
        db.query(CompanyIntegration)
        .filter(
            CompanyIntegration.company_id == company_id,
            CompanyIntegration.enabled.is_(True),
        )
        .all()
    )
    integration_results = []
    for item in integrations:
        configured, error = validate_config(
            validate_integration_config,
            item.integration_type,
            reveal_config(item.config),
        )
        integration_results.append(
            {
                "id": item.id,
                "type": item.integration_type,
                "name": item.name,
                "enabled": item.enabled,
                "configured": configured,
                "config": public_config(item.config),
                "configured_secret_fields": configured_secret_fields(item.config),
                "issue": error,
            }
        )

    agent_results = []
    for agent in agents:
        profile = (
            db.query(AIAgentProfile)
            .filter(
                AIAgentProfile.agent_id == agent.id,
                AIAgentProfile.company_id == company_id,
            )
            .first()
        )
        knowledge_count = (
            db.query(AgentKnowledge)
            .join(
                KnowledgeDocument,
                KnowledgeDocument.id == AgentKnowledge.document_id,
            )
            .filter(
                AgentKnowledge.agent_id == agent.id,
                AgentKnowledge.enabled.is_(True),
                KnowledgeDocument.enabled.is_(True),
            )
            .count()
        )
        tools = (
            db.query(AgentToolAssignment)
            .filter(
                AgentToolAssignment.agent_id == agent.id,
                AgentToolAssignment.enabled.is_(True),
            )
            .all()
        )
        runtime_tools = tool_executor.get_agent_tools(db=db, agent_id=agent.id)
        ready_action = any(item.get("name") == "action_request" for item in runtime_tools)

        channels = (
            db.query(AgentChannel)
            .filter(
                AgentChannel.agent_id == agent.id,
                AgentChannel.enabled.is_(True),
            )
            .all()
        )
        channel_results = []
        for channel in channels:
            configured, error = validate_config(
                validate_channel_config,
                channel.channel_type,
                reveal_config(channel.config),
            )
            channel_results.append(
                {
                    "id": channel.id,
                    "type": channel.channel_type,
                    "enabled": channel.enabled,
                    "configured": configured,
                    "config": public_config(channel.config),
                    "configured_secret_fields": configured_secret_fields(
                        channel.config
                    ),
                    "issue": error,
                }
            )
        ready_channels = [item for item in channel_results if item["configured"]]

        provider_selections, provider_error = _provider_runtime(
            db, company_id, agent
        )
        provider_ready = bool(provider_selections)
        prompt_ready = bool((agent.system_prompt or "").strip())
        employee_profile_ready = profile is not None

        issues = []
        warnings = []
        if not provider_ready:
            issues.append(
                "No real routed AI provider/model is available"
                + (f": {provider_error}" if provider_error else "")
            )
        if not prompt_ready:
            issues.append("System prompt is empty")
        if not employee_profile_ready:
            issues.append("AI employee profile is missing")
        if knowledge_count == 0:
            issues.append("No enabled knowledge connected")
        if not channels:
            issues.append("No enabled channel assigned")
        elif not ready_channels:
            issues.append("Channel configuration is incomplete")
        if not agent.enabled:
            warnings.append(
                "AI employee is currently disabled and must be enabled before launch"
            )
        if tools and not ready_action:
            warnings.append(
                "Tools are assigned, but no configured customer action is runtime-ready"
            )

        agent_ready = bool(
            provider_ready
            and prompt_ready
            and employee_profile_ready
            and knowledge_count > 0
            and ready_channels
            and agent.enabled
        )
        agent_results.append(
            {
                "id": agent.id,
                "name": agent.name,
                "enabled": agent.enabled,
                "provider": agent.provider,
                "model": agent.model,
                "provider_ready": provider_ready,
                "provider_routes": [
                    {
                        "provider": selection.provider,
                        "model": selection.model,
                        "reason": selection.reason,
                    }
                    for selection in provider_selections
                ],
                "prompt_ready": prompt_ready,
                "profile_exists": employee_profile_ready,
                "knowledge_count": knowledge_count,
                "tool_count": len(tools),
                "ready_action": ready_action,
                "channels": channel_results,
                "ready": agent_ready,
                "issues": issues,
                "warnings": warnings,
            }
        )

    ready_agents = [item for item in agent_results if item["ready"]]
    company_issues = []
    company_warnings = []

    if not company_profile_ready:
        company_issues.append(
            "Company profile is incomplete: " + ", ".join(profile_missing)
        )
    if not subscription_ready:
        company_issues.append("No active AI Agents service subscription")
    if not modules:
        company_issues.append("No active modules")
    if not agents:
        company_issues.append("No AI employees")
    elif not ready_agents:
        company_issues.append("No production-ready AI employee")
    if not company.active:
        company_warnings.append("Company is currently inactive")

    setup_ready = bool(
        company_profile_ready
        and subscription_ready
        and modules
        and ready_agents
    )
    if setup_ready and company.active:
        status = "ACTIVE"
    elif setup_ready:
        status = "READY_TO_ACTIVATE"
    else:
        status = "SETUP_REQUIRED"

    subscription_data = None
    if subscription is not None:
        effective_status = subscription.status
        if (
            effective_status == "active"
            and subscription.current_period_end <= _utcnow_naive()
        ):
            effective_status = "expired"
        subscription_data = {
            "id": subscription.id,
            "plan_id": subscription.plan_id,
            "plan_name": subscription_plan.name if subscription_plan else None,
            "status": effective_status,
            "current_period_start": subscription.current_period_start,
            "current_period_end": subscription.current_period_end,
            "service_code": "ai_agents",
        }

    return {
        "company": {
            "id": company.id,
            "name": company.name,
            "active": company.active,
        },
        "company_profile_ready": company_profile_ready,
        "company_profile_missing": profile_missing,
        "ready": setup_ready,
        "setup_ready": setup_ready,
        "status": status,
        "subscription_ready": subscription_ready,
        "subscription": subscription_data,
        "modules": [item.module_name for item in modules],
        "agents": agent_results,
        "integrations": integration_results,
        "issues": company_issues,
        "warnings": company_warnings,
        "runtime_environment": settings.APP_ENV,
    }
