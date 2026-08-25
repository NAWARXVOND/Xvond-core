from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func

from backend.app.modules.billing.service_models import (
    ServicePlan,
    ServiceSubscription,
    ServiceUsageEvent,
)


class ServiceLimits:
    def subscription(self, db, company_id: int, service_code: str):
        return (
            db.query(ServiceSubscription)
            .filter(
                ServiceSubscription.company_id == company_id,
                ServiceSubscription.service_code == service_code,
                ServiceSubscription.status == "active",
            )
            .first()
        )

    def entitlement(self, db, company_id: int, service_code: str):
        subscription = self.subscription(db, company_id, service_code)
        if subscription is None:
            raise HTTPException(
                status_code=403,
                detail=f"Active {service_code} service subscription required",
            )

        plan = db.query(ServicePlan).filter(
            ServicePlan.id == subscription.plan_id,
            ServicePlan.enabled.is_(True),
        ).first()
        if plan is None:
            raise HTTPException(status_code=403, detail="Service plan is unavailable")
        return subscription, plan

    def used(self, db, subscription: ServiceSubscription, metric: str) -> Decimal:
        value = (
            db.query(func.coalesce(func.sum(ServiceUsageEvent.quantity), 0))
            .filter(
                ServiceUsageEvent.company_id == subscription.company_id,
                ServiceUsageEvent.service_code == subscription.service_code,
                ServiceUsageEvent.metric == metric,
                ServiceUsageEvent.created_at >= subscription.current_period_start,
                ServiceUsageEvent.created_at < subscription.current_period_end,
            )
            .scalar()
        )
        return Decimal(str(value or 0))

    def check(self, db, company_id: int, service_code: str, metric: str, quantity=1):
        subscription, plan = self.entitlement(db, company_id, service_code)
        raw_limit = (plan.limits or {}).get(metric)
        if raw_limit in (None, 0, "0"):
            return subscription, plan

        limit = Decimal(str(raw_limit))
        requested = Decimal(str(quantity))
        if self.used(db, subscription, metric) + requested > limit:
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Monthly service limit reached",
                    "service": service_code,
                    "metric": metric,
                    "limit": str(limit),
                },
            )
        return subscription, plan

    def record(self, db, company_id: int, service_code: str, metric: str, quantity=1, metadata=None):
        self.check(db, company_id, service_code, metric, quantity)
        event = ServiceUsageEvent(
            company_id=company_id,
            service_code=service_code,
            metric=metric,
            quantity=Decimal(str(quantity)),
            metadata_json=metadata or {},
        )
        db.add(event)
        return event


service_limits = ServiceLimits()
