from fastapi import APIRouter, Depends, HTTPException

from backend.app.api.admin_agent_actions import _enabled_business_modules, _readiness
from backend.app.core.config.settings import settings
from backend.app.core.config_secrets import reveal_config
from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.company import Company
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.ai_agent.profile_models import AIAgentProfile
from backend.app.modules.billing.limits import limits_service
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.integrations.models import CompanyIntegration
from backend.app.modules.knowledge.models import AgentKnowledge, KnowledgeDocument
from backend.app.modules.tools.models import AgentToolAssignment


router = APIRouter(
    prefix="/admin/delivery-readiness",
    tags=["Xvond Admin - Delivery Readiness"],
)


def _action_state(db, company_id: int, agent_id: int) -> dict:
    assignment = (
        db.query(AgentToolAssignment)
        .filter(
            AgentToolAssignment.agent_id == agent_id,
            AgentToolAssignment.tool_name == "action_request",
            AgentToolAssignment.enabled.is_(True),
        )
        .first()
    )
    if assignment is None:
        return {
            "requested": False,
            "ready": True,
            "enabled_count": 0,
            "issues": [],
            "requires_workflow_engine": False,
            "required_integration_ids": [],
        }

    config = reveal_config(assignment.config) or {}
    stored = config.get("actions") or {}
    enabled_modules = _enabled_business_modules(db, company_id)
    enabled_actions = []
    issues = []
    required_integration_ids = set()

    for key, value in stored.items():
        if not isinstance(value, dict) or not value.get("enabled", False):
            continue
        action = {"key": key, **value}
        enabled_actions.append(action)
        for issue in _readiness(action, enabled_modules):
            issues.append(f"{action.get('label') or key}: {issue}")
        destination = action.get("destination") or {}
        if destination.get("type") == "integration" and destination.get("integration_id"):
            required_integration_ids.add(int(destination["integration_id"]))

    return {
        "requested": bool(enabled_actions),
        "ready": not issues,
        "enabled_count": len(enabled_actions),
        "issues": issues,
        "requires_workflow_engine": bool(enabled_actions),
        "required_integration_ids": sorted(required_integration_ids),
    }


def _channel_state(db, company_id: int, agent_id: int) -> dict:
    rows = (
        db.query(AgentChannel)
        .filter(
            AgentChannel.company_id == company_id,
            AgentChannel.agent_id == agent_id,
        )
        .all()
    )
    configured = [row for row in rows if bool(reveal_config(row.config) or {})]
    live = [row for row in configured if row.enabled]
    return {
        "configured_count": len(configured),
        "live_count": len(live),
        "configured": bool(configured),
        "live": bool(live),
    }


def _delivery_state(db, company_id: int, agent_id: int) -> dict:
    agent = (
        db.query(AIAgent)
        .filter(AIAgent.id == agent_id, AIAgent.company_id == company_id)
        .first()
    )
    if agent is None:
        raise HTTPException(404, "AI employee not found")

    company = db.query(Company).filter(Company.id == company_id).first()
    if company is None:
        raise HTTPException(404, "Company not found")

    profile = (
        db.query(AIAgentProfile)
        .filter(
            AIAgentProfile.agent_id == agent_id,
            AIAgentProfile.company_id == company_id,
        )
        .first()
    )
    profile_ready = profile is not None and bool(str(agent.name or "").strip())

    knowledge_count = (
        db.query(AgentKnowledge)
        .join(KnowledgeDocument, KnowledgeDocument.id == AgentKnowledge.document_id)
        .filter(
            AgentKnowledge.agent_id == agent_id,
            AgentKnowledge.enabled.is_(True),
            KnowledgeDocument.company_id == company_id,
            KnowledgeDocument.enabled.is_(True),
        )
        .count()
    )
    knowledge_ready = knowledge_count > 0

    channels = _channel_state(db, company_id, agent_id)
    actions = _action_state(db, company_id, agent_id)

    integration_issues = []
    for integration_id in actions["required_integration_ids"]:
        integration = (
            db.query(CompanyIntegration)
            .filter(
                CompanyIntegration.id == integration_id,
                CompanyIntegration.company_id == company_id,
                CompanyIntegration.enabled.is_(True),
            )
            .first()
        )
        if integration is None or not (reveal_config(integration.config) or {}):
            integration_issues.append(
                f"Connected App #{integration_id} is missing or not configured"
            )

    workflow_required = actions["requires_workflow_engine"]
    workflow_ready = (
        not workflow_required
        or (
            bool(settings.N8N_ENABLED)
            and bool(str(settings.N8N_WEBHOOK_URL or "").strip())
            and bool(str(settings.N8N_SHARED_SECRET or "").strip())
        )
    )

    setup_blockers = []
    if not profile_ready:
        setup_blockers.append("Complete employee identity and behavior")
    if not knowledge_ready:
        setup_blockers.append("Attach at least one enabled knowledge source")
    if not channels["configured"]:
        setup_blockers.append("Connect and configure at least one customer channel")
    setup_blockers.extend(actions["issues"])
    setup_blockers.extend(integration_issues)
    if workflow_required and not workflow_ready:
        setup_blockers.append("Workflow Engine is not ready for enabled business actions")

    setup_ready = not setup_blockers
    blockers = list(setup_blockers)
    if not company.active:
        blockers.insert(0, "Company must be active before this employee can go live")
    if not agent.enabled:
        blockers.insert(0, "AI employee is in draft mode")
    elif not channels["live"]:
        blockers.append("Activate at least one customer channel")

    ready_for_customer = bool(
        company.active and agent.enabled and setup_ready and channels["live"]
    )

    return {
        "agent": agent,
        "company": company,
        "payload": {
            "company_id": company_id,
            "agent_id": agent_id,
            "company_active": bool(company.active),
            "ready_for_customer": ready_for_customer,
            "setup_ready": setup_ready,
            "lifecycle": "live" if agent.enabled else "draft",
            "mode": "conversational_and_operational" if actions["requested"] else "conversational",
            "blockers": blockers,
            "setup_blockers": setup_blockers,
            "checks": {
                "company_active": bool(company.active),
                "employee_enabled": bool(agent.enabled),
                "profile": profile_ready,
                "knowledge": knowledge_ready,
                "channels": channels["configured"],
                "live_channels": channels["live"],
                "actions": actions["ready"],
                "workflow_engine": workflow_ready,
                "connected_apps": not integration_issues,
            },
            "counts": {
                "knowledge_sources": knowledge_count,
                "channels": channels["configured_count"],
                "live_channels": channels["live_count"],
                "enabled_actions": actions["enabled_count"],
                "required_connected_apps": len(actions["required_integration_ids"]),
            },
        },
    }


@router.get("/companies/{company_id}/agents/{agent_id}")
def get_delivery_readiness(
    company_id: int,
    agent_id: int,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        return _delivery_state(db, company_id, agent_id)["payload"]
    finally:
        db.close()


@router.post("/companies/{company_id}/agents/{agent_id}/go-live")
def go_live(
    company_id: int,
    agent_id: int,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        state = _delivery_state(db, company_id, agent_id)
        agent = state["agent"]
        company = state["company"]
        if agent.enabled:
            return {**state["payload"], "status": "already_live"}
        if not state["payload"]["setup_ready"]:
            raise HTTPException(
                409,
                detail={
                    "message": "AI employee is not ready to go live",
                    "blockers": state["payload"]["setup_blockers"],
                },
            )
        if not company.active:
            raise HTTPException(
                409,
                detail={
                    "message": "Activate the company before the AI employee goes live",
                    "blockers": ["Company is inactive"],
                },
            )
        limits_service.check_agent_limit(db, company_id)
        agent.enabled = True
        db.commit()
        live = _delivery_state(db, company_id, agent_id)["payload"]
        return {**live, "status": "live"}
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/companies/{company_id}/agents/{agent_id}/deactivate")
def deactivate(
    company_id: int,
    agent_id: int,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        state = _delivery_state(db, company_id, agent_id)
        agent = state["agent"]
        agent.enabled = False
        db.commit()
        draft = _delivery_state(db, company_id, agent_id)["payload"]
        return {**draft, "status": "draft"}
    finally:
        db.close()
