
from fastapi import (
    APIRouter,
    Depends,
)
from sqlalchemy import func

from backend.app.core.database.connection import (
    SessionLocal,
)
from backend.app.core.dependencies import (
    require_customer_manager,
)
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import (
    AIUsage,
)
from backend.app.modules.billing.models import (
    Plan,
    Subscription,
)
from backend.app.modules.billing.cycle import (
    current_billing_cycle,
)


router = APIRouter(
    prefix="/usage",
    tags=["Usage"],
)


@router.get("/")
def my_usage(
    current_user: User = Depends(
        require_customer_manager
    ),
):

    db = SessionLocal()

    try:

        subscription = (
            db.query(Subscription)
            .filter(
                Subscription.company_id
                == current_user.company_id,
                Subscription.status
                == "active",
            )
            .first()
        )

        query = (
            db.query(
                func.count(AIUsage.id),
                func.coalesce(
                    func.sum(
                        AIUsage.input_tokens
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        AIUsage.output_tokens
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        AIUsage.total_tokens
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        AIUsage.provider_cost
                    ),
                    0,
                ),
            )
            .filter(
                AIUsage.company_id
                == current_user.company_id
            )
        )

        cycle_start = None
        cycle_end = None

        if subscription is not None:

            (
                cycle_start,
                cycle_end,
            ) = current_billing_cycle(
                subscription.started_at
            )

            query = query.filter(
                AIUsage.created_at
                >= cycle_start,

                AIUsage.created_at
                < cycle_end,
            )

        summary = query.first()

        plan = None

        if subscription is not None:
            plan = (
                db.query(Plan)
                .filter(
                    Plan.id
                    == subscription.plan_id
                )
                .first()
            )

        used_tokens = int(
            summary[3] or 0
        )

        token_limit = (
            int(plan.token_limit)
            if plan
            else 0
        )

        return {
            "company_id":
                current_user.company_id,

            "cycle_started_at":
                cycle_start,

            "cycle_ends_at":
                cycle_end,

            "requests":
                int(summary[0] or 0),

            "input_tokens":
                int(summary[1] or 0),

            "output_tokens":
                int(summary[2] or 0),

            "total_tokens":
                used_tokens,

            "provider_cost":
                summary[4],

            "token_limit":
                token_limit,

            "remaining_tokens": (
                max(
                    token_limit
                    - used_tokens,
                    0,
                )
                if token_limit > 0
                else None
            ),
        }

    finally:
        db.close()
