import secrets
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.core.config_secrets import merge_config, reveal_config
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.channels.models import AgentChannel
from backend.app.api.admin_channels import _ensure_channels_module, _has_real_runtime_provider
from backend.app.modules.knowledge.models import AgentKnowledge, KnowledgeDocument

router=APIRouter(tags=["Website AI Widget"])

class WebsiteSetup(BaseModel):
    allowed_domain:str
    widget_name:str|None=None
    welcome_message:str|None=None
    position:str="right"

def _ready(db,ch):
    blockers=[]
    agent=db.query(AIAgent).filter(AIAgent.id==ch.agent_id,AIAgent.company_id==ch.company_id,AIAgent.enabled.is_(True)).first()
    if not agent: blockers.append("AI employee must be active")
    elif not _has_real_runtime_provider(db,ch.company_id,agent): blockers.append("At least one real AI provider/model must be configured")
    cfg=reveal_config(ch.config)
    if not str(cfg.get("allowed_domain") or "").strip(): blockers.append("Allowed website domain is required")
    if not str(cfg.get("widget_key") or "").strip(): blockers.append("Widget key is missing")
    docs=db.query(KnowledgeDocument).join(AgentKnowledge,AgentKnowledge.document_id==KnowledgeDocument.id).filter(KnowledgeDocument.company_id==ch.company_id,KnowledgeDocument.enabled.is_(True),AgentKnowledge.agent_id==ch.agent_id,AgentKnowledge.enabled.is_(True)).all()
    if not any(len((d.content or "").strip())>=20 and d.source_type!="business_profile" for d in docs): blockers.append("Add real business knowledge before activating Website Chat")
    return blockers

@router.put("/admin/website-channel/agents/{agent_id}")
def configure(agent_id:int,data:WebsiteSetup,current_admin:User=Depends(require_xvond_admin)):
    db=SessionLocal()
    try:
        agent=db.query(AIAgent).filter(AIAgent.id==agent_id).first()
        if not agent: raise HTTPException(404,"AI employee not found")
        ch=db.query(AgentChannel).filter(AgentChannel.agent_id==agent_id,AgentChannel.channel_type=="website").first()
        config={"allowed_domain":data.allowed_domain.strip(),"widget_name":(data.widget_name or agent.name).strip(),"welcome_message":(data.welcome_message or "مرحباً، كيف يمكنني مساعدتك؟").strip(),"position":"left" if data.position=="left" else "right"}
        if ch:
            old=reveal_config(ch.config);config["widget_key"]=old.get("widget_key") or secrets.token_urlsafe(32);ch.config=merge_config(ch.config,config);ch.enabled=False
        else:
            config["widget_key"]=secrets.token_urlsafe(32);ch=AgentChannel(company_id=agent.company_id,agent_id=agent.id,channel_type="website",config=config,enabled=False);db.add(ch)
        _ensure_channels_module(db,agent.company_id);db.commit();db.refresh(ch);blockers=_ready(db,ch)
        return {"status":"configured","channel_id":ch.id,"ready":not blockers,"blockers":blockers,"embed_code":f'<script src="/channels/website/{ch.id}/widget.js" async></script>'}
    finally: db.close()

@router.post("/admin/website-channel/{channel_id}/activate")
def activate(channel_id:int,current_admin:User=Depends(require_xvond_admin)):
    db=SessionLocal()
    try:
        ch=db.query(AgentChannel).filter(AgentChannel.id==channel_id,AgentChannel.channel_type=="website").first()
        if not ch: raise HTTPException(404,"Website channel not found")
        blockers=_ready(db,ch)
        if blockers: raise HTTPException(409,"Website Chat is not ready: "+"; ".join(blockers))
        ch.enabled=True;db.commit();return {"status":"active","channel_id":ch.id}
    finally: db.close()

@router.get("/channels/website/{channel_id}/widget.js")
def widget_js(channel_id:int):
    db=SessionLocal()
    try:
        ch=db.query(AgentChannel).filter(AgentChannel.id==channel_id,AgentChannel.channel_type=="website",AgentChannel.enabled.is_(True)).first()
        if not ch: raise HTTPException(404,"Widget unavailable")
        cfg=reveal_config(ch.config);key=cfg.get("widget_key");name=cfg.get("widget_name") or "AI Assistant";welcome=cfg.get("welcome_message") or "مرحباً، كيف يمكنني مساعدتك؟";position=cfg.get("position") or "right"
        js=f'''(()=>{{if(window.__xvondWidget)return;window.__xvondWidget=1;const API=new URL('/channels/website/{channel_id}/chat',document.currentScript.src).origin;let cid=null;const side={position!r};const css=`#xvond-btn{{position:fixed;bottom:20px;${{side}}:20px;z-index:2147483646;border:0;border-radius:999px;padding:14px 18px;cursor:pointer;box-shadow:0 8px 30px #0003}}#xvond-box{{position:fixed;bottom:78px;${{side}}:20px;width:min(380px,calc(100vw - 24px));height:520px;max-height:70vh;background:#fff;color:#111;z-index:2147483647;border-radius:18px;box-shadow:0 18px 60px #0004;display:none;overflow:hidden;font-family:Arial,sans-serif}}#xvond-head{{padding:16px;font-weight:700;border-bottom:1px solid #eee}}#xvond-msgs{{height:calc(100% - 118px);overflow:auto;padding:14px}}.xvond-m{{margin:8px 0;padding:10px 12px;border-radius:12px;white-space:pre-wrap;line-height:1.4}}.xvond-u{{background:#eef3ff;margin-left:40px}}.xvond-a{{background:#f5f5f5;margin-right:40px}}#xvond-form{{display:flex;border-top:1px solid #eee;padding:10px;gap:8px}}#xvond-in{{flex:1;border:1px solid #ddd;border-radius:10px;padding:10px}}#xvond-send{{border:0;border-radius:10px;padding:10px 14px;cursor:pointer}}`;const st=document.createElement('style');st.textContent=css;document.head.appendChild(st);const btn=document.createElement('button');btn.id='xvond-btn';btn.textContent='Chat';const box=document.createElement('div');box.id='xvond-box';box.innerHTML=`<div id="xvond-head"></div><div id="xvond-msgs"></div><form id="xvond-form"><input id="xvond-in" autocomplete="off" placeholder="اكتب رسالتك"><button id="xvond-send">إرسال</button></form>`;document.body.append(btn,box);box.querySelector('#xvond-head').textContent={name!r};const msgs=box.querySelector('#xvond-msgs');function add(t,c){{const d=document.createElement('div');d.className='xvond-m '+c;d.textContent=t;msgs.appendChild(d);msgs.scrollTop=msgs.scrollHeight}}add({welcome!r},'xvond-a');btn.onclick=()=>box.style.display=box.style.display==='block'?'none':'block';box.querySelector('#xvond-form').onsubmit=async e=>{{e.preventDefault();const input=box.querySelector('#xvond-in');const m=input.value.trim();if(!m)return;input.value='';add(m,'xvond-u');try{{const r=await fetch(API+'/channels/website/{channel_id}/chat',{{method:'POST',headers:{{'Content-Type':'application/json','X-Xvond-Widget-Key':{key!r}}},body:JSON.stringify({{message:m,conversation_id:cid}})}});const j=await r.json();if(!r.ok)throw new Error(j.detail||'Request failed');cid=j.conversation_id;add(j.response.content,'xvond-a')}}catch(_e){{add('تعذر إرسال الرسالة الآن. حاول مرة أخرى.','xvond-a')}}}}}})();'''
        return Response(content=js,media_type="application/javascript",headers={"Cache-Control":"no-store"})
    finally: db.close()
