from backend.app.modules.tools.base import AgentTool, ToolResult
from backend.app.modules.tools.business_models import ActionRequest, HumanHandoff
from backend.app.modules.channels.whatsapp_models import WhatsAppSession
from backend.app.modules.channels.handoff import activate_human_handoff


class ActionRequestTool(AgentTool):
    name = "action_request"
    description = "Submit a fully collected customer request for human handling. Use only after all configured required details are collected and the customer has confirmed the request."
    input_schema = {
        "type": "object",
        "properties": {
            "action_type": {"type": "string", "description": "Configured request type such as booking, order, quote or lead"},
            "details": {"type": "object", "description": "Collected customer details keyed by configured field names", "additionalProperties": True},
            "summary": {"type": "string", "description": "Short human-readable summary of the request"},
            "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]},
        },
        "required": ["action_type", "details", "summary"],
        "additionalProperties": False,
    }

    def execute(self, arguments, context):
        config = context.get("config", {}) or {}
        action_type = str(arguments.get("action_type") or "").strip()
        actions = config.get("actions") or {}
        action_config = actions.get(action_type) if isinstance(actions, dict) else None
        if not isinstance(action_config, dict) or not action_config.get("enabled", True):
            return ToolResult(success=False, error="Action request type is not configured for this employee")
        details = arguments.get("details") or {}
        if not isinstance(details, dict):
            return ToolResult(success=False, error="Action request details must be structured")
        required_fields = [str(x).strip() for x in (action_config.get("required_fields") or []) if str(x).strip()]
        missing = [field for field in required_fields if not str(details.get(field) or "").strip()]
        if missing:
            return ToolResult(success=False, error="Missing required customer details: " + ", ".join(missing))
        summary = str(arguments.get("summary") or "").strip()
        if not summary:
            return ToolResult(success=False, error="Request summary is required")
        db = context["db"]
        conversation_id = context.get("conversation_id")
        request = ActionRequest(company_id=context["company_id"], agent_id=context["agent_id"], conversation_id=conversation_id, action_type=action_type, details=details, summary=summary, status="pending_human")
        db.add(request)
        db.flush()
        reason = f"{action_type} request #{request.id}: {summary}"
        handoff = HumanHandoff(company_id=context["company_id"], agent_id=context["agent_id"], conversation_id=conversation_id, reason=reason, priority=arguments.get("priority", "normal"), department=str(action_config.get("department") or "customer_service"))
        db.add(handoff)
        db.flush()
        session = None
        if conversation_id is not None:
            session = db.query(WhatsAppSession).filter(WhatsAppSession.company_id == context["company_id"], WhatsAppSession.agent_id == context["agent_id"], WhatsAppSession.conversation_id == conversation_id).first()
            if session is not None:
                activate_human_handoff(session, reason=reason)
        return ToolResult(success=True, data={"action":"action_request_created","request_id":request.id,"handoff_id":handoff.id,"status":request.status,"ai_paused":session is not None})


action_request_tool = ActionRequestTool()
