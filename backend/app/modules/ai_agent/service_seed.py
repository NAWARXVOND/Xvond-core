from backend.app.modules.ai_agent.builtin_services import BUILTIN_AGENT_SERVICES
from backend.app.modules.ai_agent.factory_models import AgentTemplate


def seed_builtin_agent_services(db):

    created = 0
    updated = 0

    for service in BUILTIN_AGENT_SERVICES:

        template = (
            db.query(AgentTemplate)
            .filter(
                AgentTemplate.category
                == service["category"]
            )
            .first()
        )

        if template is None:

            template = AgentTemplate(
                name=service["name"],
                category=service["category"],
                description=service["description"],
                default_system_prompt=service["system_prompt"],
                default_provider="mock",
                default_model="test-model",
                default_config=service["config"],
                enabled=True,
            )

            db.add(template)
            created += 1

        else:

            template.name = service["name"]
            template.description = service["description"]
            template.default_system_prompt = service["system_prompt"]
            template.default_config = service["config"]
            template.enabled = True

            updated += 1

    db.commit()

    return {
        "created": created,
        "updated": updated,
        "total": len(BUILTIN_AGENT_SERVICES),
    }
