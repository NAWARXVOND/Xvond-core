from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, text

from backend.app.modules.ai_agent.models import AIUsage
from backend.app.modules.billing.service_models import ServicePlan, ServiceSubscription, ServiceUsageEvent


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ServiceLimits:
    def _lock(self, db, company_id: int, service_code: str, metric: str) -> None:
        bind = db.get_bind()
        if bind is not None and bind.dialect.name == "postgresql":
            key = f"service-limit:{company_id}:{service_code}:{metric}"
            db.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
                {"lock_key": key},
            )

    def subscription(self, db, company_id: int, service_code: str):
        item = db.query(ServiceSubscription).filter(
            ServiceSubscription.company_id == company_id,
            ServiceSubscription.service_code == service_code,
            ServiceSubscription.status == "active",
        ).first()
        if item is None:
            return None
        now = _utcnow_naive()
        if item.current_period_end <= now:
            item.status = "expired"
            db.flush()
            return None
        if item.current_period_start > now:
            return None
        return item

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
            ServicePlan.service_code == service_code,
        ).first()
        if plan is None:
            raise HTTPException(status_code=403, detail="Service plan is unavailable")
        return subscription, plan

    def limit_value(self, plan: ServicePlan, metric: str):
        raw = (plan.limits or {}).get(metric)
        if raw in (None, 0, "0"):
            return None
        value = Decimal(str(raw))
        if value < 0:
            raise HTTPException(500, "Service plan contains an invalid negative limit")
        return value

    def check_current(self, db, company_id: int, service_code: str, metric: str, current, quantity=1):
        self._lock(db, company_id, service_code, metric)
        subscription, plan = self.entitlement(db, company_id, service_code)
        limit = self.limit_value(plan, metric)
        if limit is None:
            return subscription, plan
        requested = Decimal(str(quantity))
        if requested < 0:
            raise HTTPException(400, "Usage quantity cannot be negative")
        if Decimal(str(current)) + requested > limit:
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Service capacity limit reached",
                    "service": service_code,
                    "metric": metric,
                    "used": str(current),
                    "limit": str(limit),
                },
            )
        return subscription, plan

    def used(self, db, subscription: ServiceSubscription, metric: str) -> Decimal:
        if subscription.service_code == "ai_agents" and metric == "tokens":
            value = db.query(func.coalesce(func.sum(AIUsage.total_tokens), 0)).filter(
                AIUsage.company_id == subscription.company_id,
                AIUsage.status == "success",
                AIUsage.created_at >= subscription.current_period_start,
                AIUsage.created_at < subscription.current_period_end,
            ).scalar()
            return Decimal(str(value or 0))
        value = db.query(func.coalesce(func.sum(ServiceUsageEvent.quantity), 0)).filter(
            ServiceUsageEvent.company_id == subscription.company_id,
            ServiceUsageEvent.service_code == subscription.service_code,
            ServiceUsageEvent.metric == metric,
            ServiceUsageEvent.created_at >= subscription.current_period_start,
            ServiceUsageEvent.created_at < subscription.current_period_end,
        ).scalar()
        return Decimal(str(value or 0))

    def _check_locked(self, db, company_id: int, service_code: str, metric: str, quantity=1):
        subscription, plan = self.entitlement(db, company_id, service_code)
        limit = self.limit_value(plan, metric)
        if limit is None:
            return subscription, plan
        requested = Decimal(str(quantity))
        if requested < 0:
            raise HTTPException(400, "Usage quantity cannot be negative")
        used = self.used(db, subscription, metric)
        if used + requested > limit:
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Monthly service limit reached",
                    "service": service_code,
                    "metric": metric,
                    "used": str(used),
                    "limit": str(limit),
                },
            )
        return subscription, plan

    def check(self, db, company_id: int, service_code: str, metric: str, quantity=1):
        self._lock(db, company_id, service_code, metric)
        return self._check_locked(db, company_id, service_code, metric, quantity)

    def record(self, db, company_id: int, service_code: str, metric: str, quantity=1, metadata=None):
        self._lock(db, company_id, service_code, metric)
        self._check_locked(db, company_id, service_code, metric, quantity)
        event = ServiceUsageEvent(
            company_id=company_id,
            service_code=service_code,
            metric=metric,
            quantity=Decimal(str(quantity)),
            metadata_json=metadata or {},
        )
        db.add(event)
        db.flush()
        return event


service_limits = ServiceLimits()
