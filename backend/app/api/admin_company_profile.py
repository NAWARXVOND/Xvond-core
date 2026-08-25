import json
import re
from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.company_catalog import (
    company_catalog,
    normalize_business_type,
    normalize_country,
    normalize_currency,
    normalize_language,
    normalize_languages,
    normalize_timezone,
)
from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.company import Company
from backend.app.models.company_profile import CompanyProfile
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.ai_agent.profile_models import AIAgentProfile
from backend.app.modules.knowledge.models import (
    AgentKnowledge,
    KnowledgeChunk,
    KnowledgeDocument,
)
from backend.app.modules.knowledge.service import knowledge_service

router = APIRouter(
    prefix="/admin/company-profile",
    tags=["Xvond Admin - Company Profile"],
)

DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


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


def _clean_list(values, *, max_items: int = 500):
    result = []
    for value in values or []:
        if isinstance(value, str):
            item = value.strip()
            if item and item not in result:
                result.append(item)
        elif value not in (None, "", {}, []):
            result.append(value)
        if len(result) >= max_items:
            break
    return result


def _validate_email(value: str | None) -> str | None:
    value = _clean(value)
    if value and not EMAIL_RE.fullmatch(value):
        raise ValueError("Invalid company email")
    return value


def _validate_website(value: str | None) -> str | None:
    value = _clean(value)
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Company website must be a valid http(s) URL")
    if parsed.username or parsed.password:
        raise ValueError("Company website must not contain embedded credentials")
    return value.rstrip("/")


def _validate_working_hours(value: dict | None) -> dict:
    if not value:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Working hours must be an object")

    result = {}
    unknown = set(value) - set(DAY_KEYS)
    if unknown:
        raise ValueError("Working hours contain unsupported day keys")

    for day in DAY_KEYS:
        row = value.get(day)
        if row in (None, {}):
            continue
        if not isinstance(row, dict):
            raise ValueError(f"Working hours for {day} are invalid")
        enabled = bool(row.get("enabled", True))
        if not enabled:
            result[day] = {"enabled": False}
            continue
        start = str(row.get("start") or "").strip()
        end = str(row.get("end") or "").strip()
        if not start or not end:
            raise ValueError(f"Working hours for {day} require start and end")
        try:
            start_time = datetime.strptime(start, "%H:%M")
            end_time = datetime.strptime(end, "%H:%M")
        except ValueError as exc:
            raise ValueError(
                f"Working hours for {day} must use HH:MM"
            ) from exc
        if end_time <= start_time:
            raise ValueError(
                f"Working hours for {day} must end after they start"
            )
        result[day] = {"enabled": True, "start": start, "end": end}
    return result


def _normalize_profile(data: CompanyProfileUpdate) -> dict:
    primary_language = normalize_language(data.primary_language)
    additional_languages = normalize_languages(data.additional_languages)
    if primary_language:
        additional_languages = [
            item for item in additional_languages if item != primary_language
        ]

    return {
        "business_type": normalize_business_type(data.business_type),
        "description": _clean(data.description),
        "country": normalize_country(data.country),
        "currency": normalize_currency(data.currency),
        "timezone": normalize_timezone(data.timezone),
        "primary_language": primary_language,
        "additional_languages": additional_languages,
        "phone": _clean(data.phone),
        "email": _validate_email(data.email),
        "website": _validate_website(data.website),
        "working_hours": _validate_working_hours(data.working_hours),
        "locations": _clean_list(data.locations),
        "services": _clean_list(data.services),
        "service_areas": _clean_list(data.service_areas),
        "policies": _clean_list(data.policies),
        "business_rules": _clean_list(data.business_rules),
    }


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
        "catalog": company_catalog(),
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
        blocks.append(
            "Additional Languages: " + ", ".join(row.additional_languages)
        )

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
            blocks.append(
                f"{label}:\n{json.dumps(value, ensure_ascii=False, indent=2)}"
            )
    return "\n\n".join(blocks).strip()


def _remove_legacy_company_knowledge(
    db, company_id: int, canonical_document_id: int
) -> None:
    legacy_documents = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.company_id == company_id,
            KnowledgeDocument.id != canonical_document_id,
            KnowledgeDocument.title.in_(("Business Profile", "Business Website")),
        )
        .all()
    )

    for legacy in legacy_documents:
        db.query(AgentKnowledge).filter(
            AgentKnowledge.document_id == legacy.id,
        ).delete(synchronize_session=False)
        db.query(KnowledgeChunk).filter(
            KnowledgeChunk.document_id == legacy.id,
        ).delete(synchronize_session=False)
        db.delete(legacy)


def sync_company_business_knowledge(
    db, company: Company, row: CompanyProfile
) -> KnowledgeDocument:
    document = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.company_id == company.id,
            KnowledgeDocument.source_type == "business_profile",
            KnowledgeDocument.title == "Business Information",
        )
        .first()
    )
    content = _business_knowledge_content(company, row)
    if document is None:
        document = KnowledgeDocument(
            company_id=company.id,
            title="Business Information",
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
            db.add(
                AgentKnowledge(
                    agent_id=agent.id,
                    document_id=document.id,
                    enabled=True,
                )
            )
        else:
            assignment.enabled = True

    _remove_legacy_company_knowledge(db, company.id, document.id)
    db.flush()
    return document


@router.get("/{company_id}")
def get_company_profile(
    company_id: int,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if company is None:
            raise HTTPException(404, "Company not found")
        row = (
            db.query(CompanyProfile)
            .filter(CompanyProfile.company_id == company_id)
            .first()
        )
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
        if len(company_name) > 255:
            raise HTTPException(400, "Company name is too long")

        try:
            normalized = _normalize_profile(data)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

        company.name = company_name
        row = (
            db.query(CompanyProfile)
            .filter(CompanyProfile.company_id == company_id)
            .first()
        )
        if row is None:
            row = CompanyProfile(company_id=company_id)
            db.add(row)

        for key, value in normalized.items():
            setattr(row, key, value)
        db.flush()

        profiles = (
            db.query(AIAgentProfile)
            .filter(AIAgentProfile.company_id == company_id)
            .all()
        )
        for profile in profiles:
            profile.business_name = company.name
            profile.business_type = row.business_type

        document = sync_company_business_knowledge(db, company, row)
        db.commit()
        result = _serialize(company, row)
        result.update(
            {
                "status": "updated",
                "knowledge_document_id": document.id,
            }
        )
        return result
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
