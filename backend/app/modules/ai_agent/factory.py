
from backend.app.core.ai.provider_policy import (
    require_provider_model,
)

from backend.app.modules.ai_agent.factory_models import (
    AgentConfig,
    AgentTemplate,
)

from backend.app.modules.ai_agent.models import (
    AIAgent,
)

from backend.app.modules.billing.limits import (
    limits_service,
)

from backend.app.modules.channels.models import (
    AgentChannel,
)

from backend.app.modules.tools.models import (
    AgentToolAssignment,
)


class AgentFactory:

    def validate_agent_identity(
        self,
        db,
        name: str,
        system_prompt: str,
        provider: str,
        model: str,
    ):

        if not (name or "").strip():
            raise ValueError(
                "Agent name is required"
            )

        if not (
            system_prompt or ""
        ).strip():
            raise ValueError(
                "System prompt is required"
            )

        if not (
            provider or ""
        ).strip():
            raise ValueError(
                "AI provider is required"
            )

        if not (
            model or ""
        ).strip():
            raise ValueError(
                "AI model is required"
            )

        require_provider_model(
            db,
            provider,
            model,
        )

    def create_custom_agent(
        self,
        db,
        company_id: int,
        name: str,
        description: str | None,
        system_prompt: str,
        provider: str,
        model: str,
        agent_type: str,
        settings: dict,
        capabilities: dict,
        customer_controls: dict,
    ) -> AIAgent:

        limits_service.check_agent_limit(
            db,
            company_id,
        )

        self.validate_agent_identity(
            db,
            name,
            system_prompt,
            provider,
            model,
        )

        agent = AIAgent(
            company_id=
                company_id,
            name=
                name.strip(),
            description=
                description,
            system_prompt=
                system_prompt.strip(),
            provider=
                provider.strip(),
            model=
                model.strip(),
            enabled=True,
        )

        db.add(agent)
        db.flush()

        config = AgentConfig(
            agent_id=
                agent.id,
            agent_type=
                (
                    agent_type
                    or "custom"
                ).strip(),
            settings=
                settings or {},
            capabilities=
                capabilities or {},
            customer_controls=
                customer_controls or {},
        )

        db.add(config)

        return agent

    def create_from_template(
        self,
        db,
        company_id: int,
        template: AgentTemplate,
        name: str | None = None,
        system_prompt: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        settings: dict | None = None,
    ) -> AIAgent:

        limits_service.check_agent_limit(
            db,
            company_id,
        )

        selected_name = (
            name
            or template.name
        )

        selected_prompt = (
            system_prompt
            or template.default_system_prompt
        )

        selected_provider = (
            provider
            or template.default_provider
        )

        selected_model = (
            model
            or template.default_model
        )

        self.validate_agent_identity(
            db,
            selected_name,
            selected_prompt,
            selected_provider,
            selected_model,
        )

        final_settings = dict(
            template.default_config
            or {}
        )

        if settings:
            final_settings.update(
                settings
            )

        agent = AIAgent(
            company_id=
                company_id,
            name=
                selected_name.strip(),
            description=
                template.description,
            system_prompt=
                selected_prompt.strip(),
            provider=
                selected_provider.strip(),
            model=
                selected_model.strip(),
            enabled=True,
        )

        db.add(agent)
        db.flush()

        config = AgentConfig(
            agent_id=
                agent.id,
            agent_type=
                template.category,
            settings=
                final_settings,
            capabilities={},
            customer_controls={
                "can_enable_disable":
                    True,
                "can_view_conversations":
                    True,
                "can_view_usage":
                    True,
                "can_edit_prompt":
                    False,
                "can_change_provider":
                    False,
                "can_change_model":
                    False,
            },
        )

        db.add(config)

        template_tools = {
            "customer_service": [
                "human_handoff",
            ],

            "sales": [
                "lead",
                "order",
                "human_handoff",
            ],

            "booking": [
                "booking",
                "lead",
                "human_handoff",
            ],

            "website": [
                "lead",
                "booking",
                "order",
                "human_handoff",
            ],

            "whatsapp": [
                "lead",
                "booking",
                "order",
                "human_handoff",
            ],

            "voice": [
                "lead",
                "booking",
                "human_handoff",
            ],

            "knowledge_assistant": [
                "human_handoff",
            ],

            "custom": [],
        }

        assigned_tools = (
            template_tools.get(
                template.category,
                [],
            )
        )

        for tool_name in assigned_tools:

            db.add(
                AgentToolAssignment(
                    agent_id=
                        agent.id,
                    tool_name=
                        tool_name,
                    config={},
                    enabled=True,
                )
            )

        template_channels = {
            "website":
                "website",
            "whatsapp":
                "whatsapp",
            "voice":
                "voice",
        }

        channel_type = (
            template_channels.get(
                template.category
            )
        )

        if channel_type:

            # Channel exists as part of setup,
            # but remains DISABLED until its
            # required configuration is entered.
            # This prevents empty channels from
            # being treated as production channels.
            db.add(
                AgentChannel(
                    company_id=
                        company_id,
                    agent_id=
                        agent.id,
                    channel_type=
                        channel_type,
                    config={},
                    enabled=False,
                )
            )

        return agent


agent_factory = AgentFactory()
