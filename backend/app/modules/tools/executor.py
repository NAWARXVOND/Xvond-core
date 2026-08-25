from backend.app.core.config_secrets import reveal_config
from backend.app.core.module_access import require_company_module
from backend.app.modules.ai_agent.models import AIAgent, AIConversation
from backend.app.modules.tools.models import AgentToolAssignment, ToolApprovalRequest
from backend.app.modules.tools.registry import tool_registry
from backend.app.modules.tools.bootstrap import register_builtin_tools

SENSITIVE_TOOLS={"webhook","custom_api"}
def tool_requires_approval(tool_name,config):return True if tool_name in SENSITIVE_TOOLS else bool((config or {}).get("approval_required",False))

def _runtime_description(tool,config):
    description=tool.description;config=config or {}
    if tool.name=="action_request":
        rules=[]
        for action_type,action in (config.get("actions") or {}).items():
            if isinstance(action,dict) and action.get("enabled",True):
                fields=[str(x).strip() for x in (action.get("required_fields") or []) if str(x).strip()];rules.append(f"{action_type}: required customer details = {', '.join(fields) if fields else 'none'}")
        if rules:description+=" CONFIGURED HUMAN-HANDOFF REQUESTS: "+" | ".join(rules)+". Collect only missing details progressively. Before submitting, summarize and obtain customer confirmation. Never hand off this request before required details are complete unless the customer explicitly asks for a human."
    if tool.name=="order":
        fields=[str(x).strip() for x in (config.get("required_fields") or []) if str(x).strip()]
        description+=f" CONFIGURED INTERNAL ORDER FIELDS: {', '.join(fields) if fields else 'none'}. Ask only for missing fields, naturally and progressively. Remember information already provided in conversation history. When all required details are present, summarize the order and ask the customer to confirm it. Call order only after confirmation. After success, tell the customer the order/request number and that it was received; do not transfer to a human unless separately required."
    if tool.name=="booking":
        fields=[str(x).strip() for x in (config.get("required_fields") or []) if str(x).strip()]
        if fields:description+=" Configured booking details: "+", ".join(fields)+". Collect only missing details progressively and confirm before creation."
    if tool.name=="lead":
        fields=[str(x).strip() for x in (config.get("required_fields") or []) if str(x).strip()]
        if fields:description+=" Required lead details: "+", ".join(fields)+". Collect missing details naturally before saving."
    return description

class ToolExecutor:
    def __init__(self):register_builtin_tools()
    def get_agent_tools(self,db,agent_id):
        assignments=db.query(AgentToolAssignment).filter(AgentToolAssignment.agent_id==agent_id,AgentToolAssignment.enabled.is_(True)).order_by(AgentToolAssignment.id.asc()).all();result=[]
        for assignment in assignments:
            tool=tool_registry.get(assignment.tool_name)
            if tool is not None:
                config=reveal_config(assignment.config) or {};result.append({"name":tool.name,"description":_runtime_description(tool,config),"input_schema":tool.input_schema})
        return result
    def validate_execution_scope(self,db,company_id,agent_id,conversation_id=None):
        agent=db.query(AIAgent).filter(AIAgent.id==agent_id,AIAgent.company_id==company_id).first()
        if agent is None:return "Agent does not belong to this company"
        if conversation_id is None:return None
        conversation=db.query(AIConversation).filter(AIConversation.id==conversation_id,AIConversation.company_id==company_id,AIConversation.agent_id==agent_id).first();return None if conversation is not None else "Conversation does not belong to this company and agent"
    def execute(self,db,company_id,agent_id,tool_name,arguments,conversation_id=None,approval_granted=False):
        scope_error=self.validate_execution_scope(db,company_id,agent_id,conversation_id)
        if scope_error:return {"success":False,"tool":tool_name,"data":None,"error":scope_error}
        require_company_module(db,company_id,"tools");assignment=db.query(AgentToolAssignment).filter(AgentToolAssignment.agent_id==agent_id,AgentToolAssignment.tool_name==tool_name,AgentToolAssignment.enabled.is_(True)).first()
        if assignment is None:return {"success":False,"tool":tool_name,"data":None,"error":"Tool is not assigned to this agent"}
        tool=tool_registry.get(tool_name)
        if tool is None:return {"success":False,"tool":tool_name,"data":None,"error":"Tool is not registered"}
        config=reveal_config(assignment.config) or {};approval_required=tool_requires_approval(tool_name,config)
        if approval_required and not approval_granted:
            request=ToolApprovalRequest(company_id=company_id,agent_id=agent_id,conversation_id=conversation_id,tool_name=tool_name,arguments=arguments or {},status="pending");db.add(request);db.flush();return {"success":False,"tool":tool_name,"data":{"approval_request_id":request.id,"status":"pending_approval"},"error":"Tool execution requires human approval","approval_required":True}
        context={"db":db,"company_id":company_id,"agent_id":agent_id,"conversation_id":conversation_id,"config":config}
        try:
            with db.begin_nested():result=tool.execute(arguments=arguments or {},context=context);db.flush()
            return {"success":bool(result.success),"tool":tool_name,"data":result.data,"error":result.error}
        except Exception as exc:return {"success":False,"tool":tool_name,"data":None,"error":str(exc)}

tool_executor=ToolExecutor()
