from datetime import UTC, datetime

from backend.app.core.readiness import company_readiness
from backend.app.models.company import Company
from backend.app.modules.ai_agent.models import AIAgent


COMPANY_LIFECYCLE_STATUSES = {
    "onboarding",
    "testing",
    "live",
    "paused",
    "suspended",
    "cancelled",
    "archived",
}
PORTAL_BLOCKED_STATUSES = {"suspended", "cancelled", "archived"}


class CompanyLifecycleError(Exception):
    pass


class CompanyNotFound(CompanyLifecycleError):
    pass


class CompanyNotReady(CompanyLifecycleError):
    def __init__(self, readiness: dict):
        super().__init__("Company is not ready to activate")
        self.readiness = readiness


class InvalidCompanyLifecycle(CompanyLifecycleError):
    pass


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def get_company(db, company_id: int) -> Company:
    company = db.query(Company).filter(Company.id == company_id).first()
    if company is None:
        raise CompanyNotFound("Company not found")
    return company


def portal_access_allowed(company: Company) -> bool:
    return str(company.lifecycle_status or "onboarding").lower() not in PORTAL_BLOCKED_STATUSES


def set_company_lifecycle(db, company_id: int, status: str) -> tuple[Company, dict | None]:
    """Transition the commercial/customer lifecycle without conflating it with AI state.

    Onboarding/testing customers may access their portal while AI runtime remains off.
    Paused customers retain their configured employee state for a safe resume. Suspended,
    cancelled and archived customers cannot sign in. Going live is readiness-gated.
    """
    normalized = str(status or "").strip().lower()
    if normalized not in COMPANY_LIFECYCLE_STATUSES:
        raise InvalidCompanyLifecycle("Unsupported company lifecycle status")

    company = get_company(db, company_id)
    readiness = None
    if normalized == "live":
        readiness = company_readiness(db, company_id)
        if readiness is None:
            raise CompanyNotFound("Company not found")
        if not readiness["ready"]:
            raise CompanyNotReady(readiness)
        company.active = True
    elif normalized in {"onboarding", "testing", "paused", "suspended", "cancelled", "archived"}:
        company.active = False

    company.lifecycle_status = normalized
    company.lifecycle_updated_at = _utcnow_naive()
    return company, readiness


def activate_company(db, company_id: int) -> tuple[Company, dict]:
    company, readiness = set_company_lifecycle(db, company_id, "live")
    return company, readiness or {}


def deactivate_company(db, company_id: int) -> Company:
    """Emergency-stop runtime and every AI employee without changing commercial state."""
    company = get_company(db, company_id)
    company.active = False
    (
        db.query(AIAgent)
        .filter(AIAgent.company_id == company_id)
        .update({AIAgent.enabled: False}, synchronize_session=False)
    )
    return company
