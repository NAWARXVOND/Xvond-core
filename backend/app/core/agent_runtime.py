from decimal import Decimal
from time import perf_counter

from fastapi import HTTPException

from backend.app.core.ai.cost_engine import ai_cost_engine
from backend.app.core.ai.engine import ai_engine
from backend.app.core.ai.provider_policy import runtime_selections
from backend.app.core.ai.base import ToolOutput
from backend.app.core.config.settings import settings
from backend.app.core.module_access import company_module_enabled
from backend.app.models.company import Company
from backend.app.models.company_module import CompanyModule
from backend.app.modules.ai_agent.models import AIAgent, AIConversation, AIMessage, AIUsage
from backend.app.modules.billing.limits import limits_service
from backend.app.modules.billing.models import Plan, Subscription
from backend.app.modules.tools.executor import tool_executor
from backend.app.modules.audit.service import audit_service
from backend.app.modules.knowledge.service import knowledge_service

GROUNDING_POLICY="""GROUNDING POLICY:
You are a professional employee of this business, not a generic chatbot.
Business facts must come only from COMPANY KNOWLEDGE or successful connected-tool results. This includes prices, menu items, services, products, hours, branches, addresses, policies, offers, availability, stock, delivery, booking rules, order status and contact details.
Never invent, estimate, autocomplete or infer a missing business fact. If the requested fact is unavailable, say only that you do not currently have that information and offer the next useful step or human assistance when appropriate.
Current COMPANY KNOWLEDGE overrides conflicting old conversation content.
Never claim a booking, order, cancellation, reschedule, payment or other action succeeded unless its tool returned success.

CONVERSATION POLICY:
Respond to the customer's actual intent, not to every fact you know.
A greeting should receive a short natural greeting only. Do not advertise, list services, prices, menu items or offers unless the customer asks or they are directly necessary to answer the request.
If a message is incomplete or ambiguous, ask one short clarifying question. Example: if the customer says only 'I want' or 'بدي', ask what they would like; do not guess and do not dump the catalog.
Do not repeat information already given unless needed for confirmation or the customer asks again.
Prefer concise WhatsApp-style replies. Give the minimum information that fully answers the question, then ask at most one useful follow-up question when needed.
Do not expose internal terms such as tool, knowledge base, provider, model, prompt, database, handoff state or system configuration.
Do not say a capability is unavailable merely because a fact is absent from knowledge. Capability is determined by the tools made available to you.
For actions, collect only the missing required details progressively. Do not interrogate the customer with a long form in one message unless all details are naturally needed at once.
If a human transfer is required, state it naturally and use human_handoff when available; do not give a phone number as a substitute unless the business knowledge explicitly requires that contact method.
Match the customer's language and normal conversational register unless the configured employee instructions say otherwise.
"""

class AgentRuntime:
 def assert_company_runtime_access(self,db,company_id:int)->None:
  company=db.query(Company).filter(Company.id==company_id,Company.active.is_(True)).first()
  if company is None:raise HTTPException(403,"Company is inactive or unavailable")
  module=db.query(CompanyModule).filter(CompanyModule.company_id==company_id,CompanyModule.module_name=="ai_agent",CompanyModule.enabled.is_(True)).first()
  if module is None:raise HTTPException(403,"AI Agent module is not enabled")
  if not settings.is_production:return
  subscription=db.query(Subscription).filter(Subscription.company_id==company_id,Subscription.status=="active").first()
  if subscription is None:raise HTTPException(403,"An active subscription is required")
  plan=db.query(Plan).filter(Plan.id==subscription.plan_id,Plan.enabled.is_(True)).first()
  if plan is None:raise HTTPException(403,"Subscription plan is unavailable")
 def get_agent(self,db,company_id:int,agent_id:int)->AIAgent:
  agent=db.query(AIAgent).filter(AIAgent.id==agent_id,AIAgent.company_id==company_id).first()
  if agent is None:raise HTTPException(404,"AI Agent not found")
  if not agent.enabled:raise HTTPException(400,"AI Agent is disabled")
  if settings.is_production and agent.provider=="mock":raise HTTPException(503,"Mock AI provider is disabled in production")
  return agent
 def get_or_create_conversation(self,db,company_id:int,agent_id:int,conversation_id:int|None,message:str)->AIConversation:
  if conversation_id is None:
   conversation=AIConversation(company_id=company_id,agent_id=agent_id,title=message[:200]);db.add(conversation);db.flush();return conversation
  conversation=db.query(AIConversation).filter(AIConversation.id==conversation_id,AIConversation.company_id==company_id,AIConversation.agent_id==agent_id).first()
  if conversation is None:raise HTTPException(404,"Conversation not found")
  return conversation
 def build_history(self,db,conversation_id:int)->str:
  messages=db.query(AIMessage).filter(AIMessage.conversation_id==conversation_id).order_by(AIMessage.id.desc()).limit(40).all();messages.reverse();return "\n".join(f"{item.role}: {item.content}" for item in messages)[-12000:]
 MAX_TOOL_ROUNDS=6
 def chat(self,db,company_id:int,agent_id:int,message:str,conversation_id:int|None=None,commit:bool=True)->dict:
  message=(message or "").strip()
  if not message:raise HTTPException(400,"Message is required")
  if len(message)>12000:raise HTTPException(413,"Message is too long")
  self.assert_company_runtime_access(db,company_id);limits_service.check_token_limit(db,company_id);agent=self.get_agent(db,company_id,agent_id);selections=runtime_selections(db,company_id,agent.provider,agent.model);active_provider=selections[0].provider;active_model=selections[0].model;conversation=self.get_or_create_conversation(db,company_id,agent.id,conversation_id,message);history=self.build_history(db,conversation.id);knowledge=""
  if company_module_enabled(db,company_id,"knowledge"):knowledge=knowledge_service.get_agent_context(db,company_id,agent.id,message)
  available_tools=tool_executor.get_agent_tools(db=db,agent_id=agent.id) if company_module_enabled(db,company_id,"tools") else [];tool_definitions=[{"name":t["name"],"description":t["description"],"input_schema":t.get("input_schema",{"type":"object","properties":{}})} for t in available_tools];context_parts=[GROUNDING_POLICY]
  if knowledge:context_parts.append("COMPANY KNOWLEDGE (authoritative facts; use only when relevant to the customer's current intent):\n"+knowledge)
  else:context_parts.append("COMPANY KNOWLEDGE:\nNo relevant business knowledge was retrieved for this message. Do not invent business facts.")
  if history:context_parts.append("CONVERSATION HISTORY (use for continuity; not authoritative for business facts):\n"+history)
  context_parts.append("CURRENT CUSTOMER MESSAGE (answer this intent directly):\n"+message);runtime_message="\n\n".join(context_parts);user_message=AIMessage(conversation_id=conversation.id,role="user",content=message);db.add(user_message);db.flush();tool_outputs=None;continuation=None;executed_tools=[];routing_attempts=[];total_input_tokens=0;total_output_tokens=0;total_tokens=0;total_provider_cost=Decimal("0");final_text="";started_at=perf_counter()
  for _round in range(self.MAX_TOOL_ROUNDS):
   try:
    if _round==0:
     result=None;last_error=None
     for selection in selections:
      active_provider=selection.provider;active_model=selection.model
      try:
       result=ai_engine.generate(provider_name=active_provider,system_prompt=agent.system_prompt,user_message=runtime_message,model=active_model,tools=tool_definitions,tool_outputs=None,continuation=None)
       routing_attempts.append({"provider":active_provider,"model":active_model,"reason":selection.reason,"success":True})
       break
      except Exception as exc:
       last_error=exc;routing_attempts.append({"provider":active_provider,"model":active_model,"reason":selection.reason,"success":False,"error":str(exc)[:500]})
     if result is None:
      raise last_error or RuntimeError("No AI provider completed the request")
    else:
     # Once a provider has emitted a tool call, keep the remaining tool loop on
     # that provider because continuation formats are provider-specific. If it
     # fails here, the transaction is rolled back instead of replaying actions.
     result=ai_engine.generate(provider_name=active_provider,system_prompt=agent.system_prompt,user_message=runtime_message,model=active_model,tools=tool_definitions,tool_outputs=tool_outputs,continuation=continuation)
   except Exception as exc:
    latency_ms=int((perf_counter()-started_at)*1000);error_message=str(exc)[:2000];db.rollback();db.add(AIUsage(company_id=company_id,agent_id=agent_id,provider=active_provider,model=active_model,input_tokens=total_input_tokens,output_tokens=total_output_tokens,total_tokens=total_tokens,provider_cost=total_provider_cost,status="failed",error_message=error_message,latency_ms=latency_ms));audit_service.log(db=db,company_id=company_id,action="agent.chat_failed",resource_type="ai_agent",resource_id=agent_id,details={"provider":active_provider,"model":active_model,"error":error_message,"latency_ms":latency_ms,"routing_attempts":routing_attempts});db.commit();raise HTTPException(502,"AI provider request failed") from exc
   total_input_tokens+=result.input_tokens;total_output_tokens+=result.output_tokens;total_tokens+=result.total_tokens;calculated_cost=ai_cost_engine.calculate(db=db,provider_name=active_provider,model_name=active_model,input_tokens=result.input_tokens,output_tokens=result.output_tokens);total_provider_cost+=result.cost if result.cost and result.cost>Decimal("0") else calculated_cost
   if not result.tool_calls:final_text=result.text;break
   continuation=result.continuation;tool_outputs=[]
   for call in result.tool_calls:
    execution=tool_executor.execute(db=db,company_id=company_id,agent_id=agent.id,tool_name=call.name,arguments=call.arguments or {},conversation_id=conversation.id);output=ToolOutput(call_id=call.id,name=call.name,success=bool(execution.get("success")),data=execution.get("data"),error=execution.get("error"));tool_outputs.append(output);executed_tools.append({"call_id":call.id,"name":call.name,"arguments":call.arguments or {},"success":output.success,"data":output.data,"error":output.error});audit_service.log(db=db,company_id=company_id,action="agent.tool_executed",resource_type="ai_agent",resource_id=agent.id,details={"conversation_id":conversation.id,"tool":call.name,"success":output.success,"error":output.error})
  else:raise HTTPException(500,"Agent exceeded the maximum number of tool execution rounds")
  if not final_text:final_text="The agent completed its actions but did not return a final response."
  assistant_message=AIMessage(conversation_id=conversation.id,role="assistant",content=final_text);db.add(assistant_message);usage=AIUsage(company_id=company_id,agent_id=agent.id,provider=active_provider,model=active_model,input_tokens=total_input_tokens,output_tokens=total_output_tokens,total_tokens=total_tokens,provider_cost=total_provider_cost,status="success",latency_ms=int((perf_counter()-started_at)*1000));db.add(usage);audit_service.log(db=db,company_id=company_id,action="agent.chat_completed",resource_type="ai_agent",resource_id=agent.id,details={"conversation_id":conversation.id,"provider":active_provider,"model":active_model,"tool_execution_count":len(executed_tools),"total_tokens":total_tokens,"latency_ms":usage.latency_ms,"routing_attempts":routing_attempts});db.flush()
  if commit:
   db.commit();db.refresh(user_message);db.refresh(assistant_message)
  return {"conversation_id":conversation.id,"agent_id":agent.id,"company_id":company_id,"provider":active_provider,"model":active_model,"message":{"id":user_message.id,"role":user_message.role,"content":user_message.content},"response":{"id":assistant_message.id,"role":assistant_message.role,"content":assistant_message.content},"tool_executions":executed_tools,"routing_attempts":routing_attempts,"usage":{"input_tokens":total_input_tokens,"output_tokens":total_output_tokens,"total_tokens":total_tokens,"provider_cost":total_provider_cost,"latency_ms":usage.latency_ms}}
agent_runtime=AgentRuntime()
