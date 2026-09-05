from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.app.api.admin_ai_employee_files import upload_pdf_knowledge
from backend.app.api.admin_ai_employee_knowledge import (
    KnowledgeCreate,
    KnowledgeUpdate,
    WebsiteKnowledgeCreate,
    create_employee_knowledge,
    delete_employee_knowledge,
    get_employee_knowledge,
    ingest_website_knowledge,
    list_employee_knowledge,
    toggle_employee_knowledge,
    update_employee_knowledge,
)
from backend.app.api.admin_company_profile import (
    CompanyProfileUpdate,
    get_company_profile,
    update_company_profile,
)
from backend.app.core.dependencies import require_customer_manager
from backend.app.models.user import User

router = APIRouter(prefix="/customer/manage", tags=["Customer Manager Controls"])


def _company_id(user: User) -> int:
    if user.company_id is None:
        raise HTTPException(403, "Customer company required")
    return user.company_id


@router.get("/business-information")
def customer_business_information(
    current_user: User = Depends(require_customer_manager),
):
    return get_company_profile(
        company_id=_company_id(current_user),
        current_admin=current_user,
    )


@router.put("/business-information")
def update_customer_business_information(
    payload: CompanyProfileUpdate,
    current_user: User = Depends(require_customer_manager),
):
    return update_company_profile(
        company_id=_company_id(current_user),
        data=payload,
        current_admin=current_user,
    )


@router.get("/agents/{agent_id}/knowledge")
def customer_knowledge_list(
    agent_id: int,
    current_user: User = Depends(require_customer_manager),
):
    return list_employee_knowledge(
        company_id=_company_id(current_user),
        agent_id=agent_id,
        current_admin=current_user,
    )


@router.get("/agents/{agent_id}/knowledge/{document_id}")
def customer_knowledge_item(
    agent_id: int,
    document_id: int,
    current_user: User = Depends(require_customer_manager),
):
    return get_employee_knowledge(
        company_id=_company_id(current_user),
        agent_id=agent_id,
        document_id=document_id,
        current_admin=current_user,
    )


@router.post("/agents/{agent_id}/knowledge")
def customer_knowledge_create(
    agent_id: int,
    payload: KnowledgeCreate,
    current_user: User = Depends(require_customer_manager),
):
    return create_employee_knowledge(
        company_id=_company_id(current_user),
        agent_id=agent_id,
        payload=payload,
        current_admin=current_user,
    )


@router.post("/agents/{agent_id}/knowledge/url")
def customer_knowledge_url(
    agent_id: int,
    payload: WebsiteKnowledgeCreate,
    current_user: User = Depends(require_customer_manager),
):
    return ingest_website_knowledge(
        company_id=_company_id(current_user),
        agent_id=agent_id,
        payload=payload,
        current_admin=current_user,
    )


@router.post("/agents/{agent_id}/knowledge/pdf")
async def customer_knowledge_pdf(
    agent_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(require_customer_manager),
):
    return await upload_pdf_knowledge(
        company_id=_company_id(current_user),
        agent_id=agent_id,
        file=file,
        current_admin=current_user,
    )


@router.put("/agents/{agent_id}/knowledge/{document_id}")
def customer_knowledge_update(
    agent_id: int,
    document_id: int,
    payload: KnowledgeUpdate,
    current_user: User = Depends(require_customer_manager),
):
    return update_employee_knowledge(
        company_id=_company_id(current_user),
        agent_id=agent_id,
        document_id=document_id,
        payload=payload,
        current_admin=current_user,
    )


@router.patch("/agents/{agent_id}/knowledge/{document_id}/toggle")
def customer_knowledge_toggle(
    agent_id: int,
    document_id: int,
    current_user: User = Depends(require_customer_manager),
):
    return toggle_employee_knowledge(
        company_id=_company_id(current_user),
        agent_id=agent_id,
        document_id=document_id,
        current_admin=current_user,
    )


@router.delete("/agents/{agent_id}/knowledge/{document_id}")
def customer_knowledge_delete(
    agent_id: int,
    document_id: int,
    current_user: User = Depends(require_customer_manager),
):
    return delete_employee_knowledge(
        company_id=_company_id(current_user),
        agent_id=agent_id,
        document_id=document_id,
        current_admin=current_user,
    )
