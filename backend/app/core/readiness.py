
from backend.app.core.ai.engine import ai_engine
from backend.app.core.config_secrets import (
    configured_secret_fields,
    public_config,
    reveal_config,
)

from backend.app.models.company import Company
from backend.app.models.company_module import (
    CompanyModule,
)

from backend.app.modules.ai_agent.factory_models import (
    AgentConfig,
)

from backend.app.modules.ai_agent.models import (
    AIAgent,
)

from backend.app.modules.billing.models import (
    Plan,
    Subscription,
)

from backend.app.modules.channels.catalog import (
    validate_channel_config,
)

from backend.app.modules.channels.models import (
    AgentChannel,
)

from backend.app.modules.integrations.catalog import (
    validate_integration_config,
)

from backend.app.modules.integrations.models import (
    CompanyIntegration,
)

from backend.app.modules.knowledge.models import (
    AgentKnowledge,
    KnowledgeDocument,
)

from backend.app.modules.tools.models import (
    AgentToolAssignment,
)


def validate_config(
    validator,
    item_type: str,
    config: dict,
) -> tuple[bool, str | None]:

    try:
        validator(
            item_type,
            config or {},
        )

        return True, None

    except ValueError as exc:

        return False, str(exc)


def company_readiness(
    db,
    company_id: int,
):

    company = (
        db.query(Company)
        .filter(
            Company.id == company_id
        )
        .first()
    )

    if company is None:
        return None

    modules = (
        db.query(CompanyModule)
        .filter(
            CompanyModule.company_id
            == company_id,
            CompanyModule.enabled
            .is_(True),
        )
        .all()
    )

    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.company_id
            == company_id,
            Subscription.status
            == "active",
        )
        .first()
    )

    subscription_plan = None

    if subscription is not None:

        subscription_plan = (
            db.query(Plan)
            .filter(
                Plan.id
                == subscription.plan_id,
                Plan.enabled
                .is_(True),
            )
            .first()
        )

    agents = (
        db.query(AIAgent)
        .filter(
            AIAgent.company_id
            == company_id
        )
        .order_by(
            AIAgent.id.asc()
        )
        .all()
    )

    integrations = (
        db.query(CompanyIntegration)
        .filter(
            CompanyIntegration.company_id
            == company_id,
            CompanyIntegration.enabled
            .is_(True),
        )
        .all()
    )

    integration_results = []

    for item in integrations:

        configured, error = (
            validate_config(
                validate_integration_config,
                item.integration_type,
                reveal_config(item.config),
            )
        )

        integration_results.append({
            "id": item.id,
            "type":
                item.integration_type,
            "name":
                item.name,
            "enabled":
                item.enabled,
            "configured":
                configured,
            "config":
                public_config(
                    item.config
                ),
            "configured_secret_fields":
                configured_secret_fields(
                    item.config
                ),
            "issue":
                error,
        })

    agent_results = []

    for agent in agents:

        config = (
            db.query(AgentConfig)
            .filter(
                AgentConfig.agent_id
                == agent.id
            )
            .first()
        )

        knowledge_count = (
            db.query(AgentKnowledge)
            .join(
                KnowledgeDocument,
                KnowledgeDocument.id
                == AgentKnowledge.document_id,
            )
            .filter(
                AgentKnowledge.agent_id
                == agent.id,
                AgentKnowledge.enabled
                .is_(True),
                KnowledgeDocument.enabled
                .is_(True),
            )
            .count()
        )

        tools = (
            db.query(
                AgentToolAssignment
            )
            .filter(
                AgentToolAssignment.agent_id
                == agent.id,
                AgentToolAssignment.enabled
                .is_(True),
            )
            .all()
        )

        channels = (
            db.query(AgentChannel)
            .filter(
                AgentChannel.agent_id
                == agent.id,
                AgentChannel.enabled
                .is_(True),
            )
            .all()
        )

        provider_ready = (
            bool(agent.provider)
            and agent.provider != "mock"
            and agent.provider
            in ai_engine.list_providers()
        )

        model_ready = bool(
            (agent.model or "").strip()
        )

        prompt_ready = bool(
            (agent.system_prompt or "")
            .strip()
        )

        config_ready = (
            config is not None
        )

        channel_results = []

        for channel in channels:

            configured, error = (
                validate_config(
                    validate_channel_config,
                    channel.channel_type,
                    reveal_config(channel.config),
                )
            )

            channel_results.append({
                "id":
                    channel.id,
                "type":
                    channel.channel_type,
                "enabled":
                    channel.enabled,
                "configured":
                    configured,
                "config":
                    public_config(
                        channel.config
                    ),
                "configured_secret_fields":
                    configured_secret_fields(
                        channel.config
                    ),
                "issue":
                    error,
            })

        ready_channels = [
            item
            for item in channel_results
            if item["configured"]
        ]

        issues = []
        warnings = []

        if not provider_ready:
            issues.append(
                "Real AI provider is not configured"
            )

        if not model_ready:
            issues.append(
                "AI model is not configured"
            )

        if not prompt_ready:
            issues.append(
                "System prompt is empty"
            )

        if not config_ready:
            issues.append(
                "Agent configuration is missing"
            )

        if knowledge_count == 0:
            issues.append(
                "No enabled knowledge connected"
            )

        if not channels:
            issues.append(
                "No enabled channel assigned"
            )

        elif not ready_channels:
            issues.append(
                "Channel configuration is incomplete"
            )

        if not agent.enabled:
            warnings.append(
                "Agent is currently disabled and will be enabled on activation"
            )

        agent_ready = (
            provider_ready
            and model_ready
            and prompt_ready
            and config_ready
            and knowledge_count > 0
            and bool(ready_channels)
        )

        agent_results.append({
            "id":
                agent.id,
            "name":
                agent.name,
            "enabled":
                agent.enabled,
            "provider":
                agent.provider,
            "model":
                agent.model,
            "provider_ready":
                provider_ready,
            "model_ready":
                model_ready,
            "prompt_ready":
                prompt_ready,
            "config_exists":
                config_ready,
            "knowledge_count":
                knowledge_count,
            "tool_count":
                len(tools),
            "channels":
                channel_results,
            "ready":
                agent_ready,
            "issues":
                issues,
            "warnings":
                warnings,
        })

    ready_agents = [
        item
        for item in agent_results
        if item["ready"]
    ]

    company_issues = []
    company_warnings = []

    if subscription is None:
        company_issues.append(
            "No active subscription"
        )

    elif subscription_plan is None:
        company_issues.append(
            "Subscription plan is disabled or missing"
        )

    if not modules:
        company_issues.append(
            "No active modules"
        )

    if not agents:
        company_issues.append(
            "No AI agents"
        )

    elif not ready_agents:
        company_issues.append(
            "No production-ready agent"
        )

    if not company.active:
        company_warnings.append(
            "Company is currently inactive"
        )

    setup_ready = (
        subscription is not None
        and subscription_plan is not None
        and bool(modules)
        and bool(ready_agents)
    )

    if (
        setup_ready
        and company.active
    ):
        status = "ACTIVE"

    elif setup_ready:
        status = "READY_TO_ACTIVATE"

    else:
        status = "SETUP_REQUIRED"

    return {
        "company": {
            "id":
                company.id,
            "name":
                company.name,
            "active":
                company.active,
        },

        # Kept for activation API compatibility.
        "ready":
            setup_ready,

        "setup_ready":
            setup_ready,

        "status":
            status,

        "subscription_ready":
            (
                subscription is not None
                and subscription_plan
                is not None
            ),

        "subscription": (
            None
            if subscription is None
            else {
                "id":
                    subscription.id,
                "plan_id":
                    subscription.plan_id,
                "plan_name": (
                    subscription_plan.name
                    if subscription_plan
                    else None
                ),
                "status":
                    subscription.status,
                "started_at":
                    subscription.started_at,
            }
        ),

        "modules": [
            item.module_name
            for item in modules
        ],

        "agents":
            agent_results,

        "integrations":
            integration_results,

        "issues":
            company_issues,

        "warnings":
            company_warnings,
    }
