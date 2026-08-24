from decimal import Decimal

from fastapi import HTTPException

from backend.app.core.ai.cost_engine import ai_cost_engine
from backend.app.core.ai.engine import ai_engine
from backend.app.core.ai.base import ToolOutput
from backend.app.core.config.settings import settings

from backend.app.models.company import Company
from backend.app.models.company_module import CompanyModule

from backend.app.modules.ai_agent.models import (
    AIAgent,
    AIConversation,
    AIMessage,
    AIUsage,
)

from backend.app.modules.billing.limits import limits_service
from backend.app.modules.billing.models import Plan, Subscription
from backend.app.modules.tools.executor import tool_executor
from backend.app.modules.audit.service import audit_service

from backend.app.modules.knowledge.service import (
    knowledge_service,
)


class AgentRuntime:

    def assert_company_runtime_access(
        self,
        db,
        company_id: int,
    ) -> None:
        company = (
            db.query(Company)
            .filter(
                Company.id == company_id,
                Company.active.is_(True),
            )
            .first()
        )

        if company is None:
            raise HTTPException(
                status_code=403,
                detail="Company is inactive or unavailable",
            )

        module = (
            db.query(CompanyModule)
            .filter(
                CompanyModule.company_id == company_id,
                CompanyModule.module_name == "ai_agent",
                CompanyModule.enabled.is_(True),
            )
            .first()
        )

        if module is None:
            raise HTTPException(
                status_code=403,
                detail="AI Agent module is not enabled",
            )

        if not settings.is_production:
            return

        subscription = (
            db.query(Subscription)
            .filter(
                Subscription.company_id == company_id,
                Subscription.status == "active",
            )
            .first()
        )

        if subscription is None:
            raise HTTPException(
                status_code=403,
                detail="An active subscription is required",
            )

        plan = (
            db.query(Plan)
            .filter(
                Plan.id == subscription.plan_id,
                Plan.enabled.is_(True),
            )
            .first()
        )

        if plan is None:
            raise HTTPException(
                status_code=403,
                detail="Subscription plan is unavailable",
            )

    def get_agent(
        self,
        db,
        company_id: int,
        agent_id: int,
    ) -> AIAgent:

        agent = (
            db.query(AIAgent)
            .filter(
                AIAgent.id == agent_id,
                AIAgent.company_id == company_id,
            )
            .first()
        )

        if agent is None:
            raise HTTPException(
                status_code=404,
                detail="AI Agent not found",
            )

        if not agent.enabled:
            raise HTTPException(
                status_code=400,
                detail="AI Agent is disabled",
            )

        if settings.is_production and agent.provider == "mock":
            raise HTTPException(
                status_code=503,
                detail="Mock AI provider is disabled in production",
            )

        return agent

    def get_or_create_conversation(
        self,
        db,
        company_id: int,
        agent_id: int,
        conversation_id: int | None,
        message: str,
    ) -> AIConversation:

        if conversation_id is None:
            conversation = AIConversation(
                company_id=company_id,
                agent_id=agent_id,
                title=message[:200],
            )

            db.add(conversation)
            db.flush()

            return conversation

        conversation = (
            db.query(AIConversation)
            .filter(
                AIConversation.id == conversation_id,
                AIConversation.company_id == company_id,
                AIConversation.agent_id == agent_id,
            )
            .first()
        )

        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found",
            )

        return conversation

    def build_history(
        self,
        db,
        conversation_id: int,
    ) -> str:

        messages = (
            db.query(AIMessage)
            .filter(
                AIMessage.conversation_id
                == conversation_id
            )
            .order_by(
                AIMessage.id.desc()
            )
            .limit(40)
            .all()
        )

        messages.reverse()

        history = "\n".join(
            f"{item.role}: {item.content}"
            for item in messages
        )

        # Prevent old conversations from
        # growing the AI context forever.
        return history[-12000:]

    MAX_TOOL_ROUNDS = 6

    def chat(
        self,
        db,
        company_id: int,
        agent_id: int,
        message: str,
        conversation_id: int | None = None,
    ) -> dict:

        message = (message or "").strip()

        if not message:
            raise HTTPException(
                status_code=400,
                detail="Message is required",
            )

        if len(message) > 12000:
            raise HTTPException(
                status_code=413,
                detail="Message is too long",
            )

        self.assert_company_runtime_access(
            db,
            company_id,
        )

        limits_service.check_token_limit(
            db,
            company_id,
        )

        agent = self.get_agent(
            db,
            company_id,
            agent_id,
        )

        conversation = self.get_or_create_conversation(
            db=db,
            company_id=company_id,
            agent_id=agent.id,
            conversation_id=conversation_id,
            message=message,
        )

        history = self.build_history(
            db,
            conversation.id,
        )

        knowledge = (
            knowledge_service.get_agent_context(
                db=db,
                company_id=company_id,
                agent_id=agent.id,
                query=message,
            )
        )

        available_tools = (
            tool_executor.get_agent_tools(
                db=db,
                agent_id=agent.id,
            )
        )

        tool_definitions = [
            {
                "name": tool["name"],
                "description":
                    tool["description"],
                "input_schema":
                    tool.get(
                        "input_schema",
                        {
                            "type": "object",
                            "properties": {},
                        },
                    ),
            }
            for tool in available_tools
        ]

        context_parts = []

        if knowledge:
            context_parts.append(
                "COMPANY KNOWLEDGE:\n"
                + knowledge
            )

        if history:
            context_parts.append(
                "CONVERSATION HISTORY:\n"
                + history
            )

        context_parts.append(
            "CURRENT USER MESSAGE:\n"
            + message
        )

        runtime_message = (
            "\n\n".join(
                context_parts
            )
        )

        user_message = AIMessage(
            conversation_id=conversation.id,
            role="user",
            content=message,
        )

        db.add(user_message)
        db.flush()

        tool_outputs = None
        continuation = None

        executed_tools = []

        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0

        total_provider_cost = Decimal(
            "0"
        )

        final_text = ""

        for _round in range(
            self.MAX_TOOL_ROUNDS
        ):

            result = ai_engine.generate(
                provider_name=agent.provider,
                system_prompt=agent.system_prompt,
                user_message=runtime_message,
                model=agent.model,
                tools=tool_definitions,
                tool_outputs=tool_outputs,
                continuation=continuation,
            )

            total_input_tokens += (
                result.input_tokens
            )

            total_output_tokens += (
                result.output_tokens
            )

            total_tokens += (
                result.total_tokens
            )

            calculated_cost = (
                ai_cost_engine.calculate(
                    db=db,
                    provider_name=agent.provider,
                    model_name=agent.model,
                    input_tokens=
                        result.input_tokens,
                    output_tokens=
                        result.output_tokens,
                )
            )

            round_cost = (
                result.cost
                if (
                    result.cost
                    and result.cost
                    > Decimal("0")
                )
                else calculated_cost
            )

            total_provider_cost += (
                round_cost
            )

            if not result.tool_calls:

                final_text = result.text
                break

            continuation = (
                result.continuation
            )

            tool_outputs = []

            for call in result.tool_calls:

                execution = (
                    tool_executor.execute(
                        db=db,
                        company_id=company_id,
                        agent_id=agent.id,
                        tool_name=call.name,
                        arguments=
                            call.arguments
                            or {},
                        conversation_id=
                            conversation.id,
                    )
                )

                output = ToolOutput(
                    call_id=call.id,
                    name=call.name,
                    success=bool(
                        execution.get(
                            "success"
                        )
                    ),
                    data=execution.get(
                        "data"
                    ),
                    error=execution.get(
                        "error"
                    ),
                )

                tool_outputs.append(
                    output
                )

                executed_tools.append({
                    "call_id":
                        call.id,
                    "name":
                        call.name,
                    "arguments":
                        call.arguments or {},
                    "success":
                        output.success,
                    "data":
                        output.data,
                    "error":
                        output.error,
                })

                audit_service.log(
                    db=db,
                    company_id=company_id,
                    action="agent.tool_executed",
                    resource_type="ai_agent",
                    resource_id=agent.id,
                    details={
                        "conversation_id":
                            conversation.id,
                        "tool":
                            call.name,
                        "success":
                            output.success,
                        "error":
                            output.error,
                    },
                )

        else:

            raise HTTPException(
                status_code=500,
                detail=(
                    "Agent exceeded the "
                    "maximum number of tool "
                    "execution rounds"
                ),
            )

        if not final_text:

            final_text = (
                "The agent completed its "
                "actions but did not return "
                "a final response."
            )

        assistant_message = AIMessage(
            conversation_id=
                conversation.id,
            role="assistant",
            content=final_text,
        )

        db.add(assistant_message)

        usage = AIUsage(
            company_id=company_id,
            agent_id=agent.id,
            provider=agent.provider,
            model=agent.model,
            input_tokens=
                total_input_tokens,
            output_tokens=
                total_output_tokens,
            total_tokens=
                total_tokens,
            provider_cost=
                total_provider_cost,
        )

        db.add(usage)

        audit_service.log(
            db=db,
            company_id=company_id,
            action="agent.chat_completed",
            resource_type="ai_agent",
            resource_id=agent.id,
            details={
                "conversation_id":
                    conversation.id,
                "provider":
                    agent.provider,
                "model":
                    agent.model,
                "tool_execution_count":
                    len(executed_tools),
                "total_tokens":
                    total_tokens,
            },
        )

        db.commit()

        db.refresh(user_message)
        db.refresh(assistant_message)

        return {
            "conversation_id":
                conversation.id,
            "agent_id":
                agent.id,
            "company_id":
                company_id,
            "provider":
                agent.provider,
            "model":
                agent.model,

            "message": {
                "id":
                    user_message.id,
                "role":
                    user_message.role,
                "content":
                    user_message.content,
            },

            "response": {
                "id":
                    assistant_message.id,
                "role":
                    assistant_message.role,
                "content":
                    assistant_message.content,
            },

            "tool_executions":
                executed_tools,

            "usage": {
                "input_tokens":
                    total_input_tokens,
                "output_tokens":
                    total_output_tokens,
                "total_tokens":
                    total_tokens,
                "provider_cost":
                    total_provider_cost,
            },
        }


agent_runtime = AgentRuntime()

