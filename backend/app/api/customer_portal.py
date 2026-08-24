
from fastapi import (
    APIRouter,
    Depends,
)

from sqlalchemy import func

from backend.app.core.config_secrets import (
    configured_secret_fields,
    public_config,
)
from backend.app.core.database.connection import (
    SessionLocal,
)
from backend.app.core.dependencies import (
    require_customer_user,
)

from backend.app.models.company import Company
from backend.app.models.user import User

from backend.app.modules.ai_agent.models import (
    AIAgent,
    AIConversation,
    AIUsage,
)
from backend.app.modules.billing.models import (
    Plan,
    Subscription,
)
from backend.app.modules.channels.models import (
    AgentChannel,
)
from backend.app.modules.integrations.models import (
    CompanyIntegration,
)
from backend.app.modules.knowledge.models import (
    KnowledgeDocument,
)


router = APIRouter(
    prefix="/customer",
    tags=["Customer Portal"],
)


@router.get("/overview")
def overview(
    current_user: User = Depends(
        require_customer_user
    ),
):

    db = SessionLocal()

    try:

        company_id = (
            current_user.company_id
        )

        company = (
            db.query(Company)
            .filter(
                Company.id
                == company_id
            )
            .first()
        )

        subscription = (
            db.query(Subscription)
            .filter(
                Subscription.company_id
                == company_id
            )
            .first()
        )

        plan = None

        if subscription:
            plan = (
                db.query(Plan)
                .filter(
                    Plan.id
                    == subscription.plan_id
                )
                .first()
            )

        agents = (
            db.query(AIAgent)
            .filter(
                AIAgent.company_id
                == company_id
            )
            .all()
        )

        channels = (
            db.query(AgentChannel)
            .filter(
                AgentChannel.company_id
                == company_id
            )
            .all()
        )

        integrations = (
            db.query(CompanyIntegration)
            .filter(
                CompanyIntegration.company_id
                == company_id
            )
            .all()
        )

        usage = (
            db.query(
                func.count(AIUsage.id),
                func.coalesce(
                    func.sum(
                        AIUsage.total_tokens
                    ),
                    0,
                ),
            )
            .filter(
                AIUsage.company_id
                == company_id
            )
            .first()
        )

        return {
            "company": {
                "id":
                    company.id,
                "name":
                    company.name,
                "active":
                    company.active,
            },

            "subscription": (
                None
                if subscription is None
                else {
                    "id":
                        subscription.id,
                    "status":
                        subscription.status,
                    "started_at":
                        subscription.started_at,
                    "plan": (
                        None
                        if plan is None
                        else {
                            "id":
                                plan.id,
                            "name":
                                plan.name,
                            "agent_limit":
                                plan.agent_limit,
                            "token_limit":
                                plan.token_limit,
                            "channel_limit":
                                plan.channel_limit,
                        }
                    ),
                }
            ),

            "summary": {
                "agents":
                    len(agents),
                "active_agents":
                    sum(
                        1
                        for item in agents
                        if item.enabled
                    ),
                "conversations":
                    db.query(
                        AIConversation
                    ).filter(
                        AIConversation.company_id
                        == company_id
                    ).count(),
                "requests":
                    int(
                        usage[0] or 0
                    ),
                "tokens":
                    int(
                        usage[1] or 0
                    ),
                "knowledge_documents":
                    db.query(
                        KnowledgeDocument
                    ).filter(
                        KnowledgeDocument.company_id
                        == company_id,
                        KnowledgeDocument.enabled
                        .is_(True),
                    ).count(),
                "channels":
                    len(channels),
                "integrations":
                    len(integrations),
            },

            "channels": [
                {
                    "id":
                        item.id,
                    "agent_id":
                        item.agent_id,
                    "type":
                        item.channel_type,
                    "enabled":
                        item.enabled,
                    "config":
                        public_config(
                            item.config
                        ),
                    "configured_secret_fields":
                        configured_secret_fields(
                            item.config
                        ),
                }
                for item in channels
            ],

            "integrations": [
                {
                    "id":
                        item.id,
                    "type":
                        item.integration_type,
                    "name":
                        item.name,
                    "enabled":
                        item.enabled,
                    "config":
                        public_config(
                            item.config
                        ),
                    "configured_secret_fields":
                        configured_secret_fields(
                            item.config
                        ),
                }
                for item in integrations
            ],
        }

    finally:
        db.close()
