from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CUSTOMER_MANAGEMENT = ROOT / "backend" / "app" / "api" / "customer_management.py"
CUSTOMER_AGENTS = ROOT / "backend" / "app" / "api" / "customer_agents.py"
MANAGER_KNOWLEDGE_UI = ROOT / "frontend" / "customer" / "manager-knowledge-controls.js"
PORTAL_HTML = ROOT / "frontend" / "customer" / "index.html"


def test_customer_management_is_manager_only_and_company_scoped_from_session():
    source = CUSTOMER_MANAGEMENT.read_text(encoding="utf-8")
    assert "Depends(require_customer_manager)" in source
    assert source.count("Depends(require_customer_manager)") >= 9
    assert "return user.company_id" in source
    assert "company_id=_company_id(current_user)" in source
    assert "company_id:" not in source.split("def customer_business_information", 1)[1].split("):", 1)[0]


def test_customer_business_information_reuses_canonical_company_profile_sync():
    source = CUSTOMER_MANAGEMENT.read_text(encoding="utf-8")
    assert "get_company_profile" in source
    assert "update_company_profile" in source
    assert 'router = APIRouter(prefix="/manage"' in source


def test_customer_knowledge_reuses_existing_secure_knowledge_pipeline():
    source = CUSTOMER_MANAGEMENT.read_text(encoding="utf-8")
    assert "create_employee_knowledge" in source
    assert "update_employee_knowledge" in source
    assert "toggle_employee_knowledge" in source
    assert "delete_employee_knowledge" in source
    assert "ingest_website_knowledge" in source
    assert "upload_pdf_knowledge" in source


def test_customer_management_router_is_nested_under_registered_customer_agents_router():
    source = CUSTOMER_AGENTS.read_text(encoding="utf-8")
    assert "from backend.app.api.customer_management import router as customer_management_router" in source
    assert "router.include_router(customer_management_router)" in source


def test_manager_ui_exposes_behavior_business_and_knowledge_without_provider_controls():
    source = MANAGER_KNOWLEDGE_UI.read_text(encoding="utf-8")
    assert 'managerTabButton("Behavior", "behavior")' in source
    assert 'managerTabButton("Business Information", "business")' in source
    assert 'managerTabButton("Knowledge", "knowledge")' in source
    assert "/customer/agents/manage/business-information" in source
    assert "/knowledge/url" in source
    assert "/knowledge/pdf" in source
    assert "provider" not in source.lower()
    assert "model" not in source.lower()


def test_manager_knowledge_ui_loads_after_base_manager_controls_before_session_start():
    html = PORTAL_HTML.read_text(encoding="utf-8")
    base = html.index("/static/customer/manager-controls.js")
    knowledge = html.index("/static/customer/manager-knowledge-controls.js")
    session = html.index("/static/customer/session-security.js")
    assert base < knowledge < session
