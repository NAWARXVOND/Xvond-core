from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from redis.exceptions import RedisError
from sqlalchemy import func

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.company import Company
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIUsage
from backend.app.modules.billing.service_models import ServicePlan, ServiceSubscription
from backend.app.modules.channels.whatsapp_queue import whatsapp_job_queue
from backend.app.modules.solutions.catalog import SERVICE_CATALOG
from backend.app.modules.tools.business_models import ActionRequest

router = APIRouter(prefix="/admin/operations", tags=["Xvond Admin - Operations"])
UNRESOLVED_EXTERNAL = {"executing", "external_failed", "cancelling"}
RECONCILIATION_OUTCOMES = {"executed", "not_executed", "cancelled"}


class ReconcileExternalOperation(BaseModel):
    outcome: str
    note: str | None = None


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def get_company_or_404(db, company_id: int):
    company = db.query(Company).filter(Company.id == company_id).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def _operation_metadata(item: ActionRequest) -> dict:
    """Return operator-safe metadata without tenant customer content."""
    return {
        "id": item.id,
        "company_id": item.company_id,
        "agent_id": item.agent_id,
        "action_type": item.action_type,
        "status": item.status,
        "created_at": item.created_at,
    }


@router.get("/companies/{company_id}/usage")
def company_usage(company_id: int, current_admin: User = Depends(require_xvond_admin)):
    """Operational usage/cost telemetry only; no prompts or conversation content."""
    db = SessionLocal()
    try:
        get_company_or_404(db, company_id)
        summary = db.query(
            func.count(AIUsage.id),
            func.coalesce(func.sum(AIUsage.input_tokens), 0),
            func.coalesce(func.sum(AIUsage.output_tokens), 0),
            func.coalesce(func.sum(AIUsage.total_tokens), 0),
            func.coalesce(func.sum(AIUsage.provider_cost), 0),
        ).filter(AIUsage.company_id == company_id).first()
        items = db.query(AIUsage).filter(
            AIUsage.company_id == company_id
        ).order_by(AIUsage.id.desc()).limit(500).all()
        return {
            "company_id": company_id,
            "summary": {
                "requests": summary[0],
                "input_tokens": summary[1],
                "output_tokens": summary[2],
                "total_tokens": summary[3],
                "provider_cost": summary[4],
            },
            "usage": [
                {
                    "id": item.id,
                    "agent_id": item.agent_id,
                    "provider": item.provider,
                    "model": item.model,
                    "input_tokens": item.input_tokens,
                    "output_tokens": item.output_tokens,
                    "total_tokens": item.total_tokens,
                    "provider_cost": item.provider_cost,
                    "status": item.status,
                    "latency_ms": item.latency_ms,
                    "created_at": item.created_at,
                }
                for item in items
            ],
        }
    finally:
        db.close()


@router.get("/subscriptions")
def subscriptions(current_admin: User = Depends(require_xvond_admin)):
    """Canonical service subscriptions across all companies."""
    db = SessionLocal()
    try:
        rows = (
            db.query(ServiceSubscription, Company, ServicePlan)
            .join(Company, Company.id == ServiceSubscription.company_id)
            .join(ServicePlan, ServicePlan.id == ServiceSubscription.plan_id)
            .order_by(ServiceSubscription.id.desc())
            .all()
        )
        return {
            "subscriptions": [
                {
                    "id": subscription.id,
                    "company_id": company.id,
                    "company_name": company.name,
                    "service_code": subscription.service_code,
                    "service_name": SERVICE_CATALOG.get(subscription.service_code, {}).get(
                        "name", subscription.service_code
                    ),
                    "plan_id": plan.id,
                    "plan_name": plan.name,
                    "tier": plan.tier,
                    "monthly_price": plan.monthly_price,
                    "currency": plan.currency,
                    "status": subscription.status,
                    "current_period_start": subscription.current_period_start,
                    "current_period_end": subscription.current_period_end,
                }
                for subscription, company, plan in rows
            ]
        }
    finally:
        db.close()


@router.get("/companies/{company_id}/external-unresolved")
def unresolved_external_operations(
    company_id: int,
    current_admin: User = Depends(require_xvond_admin),
):
    """Expose only technical operation metadata needed for reconciliation."""
    db = SessionLocal()
    try:
        get_company_or_404(db, company_id)
        items = db.query(ActionRequest).filter(
            ActionRequest.company_id == company_id,
            ActionRequest.status.in_(UNRESOLVED_EXTERNAL),
        ).order_by(ActionRequest.id.desc()).all()
        return {
            "count": len(items),
            "requests": [_operation_metadata(item) for item in items],
        }
    finally:
        db.close()


@router.patch("/requests/{request_id}/reconcile")
def reconcile_external_operation(
    request_id: int,
    data: ReconcileExternalOperation,
    current_admin: User = Depends(require_xvond_admin),
):
    outcome = data.outcome.strip().lower()
    if outcome not in RECONCILIATION_OUTCOMES:
        raise HTTPException(400, "Invalid reconciliation outcome")
    db = SessionLocal()
    try:
        item = db.query(ActionRequest).filter(ActionRequest.id == request_id).first()
        if item is None:
            raise HTTPException(404, "Operation not found")
        if item.status not in UNRESOLVED_EXTERNAL:
            raise HTTPException(409, "Operation does not need external reconciliation")

        details = dict(item.details or {})
        previous = details.get("_xvond_execution")
        previous = dict(previous) if isinstance(previous, dict) else {}
        now = _utcnow_naive().isoformat()
        reconciliation = {
            "outcome": outcome,
            "note": (data.note or "").strip()[:1000] or None,
            "reconciled_at": now,
            "previous_state": previous,
        }
        details["_xvond_reconciliation"] = reconciliation

        if outcome == "executed":
            details["_xvond_execution"] = {
                **previous,
                "state": "confirmed",
                "operation": "execute",
                "updated_at": now,
                "reconciled": True,
            }
            item.status = "confirmed"
        elif outcome == "cancelled":
            details["_xvond_execution"] = {
                **previous,
                "state": "confirmed",
                "operation": "cancel",
                "updated_at": now,
                "reconciled": True,
            }
            item.status = "cancelled"
        else:
            details["_xvond_execution"] = {
                **previous,
                "state": "reconciled_not_executed",
                "updated_at": now,
                "reconciled": True,
            }
            item.status = "new"

        item.details = details
        db.commit()
        db.refresh(item)
        return _operation_metadata(item)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/workers/whatsapp")
def whatsapp_worker_status(current_admin: User = Depends(require_xvond_admin)):
    try:
        return whatsapp_job_queue.stats()
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="WhatsApp worker queue unavailable") from exc


@router.get("/workers/whatsapp/dead")
def whatsapp_dead_jobs(
    limit: int = 50,
    current_admin: User = Depends(require_xvond_admin),
):
    try:
        return {"jobs": whatsapp_job_queue.dead_jobs(limit=limit)}
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="WhatsApp worker queue unavailable") from exc


@router.post("/workers/whatsapp/dead/retry")
def retry_whatsapp_dead_jobs(
    limit: int = 100,
    current_admin: User = Depends(require_xvond_admin),
):
    try:
        requeued = whatsapp_job_queue.requeue_dead(limit=limit)
        return {"status": "requeued", "requeued": requeued}
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="WhatsApp worker queue unavailable") from exc
