from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.ai.provider_policy import runtime_selections
from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.core.config_secrets import configured_secret_fields, merge_config, public_config, reveal_config
from backend.app.models.company import Company
from backend.app.models.company_module import CompanyModule
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.billing.limits import limits_service
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.channels.catalog import get_channel_definition, validate_channel_config
from backend.app.modules.knowledge.models import AgentKnowledge, KnowledgeDocument

router = APIRouter(prefix="/admin/channels", tags=["Xvond Admin - Channels"])

class ChannelCreate(BaseModel):
    channel_type: str
    config: dict = Field(default_factory=dict)

class ChannelUpdate(BaseModel):
    config: dict | None = None
    enabled: bool | None = None

class WhatsAppConfigUpdate(BaseModel):
    phone_number_id: str
    access_token: str
    verify_token: str
    app_secret: str
    graph_api_version: str = "v23.0"

def _channel_configured(channel: AgentChannel) -> bool:
    try:
        validate_channel_config(channel.channel_type, reveal_config(channel.config))
        return True
    except ValueError:
        return False

def serialize_channel(channel: AgentChannel) -> dict:
    return {"id":channel.id,"company_id":channel.company_id,"agent_id":channel.agent_id,"channel_type":channel.channel_type,"config":public_config(channel.config),"configured_secret_fields":configured_secret_fields(channel.config),"configured":_channel_configured(channel),"enabled":channel.enabled,"created_at":channel.created_at}

def _ensure_channels_module(db, company_id: int):
    module=db.query(CompanyModule).filter(CompanyModule.company_id==company_id,CompanyModule.module_name=="channels").first()
    if module is None:
        module=CompanyModule(company_id=company_id,module_name="channels",enabled=True);db.add(module)
    else: module.enabled=True
    return module

def _has_real_runtime_provider(db, company_id:int, agent:AIAgent|None)->bool:
    if agent is None:return False
    try:
        selections=runtime_selections(db,company_id,agent.provider,agent.model)
    except Exception:
        return False
    return any(item.provider!="mock" for item in selections)

def _activation_blockers(db, channel: AgentChannel) -> list[str]:
    blockers=[]
    company=db.query(Company).filter(Company.id==channel.company_id).first()
    agent=db.query(AIAgent).filter(AIAgent.id==channel.agent_id,AIAgent.company_id==channel.company_id).first()
    if company is None or not company.active: blockers.append("Company must be active")
    if agent is None or not agent.enabled: blockers.append("AI employee must be active")
    elif not _has_real_runtime_provider(db,channel.company_id,agent): blockers.append("At least one real AI provider/model must be enabled and configured")
    if not _channel_configured(channel): blockers.append(f"{channel.channel_type.title()} channel configuration is incomplete")
    useful=(db.query(KnowledgeDocument).join(AgentKnowledge,AgentKnowledge.document_id==KnowledgeDocument.id).filter(KnowledgeDocument.company_id==channel.company_id,KnowledgeDocument.enabled.is_(True),AgentKnowledge.agent_id==channel.agent_id,AgentKnowledge.enabled.is_(True),KnowledgeDocument.source_type.notin_(["business_profile","website_reference"])).all())
    if not any(len((doc.content or "").strip())>=20 for doc in useful): blockers.append("Add real business knowledge before activating this channel")
    return blockers

@router.post("/agents/{agent_id}")
def create_channel(agent_id:int,data:ChannelCreate,current_admin:User=Depends(require_xvond_admin)):
    db=SessionLocal()
    try:
        agent=db.query(AIAgent).filter(AIAgent.id==agent_id).first()
        if agent is None: raise HTTPException(404,"AI Agent not found")
        channel_type=data.channel_type.strip().lower()
        if not channel_type: raise HTTPException(400,"Channel type is required")
        if get_channel_definition(channel_type) is None: raise HTTPException(400,"Unsupported channel type")
        if db.query(AgentChannel).filter(AgentChannel.agent_id==agent.id,AgentChannel.channel_type==channel_type).first() is not None: raise HTTPException(409,"This channel type is already assigned to the agent")
        limits_service.check_channel_limit(db,agent.company_id)
        channel=AgentChannel(company_id=agent.company_id,agent_id=agent.id,channel_type=channel_type,config=data.config,enabled=False);db.add(channel);_ensure_channels_module(db,agent.company_id);db.commit();db.refresh(channel)
        result=serialize_channel(channel);result["status"]="created";return result
    finally: db.close()

@router.get("/companies/{company_id}")
def list_company_channels(company_id:int,current_admin:User=Depends(require_xvond_admin)):
    db=SessionLocal()
    try:
        items=db.query(AgentChannel).filter(AgentChannel.company_id==company_id).order_by(AgentChannel.id.asc()).all();return {"company_id":company_id,"channels":[serialize_channel(item) for item in items]}
    finally: db.close()

@router.get("/{channel_id}/readiness")
def channel_readiness(channel_id:int,current_admin:User=Depends(require_xvond_admin)):
    db=SessionLocal()
    try:
        channel=db.query(AgentChannel).filter(AgentChannel.id==channel_id).first()
        if channel is None: raise HTTPException(404,"Channel not found")
        blockers=_activation_blockers(db,channel);return {"channel_id":channel.id,"ready":not blockers,"blockers":blockers}
    finally: db.close()

@router.put("/{channel_id}")
def update_channel(channel_id:int,data:ChannelUpdate,current_admin:User=Depends(require_xvond_admin)):
    db=SessionLocal()
    try:
        channel=db.query(AgentChannel).filter(AgentChannel.id==channel_id).first()
        if channel is None: raise HTTPException(404,"Channel not found")
        if data.config is not None: channel.config=merge_config(channel.config,data.config);db.flush()
        if data.enabled is True and channel.enabled is False:
            limits_service.check_channel_limit(db,channel.company_id);blockers=_activation_blockers(db,channel)
            if blockers: raise HTTPException(409,"Channel is not ready: "+"; ".join(blockers))
            _ensure_channels_module(db,channel.company_id);channel.enabled=True
        elif data.enabled is False: channel.enabled=False
        db.commit();db.refresh(channel);result=serialize_channel(channel);result["status"]="updated";return result
    except HTTPException: db.rollback();raise
    except Exception: db.rollback();raise
    finally: db.close()

@router.put("/{channel_id}/whatsapp-config")
def configure_whatsapp(channel_id:int,data:WhatsAppConfigUpdate,current_admin:User=Depends(require_xvond_admin)):
    db=SessionLocal()
    try:
        channel=db.query(AgentChannel).filter(AgentChannel.id==channel_id,AgentChannel.channel_type=="whatsapp").first()
        if channel is None: raise HTTPException(404,"WhatsApp channel not found")
        new_config=merge_config(channel.config,{"phone_number_id":data.phone_number_id,"access_token":data.access_token,"verify_token":data.verify_token,"app_secret":data.app_secret,"graph_api_version":data.graph_api_version})
        try: validate_channel_config("whatsapp",reveal_config(new_config))
        except ValueError as exc: raise HTTPException(400,detail=str(exc)) from exc
        channel.config=new_config;channel.enabled=False;_ensure_channels_module(db,channel.company_id);db.commit();db.refresh(channel);blockers=_activation_blockers(db,channel);result=serialize_channel(channel);result.update({"status":"configured","ready":not blockers,"blockers":blockers});return result
    except HTTPException: db.rollback();raise
    except Exception: db.rollback();raise
    finally: db.close()

@router.delete("/{channel_id}")
def delete_channel(channel_id:int,current_admin:User=Depends(require_xvond_admin)):
    db=SessionLocal()
    try:
        channel=db.query(AgentChannel).filter(AgentChannel.id==channel_id).first()
        if channel is None: raise HTTPException(404,"Channel not found")
        db.delete(channel);db.commit();return {"channel_id":channel_id,"status":"deleted"}
    finally: db.close()
