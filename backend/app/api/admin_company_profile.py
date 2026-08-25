import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.company import Company
from backend.app.models.company_profile import CompanyProfile
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.ai_agent.profile_models import AIAgentProfile
from backend.app.modules.knowledge.models import AgentKnowledge, KnowledgeDocument
from backend.app.modules.knowledge.service import knowledge_service

router = APIRouter(prefix="/admin/company-profile", tags=["Xvond Admin - Company Profile"])


class CompanyProfileUpdate(BaseModel):
    company_name: str
    business_type: str | None = None
    description: str | None = None
    country: str | None = None
    currency: str | None = None
    timezone: str | None = None
    primary_language: str | None = None
    additional_languages: list[str] = Field(default_factory=list)
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    working_hours: dict = Field(default_factory=dict)
    locations: list = Field(default_factory=list)
    services: list = Field(default_factory=list)
    service_areas: list = Field(default_factory=list)
    policies: list = Field(default_factory=list)
    business_rules: list = Field(default_factory=list)


def _clean(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_list(values):
    result = []
    for value in values or []:
        if isinstance(value, str):
            item = value.strip()
            if item and item not in result:
                result.append(item)
        elif value not in (None, "", {}, []):
            result.append(value)
    return result


def _serialize(company: Company, row: CompanyProfile | None) -> dict:
    return {
        "company_id": company.id,
        "company_name": company.name,
        "active": company.active,
        "business_type": row.business_type if row else None,
        "description": row.description if row else None,
        "country": row.country if row else None,
        "currency": row.currency if row else None,
        "timezone": row.timezone if row else None,
        "primary_language": row.primary_language if row else None,
        "additional_languages": list(row.additional_languages or []) if row else [],
        "phone": row.phone if row else None,
        "email": row.email if row else None,
        "website": row.website if row else None,
        "working_hours": dict(row.working_hours or {}) if row else {},
        "locations": list(row.locations or []) if row else [],
        "services": list(row.services or []) if row else [],
        "service_areas": list(row.service_areas or []) if row else [],
        "policies": list(row.policies or []) if row else [],
        "business_rules": list(row.business_rules or []) if row else [],
    }


def _business_knowledge_content(company: Company, row: CompanyProfile) -> str:
    blocks = [f"Business Name: {company.name}"]
    scalar = [
        ("Business Type", row.business_type),
        ("Description", row.description),
        ("Country", row.country),
        ("Currency", row.currency),
        ("Timezone", row.timezone),
        ("Primary Language", row.primary_language),
        ("Phone", row.phone),
        ("Email", row.email),
        ("Website", row.website),
    ]
    for label, value in scalar:
        if value:
            blocks.append(f"{label}: {value}")
    if row.additional_languages:
        blocks.append("Additional Languages: " + ", ".join(row.additional_languages))

    structured = [
        ("Working Hours", row.working_hours),
        ("Locations / Branches", row.locations),
        ("Services", row.services),
        ("Service Areas", row.service_areas),
        ("Policies", row.policies),
        ("Business Rules", row.business_rules),
    ]
    for label, value in structured:
        if value:
            blocks.append(f"{label}:\n{json.dumps(value, ensure_ascii=False, indent=2)}")
    return "\n\n".join(blocks).strip()


def sync_company_business_knowledge(db, company: Company, row: CompanyProfile) -> KnowledgeDocument:
    document = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.company_id == company.id,
            KnowledgeDocument.source_type == "business_profile",
            KnowledgeDocument.title == "Company Business Information",
        )
        .first()
    )
    content = _business_knowledge_content(company, row)
    if document is None:
        document = KnowledgeDocument(
            company_id=company.id,
            title="Company Business Information",
            source_type="business_profile",
            content=content,
            enabled=True,
        )
        db.add(document)
        db.flush()
    else:
        document.content = content
        document.enabled = True
        db.flush()

    knowledge_service.rebuild_document_index(db, document)
    agents = db.query(AIAgent).filter(AIAgent.company_id == company.id).all()
    for agent in agents:
        assignment = (
            db.query(AgentKnowledge)
            .filter(
                AgentKnowledge.agent_id == agent.id,
                AgentKnowledge.document_id == document.id,
            )
            .first()
        )
        if assignment is None:
            db.add(AgentKnowledge(agent_id=agent.id, document_id=document.id, enabled=True))
        else:
            assignment.enabled = True
    db.flush()
    return document


@router.get("/{company_id}")
def get_company_profile(company_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if company is None:
            raise HTTPException(404, "Company not found")
        row = db.query(CompanyProfile).filter(CompanyProfile.company_id == company_id).first()
        return _serialize(company, row)
    finally:
        db.close()


@router.put("/{company_id}")
def update_company_profile(
    company_id: int,
    data: CompanyProfileUpdate,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if company is None:
            raise HTTPException(404, "Company not found")

        company_name = _clean(data.company_name)
        if not company_name:
            raise HTTPException(400, "Company name is required")
        company.name = company_name

        row = db.query(CompanyProfile).filter(CompanyProfile.company_id == company_id).first()
        if row is None:
            row = CompanyProfile(company_id=company_id)
            db.add(row)

        row.business_type = _clean(data.business_type)
        row.description = _clean(data.description)
        row.country = _clean(data.country)
        row.currency = _clean(data.currency)
        row.timezone = _clean(data.timezone)
        row.primary_language = _clean(data.primary_language)
        row.additional_languages = _clean_list(data.additional_languages)
        row.phone = _clean(data.phone)
        row.email = _clean(data.email)
        row.website = _clean(data.website)
        row.working_hours = dict(data.working_hours or {})
        row.locations = _clean_list(data.locations)
        row.services = _clean_list(data.services)
        row.service_areas = _clean_list(data.service_areas)
        row.policies = _clean_list(data.policies)
        row.business_rules = _clean_list(data.business_rules)
        db.flush()

        # Company identity is authoritative. Existing employee profiles inherit it.
        profiles = db.query(AIAgentProfile).filter(AIAgentProfile.company_id == company_id).all()
        for profile in profiles:
            profile.business_name = company.name
            profile.business_type = row.business_type

        document = sync_company_business_knowledge(db, company, row)
        db.commit()
        result = _serialize(company, row)
        result.update({"status": "updated", "knowledge_document_id": document.id})
        return result
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
