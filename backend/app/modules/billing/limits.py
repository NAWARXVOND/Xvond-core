
from fastapi import HTTPException
from sqlalchemy import func

from backend.app.modules.ai_agent.models import (
    AIAgent,
    AIUsage,
)

from backend.app.modules.billing.models import (
    Plan,
    Subscription,
)
from backend.app.modules.billing.cycle import (
    current_billing_cycle,
)

from backend.app.modules.channels.models import (
    AgentChannel,
)


class LimitsService:

    def get_company_subscription(
        self,
        db,
        company_id: int,
    ) -> Subscription | None:

        return (
            db.query(Subscription)
            .filter(
                Subscription.company_id
                == company_id,
                Subscription.status
                == "active",
            )
            .first()
        )

    def get_company_plan(
        self,
        db,
        company_id: int,
    ) -> Plan | None:

        subscription = (
            self.get_company_subscription(
                db,
                company_id,
            )
        )

        if subscription is None:
            return None

        return (
            db.query(Plan)
            .filter(
                Plan.id
                == subscription.plan_id,
                Plan.enabled.is_(True),
            )
            .first()
        )

    def check_agent_limit(
        self,
        db,
        company_id: int,
    ):

        plan = self.get_company_plan(
            db,
            company_id,
        )

        # Development / setup companies
        # can still exist before subscription.
        if plan is None:
            return

        current = (
            db.query(
                func.count(AIAgent.id)
            )
            .filter(
                AIAgent.company_id
                == company_id,
                AIAgent.enabled.is_(True),
            )
            .scalar()
        )

        if (
            plan.agent_limit > 0
            and current
            >= plan.agent_limit
        ):
            raise HTTPException(
                status_code=403,
                detail="Agent limit reached",
            )

    def check_channel_limit(
        self,
        db,
        company_id: int,
    ):

        plan = self.get_company_plan(
            db,
            company_id,
        )

        if plan is None:
            return

        current = (
            db.query(
                func.count(
                    AgentChannel.id
                )
            )
            .filter(
                AgentChannel.company_id
                == company_id,
                AgentChannel.enabled
                .is_(True),
            )
            .scalar()
        )

        if (
            plan.channel_limit > 0
            and current
            >= plan.channel_limit
        ):
            raise HTTPException(
                status_code=403,
                detail="Channel limit reached",
            )

    def check_token_limit(
        self,
        db,
        company_id: int,
    ):

        subscription = (
            self.get_company_subscription(
                db,
                company_id,
            )
        )

        if subscription is None:
            return

        plan = (
            db.query(Plan)
            .filter(
                Plan.id
                == subscription.plan_id,
                Plan.enabled.is_(True),
            )
            .first()
        )

        if plan is None:
            return

        if plan.token_limit <= 0:
            return

        cycle_start, _ = (
            current_billing_cycle(
                subscription.started_at
            )
        )

        used = (
            db.query(
                func.coalesce(
                    func.sum(
                        AIUsage.total_tokens
                    ),
                    0,
                )
            )
            .filter(
                AIUsage.company_id
                == company_id,
                AIUsage.created_at
                >= cycle_start,
            )
            .scalar()
        )

        if used >= plan.token_limit:
            raise HTTPException(
                status_code=403,
                detail=(
                    "AI token limit reached"
                ),
            )


limits_service = LimitsService()
