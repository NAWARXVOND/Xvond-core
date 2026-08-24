from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin

from backend.app.models.company import Company
from backend.app.models.user import User

from backend.app.modules.ai_agent.models import (
    AIAgent,
    AIConversation,
    AIMessage,
    AIUsage,
)

from backend.app.modules.billing.models import (
    Plan,
    Subscription,
)


router = APIRouter(
    prefix="/admin/operations",
    tags=["Xvond Admin - Operations"],
)


def get_company_or_404(
    db,
    company_id: int,
):
    company = (
        db.query(Company)
        .filter(
            Company.id == company_id
        )
        .first()
    )

    if company is None:
        raise HTTPException(
            status_code=404,
            detail="Company not found",
        )

    return company


@router.get(
    "/companies/{company_id}/usage"
)
def company_usage(
    company_id: int,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:
        get_company_or_404(
            db,
            company_id,
        )

        summary = (
            db.query(
                func.count(AIUsage.id),
                func.coalesce(
                    func.sum(
                        AIUsage.input_tokens
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        AIUsage.output_tokens
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        AIUsage.total_tokens
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        AIUsage.provider_cost
                    ),
                    0,
                ),
            )
            .filter(
                AIUsage.company_id
                == company_id
            )
            .first()
        )

        items = (
            db.query(AIUsage)
            .filter(
                AIUsage.company_id
                == company_id
            )
            .order_by(
                AIUsage.id.desc()
            )
            .limit(500)
            .all()
        )

        return {
            "company_id": company_id,

            "summary": {
                "requests": summary[0],
                "input_tokens": summary[1],
                "output_tokens": summary[2],
                "total_tokens": summary[3],
                "provider_cost": summary[4],
            },

            "usage": [
                {
                    "id": item.id,
                    "agent_id": item.agent_id,
                    "provider": item.provider,
                    "model": item.model,
                    "input_tokens": item.input_tokens,
                    "output_tokens": item.output_tokens,
                    "total_tokens": item.total_tokens,
                    "provider_cost": item.provider_cost,
                    "created_at": item.created_at,
                }
                for item in items
            ],
        }

    finally:
        db.close()


@router.get(
    "/companies/{company_id}/conversations"
)
def company_conversations(
    company_id: int,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:
        get_company_or_404(
            db,
            company_id,
        )

        items = (
            db.query(AIConversation)
            .filter(
                AIConversation.company_id
                == company_id
            )
            .order_by(
                AIConversation.id.desc()
            )
            .limit(500)
            .all()
        )

        return {
            "company_id": company_id,

            "conversations": [
                {
                    "id": item.id,
                    "agent_id": item.agent_id,
                    "title": item.title,
                    "created_at": item.created_at,
                }
                for item in items
            ],
        }

    finally:
        db.close()


@router.get(
    "/companies/{company_id}/conversations/{conversation_id}"
)
def conversation_messages(
    company_id: int,
    conversation_id: int,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:
        conversation = (
            db.query(AIConversation)
            .filter(
                AIConversation.id
                == conversation_id,

                AIConversation.company_id
                == company_id,
            )
            .first()
        )

        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found",
            )

        messages = (
            db.query(AIMessage)
            .filter(
                AIMessage.conversation_id
                == conversation.id
            )
            .order_by(
                AIMessage.id.asc()
            )
            .all()
        )

        return {
            "conversation": {
                "id": conversation.id,
                "agent_id": conversation.agent_id,
                "title": conversation.title,
                "created_at": conversation.created_at,
            },

            "messages": [
                {
                    "id": item.id,
                    "role": item.role,
                    "content": item.content,
                    "created_at": item.created_at,
                }
                for item in messages
            ],
        }

    finally:
        db.close()


@router.get(
    "/subscriptions"
)
def subscriptions(
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:
        rows = (
            db.query(
                Subscription,
                Company,
                Plan,
            )
            .join(
                Company,
                Company.id
                == Subscription.company_id,
            )
            .join(
                Plan,
                Plan.id
                == Subscription.plan_id,
            )
            .order_by(
                Subscription.id.desc()
            )
            .all()
        )

        return {
            "subscriptions": [
                {
                    "id": subscription.id,
                    "company_id": company.id,
                    "company_name": company.name,
                    "plan_id": plan.id,
                    "plan_name": plan.name,
                    "price": plan.price,
                    "status": subscription.status,
                    "started_at": subscription.started_at,
                }
                for subscription, company, plan
                in rows
            ]
        }

    finally:
        db.close()
