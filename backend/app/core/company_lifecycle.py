from backend.app.core.readiness import company_readiness
from backend.app.models.company import Company
from backend.app.modules.ai_agent.models import AIAgent


class CompanyLifecycleError(Exception):
    pass


class CompanyNotFound(CompanyLifecycleError):
    pass


class CompanyNotReady(CompanyLifecycleError):
    def __init__(self, readiness: dict):
        super().__init__("Company is not ready to activate")
        self.readiness = readiness


def get_company(db, company_id: int) -> Company:
    company = db.query(Company).filter(Company.id == company_id).first()
    if company is None:
        raise CompanyNotFound("Company not found")
    return company


def activate_company(db, company_id: int) -> tuple[Company, dict]:
    """Activate a company only after canonical setup readiness passes.

    This transition intentionally does not enable AI employees. Employee Go Live
    remains owned by Delivery Readiness so company activation cannot bypass
    employee, package or channel gates.
    """
    company = get_company(db, company_id)
    readiness = company_readiness(db, company_id)
    if readiness is None:
        raise CompanyNotFound("Company not found")
    if not readiness["ready"]:
        raise CompanyNotReady(readiness)
    company.active = True
    return company, readiness


def deactivate_company(db, company_id: int) -> Company:
    """Emergency-stop a company and every AI employee in the tenant."""
    company = get_company(db, company_id)
    company.active = False
    (
        db.query(AIAgent)
        .filter(AIAgent.company_id == company_id)
        .update({AIAgent.enabled: False}, synchronize_session=False)
    )
    return company
