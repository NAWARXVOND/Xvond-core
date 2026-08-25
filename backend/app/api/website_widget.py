import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from backend.app.api.admin_channels import _ensure_channels_module, _has_real_runtime_provider
from backend.app.core.config.settings import settings
from backend.app.core.config_secrets import merge_config, reveal_config
from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.knowledge.models import AgentKnowledge, KnowledgeDocument

router = APIRouter(tags=["Website AI Widget"])


class WebsiteSetup(BaseModel):
    allowed_domain: str
    widget_name: str | None = None
    welcome_message: str | None = None
    position: str = "right"
    custom_instructions: str | None = None
    accent_color: str = "#111827"
    launcher_label: str = "Chat"


DEFAULT_BEHAVIOR = """WEBSITE CHANNEL CONTEXT:
You are speaking with a visitor through the business website chat widget.
The website is only the communication channel. Your business identity, knowledge and configured actions are shared with the same AI employee across channels.
Be concise, natural and useful. Do not dump services, prices or menus unless relevant to the visitor's request.
If the request is vague, ask one short clarifying question.
Never invent business facts and never claim an action succeeded unless its configured action returned success.
Do not mention AI providers, prompts, tools, databases, routing or Xvond internals.
"""


def _embed(channel_id: int) -> str:
    src = f"/channels/website/{channel_id}/widget.js"
    if settings.PUBLIC_BASE_URL:
        src = settings.PUBLIC_BASE_URL + src
    return f'<script src="{src}" async></script>'


def _useful_business_knowledge(document: KnowledgeDocument) -> bool:
    content = (document.content or "").strip()
    if len(content) < 20:
        return False
    if document.source_type != "business_profile":
        return True
    # A company profile becomes sufficient only when it contains substantive
    # operating facts, not merely a company name/type placeholder.
    markers = (
        "Description:",
        "Working Hours:",
        "Locations / Branches:",
        "Services:",
        "Policies:",
        "Business Rules:",
    )
    return len(content) >= 80 and any(marker in content for marker in markers)


def _ready(db, channel: AgentChannel) -> list[str]:
    blockers = []
    agent = db.query(AIAgent).filter(
        AIAgent.id == channel.agent_id,
        AIAgent.company_id == channel.company_id,
        AIAgent.enabled.is_(True),
    ).first()
    if not agent:
        blockers.append("AI employee must be active")
    elif not _has_real_runtime_provider(db, channel.company_id, agent):
        blockers.append("At least one real AI provider/model must be configured")
    config = reveal_config(channel.config) or {}
    if not str(config.get("allowed_domain") or "").strip():
        blockers.append("Allowed website domain is required")
    if not str(config.get("widget_key") or "").strip():
        blockers.append("Widget key is missing")
    if settings.is_production and not settings.PUBLIC_BASE_URL:
        blockers.append("Xvond public API URL is not configured")
    docs = (
        db.query(KnowledgeDocument)
        .join(AgentKnowledge, AgentKnowledge.document_id == KnowledgeDocument.id)
        .filter(
            KnowledgeDocument.company_id == channel.company_id,
            KnowledgeDocument.enabled.is_(True),
            AgentKnowledge.agent_id == channel.agent_id,
            AgentKnowledge.enabled.is_(True),
        )
        .all()
    )
    if not any(_useful_business_knowledge(doc) for doc in docs):
        blockers.append("Add real business knowledge before activating Website Chat")
    return blockers


def _behavior(config: dict) -> str:
    custom = str(config.get("custom_instructions") or "").strip()
    parts = [DEFAULT_BEHAVIOR]
    if custom:
        parts.append("Website-specific instructions: " + custom)
    return "\n".join(parts)


@router.get("/admin/website-channel/agents/{agent_id}")
def get_config(agent_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        channel = db.query(AgentChannel).filter(AgentChannel.agent_id == agent_id, AgentChannel.channel_type == "website").first()
        if not channel:
            return {"configured": False}
        config = reveal_config(channel.config) or {}
        blockers = _ready(db, channel)
        safe = {key: value for key, value in config.items() if key != "widget_key"}
        return {"configured": True, "channel_id": channel.id, "enabled": channel.enabled, "ready": not blockers, "blockers": blockers, "config": safe, "embed_code": _embed(channel.id)}
    finally:
        db.close()


@router.put("/admin/website-channel/agents/{agent_id}")
def configure(agent_id: int, data: WebsiteSetup, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        agent = db.query(AIAgent).filter(AIAgent.id == agent_id).first()
        if not agent:
            raise HTTPException(404, "AI employee not found")
        domain = data.allowed_domain.strip()
        if not domain:
            raise HTTPException(400, "Allowed domain is required")
        channel = db.query(AgentChannel).filter(AgentChannel.agent_id == agent_id, AgentChannel.channel_type == "website").first()
        config = {
            "allowed_domain": domain,
            "widget_name": (data.widget_name or agent.name).strip(),
            "welcome_message": (data.welcome_message or "مرحباً، كيف يمكنني مساعدتك؟").strip(),
            "position": "left" if data.position == "left" else "right",
            "custom_instructions": (data.custom_instructions or "").strip(),
            "accent_color": data.accent_color if data.accent_color.startswith("#") else "#111827",
            "launcher_label": (data.launcher_label or "Chat").strip()[:30],
        }
        if channel:
            old = reveal_config(channel.config) or {}
            config["widget_key"] = old.get("widget_key") or secrets.token_urlsafe(32)
            if isinstance(old.get("employee_setup"), dict):
                config["employee_setup"] = old["employee_setup"]
            channel.config = merge_config(channel.config, config)
            channel.enabled = False
        else:
            config["widget_key"] = secrets.token_urlsafe(32)
            channel = AgentChannel(company_id=agent.company_id, agent_id=agent.id, channel_type="website", config=config, enabled=False)
            db.add(channel)
        _ensure_channels_module(db, agent.company_id)
        db.commit()
        db.refresh(channel)
        blockers = _ready(db, channel)
        return {"status": "configured", "channel_id": channel.id, "ready": not blockers, "blockers": blockers, "embed_code": _embed(channel.id)}
    finally:
        db.close()


@router.post("/admin/website-channel/{channel_id}/activate")
def activate(channel_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        channel = db.query(AgentChannel).filter(AgentChannel.id == channel_id, AgentChannel.channel_type == "website").first()
        if not channel:
            raise HTTPException(404, "Website channel not found")
        blockers = _ready(db, channel)
        if blockers:
            raise HTTPException(409, "Website Chat is not ready: " + "; ".join(blockers))
        channel.enabled = True
        db.commit()
        return {"status": "active", "channel_id": channel.id}
    finally:
        db.close()


@router.post("/admin/website-channel/{channel_id}/deactivate")
def deactivate(channel_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        channel = db.query(AgentChannel).filter(AgentChannel.id == channel_id, AgentChannel.channel_type == "website").first()
        if not channel:
            raise HTTPException(404, "Website channel not found")
        channel.enabled = False
        db.commit()
        return {"status": "inactive"}
    finally:
        db.close()


@router.get("/channels/website/{channel_id}/widget.js")
def widget_js(channel_id: int):
    db = SessionLocal()
    try:
        channel = db.query(AgentChannel).filter(AgentChannel.id == channel_id, AgentChannel.channel_type == "website", AgentChannel.enabled.is_(True)).first()
        if not channel:
            raise HTTPException(404, "Widget unavailable")
        config = reveal_config(channel.config) or {}
        key = config.get("widget_key")
        name = config.get("widget_name") or "AI Assistant"
        welcome = config.get("welcome_message") or "مرحباً، كيف يمكنني مساعدتك؟"
        position = config.get("position") or "right"
        accent = config.get("accent_color") or "#111827"
        label = config.get("launcher_label") or "Chat"
        js = f'''(()=>{{if(window.__xvondWidget)return;window.__xvondWidget=1;const API=new URL(document.currentScript.src).origin;let cid=sessionStorage.getItem('xvond_conversation_{channel_id}')||null;let lastId=Number(sessionStorage.getItem('xvond_last_{channel_id}')||0);const side={position!r};const accent={accent!r};const headers={{'Content-Type':'application/json','X-Xvond-Widget-Key':{key!r}}};const css=`#xvond-btn{{position:fixed;bottom:20px;${{side}}:20px;z-index:2147483646;border:0;border-radius:999px;padding:14px 18px;cursor:pointer;box-shadow:0 8px 30px #0003;background:${{accent}};color:#fff}}#xvond-box{{position:fixed;bottom:78px;${{side}}:20px;width:min(380px,calc(100vw - 24px));height:520px;max-height:70vh;background:#fff;color:#111;z-index:2147483647;border-radius:18px;box-shadow:0 18px 60px #0004;display:none;overflow:hidden;font-family:Arial,sans-serif}}#xvond-head{{padding:16px;font-weight:700;border-bottom:1px solid #eee}}#xvond-msgs{{height:calc(100% - 118px);overflow:auto;padding:14px}}.xvond-m{{margin:8px 0;padding:10px 12px;border-radius:12px;white-space:pre-wrap;line-height:1.4}}.xvond-u{{background:#eef3ff;margin-left:40px}}.xvond-a{{background:#f5f5f5;margin-right:40px}}#xvond-form{{display:flex;border-top:1px solid #eee;padding:10px;gap:8px}}#xvond-in{{flex:1;border:1px solid #ddd;border-radius:10px;padding:10px}}#xvond-send{{border:0;border-radius:10px;padding:10px 14px;cursor:pointer;background:${{accent}};color:#fff}}`;const st=document.createElement('style');st.textContent=css;document.head.appendChild(st);const btn=document.createElement('button');btn.id='xvond-btn';btn.textContent={label!r};const box=document.createElement('div');box.id='xvond-box';box.innerHTML=`<div id="xvond-head"></div><div id="xvond-msgs"></div><form id="xvond-form"><input id="xvond-in" autocomplete="off" placeholder="اكتب رسالتك"><button id="xvond-send">إرسال</button></form>`;document.body.append(btn,box);box.querySelector('#xvond-head').textContent={name!r};const msgs=box.querySelector('#xvond-msgs');function add(t,c){{if(!t)return;const d=document.createElement('div');d.className='xvond-m '+c;d.textContent=t;msgs.appendChild(d);msgs.scrollTop=msgs.scrollHeight}}function remember(id){{if(id&&id>lastId){{lastId=id;sessionStorage.setItem('xvond_last_{channel_id}',String(lastId))}}}}add({welcome!r},'xvond-a');btn.onclick=()=>box.style.display=box.style.display==='block'?'none':'block';box.querySelector('#xvond-form').onsubmit=async e=>{{e.preventDefault();const input=box.querySelector('#xvond-in');const m=input.value.trim();if(!m)return;input.value='';add(m,'xvond-u');try{{const r=await fetch(API+'/channels/website/{channel_id}/chat',{{method:'POST',headers,body:JSON.stringify({{message:m,conversation_id:cid}})}});const j=await r.json();if(!r.ok)throw new Error(j.detail||'Request failed');cid=j.conversation_id;sessionStorage.setItem('xvond_conversation_{channel_id}',cid);if(j.message)remember(j.message.id);if(j.response){{add(j.response.content,'xvond-a');remember(j.response.id)}}}}catch(_e){{add('تعذر إرسال الرسالة الآن. حاول مرة أخرى.','xvond-a')}}}};async function poll(){{if(!cid)return;try{{const r=await fetch(API+`/channels/website/{channel_id}/conversation/${{cid}}/messages?after_id=${{lastId}}`,{{headers:{{'X-Xvond-Widget-Key':{key!r}}}}});if(!r.ok)return;const j=await r.json();for(const m of (j.messages||[])){{remember(m.id);if(m.role==='human')add(m.content,'xvond-a')}}}}catch(_e){{}}}}setInterval(poll,2500)}})();'''
        return Response(content=js, media_type="application/javascript", headers={"Cache-Control": "no-store"})
    finally:
        db.close()


def website_behavior(config: dict) -> str:
    return _behavior(config)
