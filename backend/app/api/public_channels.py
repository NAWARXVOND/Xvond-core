import hmac
from urllib.parse import urlparse
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from backend.app.core.agent_runtime import agent_runtime
from backend.app.core.config_secrets import reveal_config
from backend.app.core.database.connection import SessionLocal
from backend.app.modules.channels.models import AgentChannel
from backend.app.api.website_widget import website_behavior

router=APIRouter(prefix="/channels",tags=["Public Agent Channels"])
class WebsiteChatInput(BaseModel):message:str;conversation_id:int|None=None
class VoiceTurnInput(BaseModel):transcript:str;conversation_id:int|None=None;session_id:str|None=None

def secure_equal(received,expected):return bool(received and expected and hmac.compare_digest(str(received),str(expected)))
def host(value):
 if not value:return ""
 parsed=urlparse(value if "://" in value else f"https://{value}");return (parsed.hostname or "").lower().strip(".")
def website_origin_allowed(origin,allowed_domain):
 origin_host=host(origin);allowed_host=host(allowed_domain);return bool(origin_host and allowed_host and (origin_host==allowed_host or origin_host.endswith("."+allowed_host)))
def require_channel(db,channel_id,channel_type):
 channel=db.query(AgentChannel).filter(AgentChannel.id==channel_id,AgentChannel.channel_type==channel_type,AgentChannel.enabled.is_(True)).first()
 if channel is None:raise HTTPException(404,"Channel unavailable")
 return channel

@router.post("/website/{channel_id}/chat")
def website_chat(channel_id:int,data:WebsiteChatInput,request:Request,x_xvond_widget_key:str|None=Header(default=None)):
 db=SessionLocal()
 try:
  channel=require_channel(db,channel_id,"website");config=reveal_config(channel.config)
  if not secure_equal(x_xvond_widget_key,config.get("widget_key")):raise HTTPException(401,"Invalid widget key")
  if not website_origin_allowed(request.headers.get("origin"),config.get("allowed_domain")):raise HTTPException(403,"Website origin is not allowed")
  agent=agent_runtime.get_agent(db,channel.company_id,channel.agent_id);original_prompt=agent.system_prompt
  try:
   agent.system_prompt=(original_prompt+"\n\n"+website_behavior(config)).strip()
   return agent_runtime.chat(db=db,company_id=channel.company_id,agent_id=channel.agent_id,message=data.message,conversation_id=data.conversation_id)
  finally:agent.system_prompt=original_prompt
 finally:db.close()

@router.post("/voice/{channel_id}/turn")
def voice_turn(channel_id:int,data:VoiceTurnInput,x_xvond_voice_token:str|None=Header(default=None)):
 db=SessionLocal()
 try:
  channel=require_channel(db,channel_id,"voice");config=reveal_config(channel.config)
  if not secure_equal(x_xvond_voice_token,config.get("auth_token")):raise HTTPException(401,"Invalid voice channel token")
  result=agent_runtime.chat(db=db,company_id=channel.company_id,agent_id=channel.agent_id,message=data.transcript,conversation_id=data.conversation_id)
  return {"channel_id":channel.id,"session_id":data.session_id,"conversation_id":result["conversation_id"],"text":result["response"]["content"]}
 finally:db.close()
