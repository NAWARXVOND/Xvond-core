from datetime import datetime
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends
from sqlalchemy import func

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_customer_manager
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIUsage
from backend.app.modules.billing.service_models import ServicePlan, ServiceSubscription


router = APIRouter(
    prefix="/usage",
    tags=["Usage"],
)


def _token_limit(plan: ServicePlan | None) -> int:
    if plan is None:
        return 0
    raw = (plan.limits or {}).get("tokens")
    if raw in (None, 0, "0"):
        return 0
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return 0
    if value <= 0:
        return 0
    return int(value)


@router.get("/")
def my_usage(
    current_user: User = Depends(
        require_customer_manager
    ),
):
    db = SessionLocal()
    try:
        company_id = current_user.company_id
        now = datetime.utcnow()

        service_row = (
            db.query(ServiceSubscription, ServicePlan)
            .join(
                ServicePlan,
                ServicePlan.id == ServiceSubscription.plan_id,
            )
            .filter(
                ServiceSubscription.company_id == company_id,
                ServiceSubscription.service_code == "ai_agents",
                ServiceSubscription.status == "active",
                ServiceSubscription.current_period_start <= now,
                ServiceSubscription.current_period_end > now,
                ServicePlan.enabled.is_(True),
                ServicePlan.service_code == "ai_agents",
            )
            .order_by(ServiceSubscription.id.desc())
            .first()
        )

        subscription = service_row[0] if service_row else None
        plan = service_row[1] if service_row else None
        cycle_start = subscription.current_period_start if subscription else None
        cycle_end = subscription.current_period_end if subscription else None

        request_query = db.query(func.count(AIUsage.id)).filter(
            AIUsage.company_id == company_id
        )
        failed_query = db.query(func.count(AIUsage.id)).filter(
            AIUsage.company_id == company_id,
            AIUsage.status != "success",
        )
        successful_usage_query = db.query(
            func.coalesce(func.sum(AIUsage.input_tokens), 0),
            func.coalesce(func.sum(AIUsage.output_tokens), 0),
            func.coalesce(func.sum(AIUsage.total_tokens), 0),
            func.coalesce(func.sum(AIUsage.provider_cost), 0),
        ).filter(
            AIUsage.company_id == company_id,
            AIUsage.status == "success",
        )

        if cycle_start is not None and cycle_end is not None:
            request_query = request_query.filter(
                AIUsage.created_at >= cycle_start,
                AIUsage.created_at < cycle_end,
            )
            failed_query = failed_query.filter(
                AIUsage.created_at >= cycle_start,
                AIUsage.created_at < cycle_end,
            )
            successful_usage_query = successful_usage_query.filter(
                AIUsage.created_at >= cycle_start,
                AIUsage.created_at < cycle_end,
            )

        requests = int(request_query.scalar() or 0)
        failed_requests = int(failed_query.scalar() or 0)
        summary = successful_usage_query.first()
        used_tokens = int(summary[2] or 0)
        token_limit = _token_limit(plan)

        return {
            "company_id": company_id,
            "service_code": "ai_agents" if subscription else None,
            "plan": plan.name if plan else None,
            "plan_tier": plan.tier if plan else None,
            "cycle_started_at": cycle_start,
            "cycle_ends_at": cycle_end,
            "requests": requests,
            "successful_requests": max(requests - failed_requests, 0),
            "failed_requests": failed_requests,
            "input_tokens": int(summary[0] or 0),
            "output_tokens": int(summary[1] or 0),
            "total_tokens": used_tokens,
            "provider_cost": summary[3],
            "token_limit": token_limit,
            "remaining_tokens": (
                max(token_limit - used_tokens, 0)
                if token_limit > 0
                else None
            ),
        }
    finally:
        db.close()
