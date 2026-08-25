from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.tools.models import AgentToolAssignment

router = APIRouter(prefix="/admin/agent-actions", tags=["Xvond Admin - Agent Actions"])
VALID_MODES = {"disabled", "xvond_internal", "human_handoff"}

class ActionSettings(BaseModel):
    booking_mode: str = "disabled"
    booking_fields: list[str] = Field(default_factory=list)
    order_mode: str = "disabled"
    order_fields: list[str] = Field(default_factory=list)
    lead_enabled: bool = True
    lead_fields: list[str] = Field(default_factory=lambda:["name","phone"])


def _assignment(db, agent_id, name):
    return db.query(AgentToolAssignment).filter(AgentToolAssignment.agent_id==agent_id,AgentToolAssignment.tool_name==name).first()

def _set(db,agent_id,name,enabled,config):
    row=_assignment(db,agent_id,name)
    if row:
        row.enabled=enabled;row.config=config
    else:
        db.add(AgentToolAssignment(agent_id=agent_id,tool_name=name,enabled=enabled,config=config))

def _fields(values):
    out=[]
    for value in values or []:
        v=str(value).strip()
        if v and v not in out:out.append(v)
    return out[:30]

@router.get("/{agent_id}")
def get_actions(agent_id:int,current_admin:User=Depends(require_xvond_admin)):
    db=SessionLocal()
    try:
        agent=db.query(AIAgent).filter(AIAgent.id==agent_id).first()
        if not agent:raise HTTPException(404,"AI employee not found")
        request=_assignment(db,agent_id,"action_request");cfg=(request.config or {}) if request else {};actions=cfg.get("actions") or {}
        booking=_assignment(db,agent_id,"booking");order=_assignment(db,agent_id,"order");lead=_assignment(db,agent_id,"lead")
        bm="xvond_internal" if booking and booking.enabled else ("human_handoff" if actions.get("booking",{}).get("enabled") else "disabled")
        om="xvond_internal" if order and order.enabled else ("human_handoff" if actions.get("order",{}).get("enabled") else "disabled")
        return {"booking_mode":bm,"booking_fields":actions.get("booking",{}).get("required_fields",["customer_name","phone","service","date","time"]),"order_mode":om,"order_fields":actions.get("order",{}).get("required_fields",["customer_name","phone","request","date","location"]),"lead_enabled":bool(lead and lead.enabled),"lead_fields":((lead.config or {}).get("required_fields") if lead else None) or ["name","phone"]}
    finally:db.close()

@router.put("/{agent_id}")
def update_actions(agent_id:int,data:ActionSettings,current_admin:User=Depends(require_xvond_admin)):
    db=SessionLocal()
    try:
        agent=db.query(AIAgent).filter(AIAgent.id==agent_id).first()
        if not agent:raise HTTPException(404,"AI employee not found")
        if data.booking_mode not in VALID_MODES or data.order_mode not in VALID_MODES:raise HTTPException(400,"Invalid action mode")
        booking_fields=_fields(data.booking_fields);order_fields=_fields(data.order_fields);lead_fields=_fields(data.lead_fields)
        _set(db,agent_id,"booking",data.booking_mode=="xvond_internal",{"approval_required":False,"mode":"xvond_internal"})
        _set(db,agent_id,"order",data.order_mode=="xvond_internal",{"approval_required":False,"mode":"xvond_internal"})
        _set(db,agent_id,"lead",data.lead_enabled,{"approval_required":False,"required_fields":lead_fields})
        _set(db,agent_id,"human_handoff",True,{"approval_required":False})
        actions={}
        if data.booking_mode=="human_handoff":actions["booking"]={"enabled":True,"required_fields":booking_fields,"department":"bookings"}
        if data.order_mode=="human_handoff":actions["order"]={"enabled":True,"required_fields":order_fields,"department":"orders"}
        _set(db,agent_id,"action_request",bool(actions),{"approval_required":False,"actions":actions})
        db.commit();return {"status":"updated"}
    except HTTPException:db.rollback();raise
    except Exception:db.rollback();raise
    finally:db.close()
