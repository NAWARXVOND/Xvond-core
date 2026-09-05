from backend.app.api.admin_ai_employee_profile import EmployeeProfileUpdate, _profile_prompt
from backend.app.modules.knowledge.service import KnowledgeMatch, KnowledgeService


def test_contact_intent_understands_human_contact_language():
    service = KnowledgeService()
    for query in (
        "بدي اتواصل مع المسؤول",
        "بدي احكي مع موظف",
        "ممكن رقم فريق المبيعات",
        "I want to speak to a representative",
    ):
        assert "contact" in service.detect_intents(query)


def test_knowledge_source_priority_is_core_then_curated_then_imports():
    service = KnowledgeService()
    assert service._source_priority_boost("business_profile") > service._source_priority_boost("general")
    assert service._source_priority_boost("general") > service._source_priority_boost("pdf")
    assert service._source_priority_boost("pdf") > service._source_priority_boost("website")


def test_agent_context_combines_core_and_multiple_supplementary_sources(monkeypatch):
    service = KnowledgeService()
    monkeypatch.setattr(service, "backfill_company_index", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(
        service,
        "_core_business_information",
        lambda *_args, **_kwargs: ("Business Name: Xvond\nPhone: 9111 8075", 1),
    )
    monkeypatch.setattr(
        service,
        "search_agent_knowledge",
        lambda *_args, **_kwargs: [
            KnowledgeMatch(1, "Business Information", "business_profile", 0, "duplicate core", 100),
            KnowledgeMatch(2, "Manual Services", "general", 0, "Curated service detail", 80),
            KnowledgeMatch(3, "Services.pdf", "pdf", 0, "PDF service detail", 70),
            KnowledgeMatch(4, "Website", "website", 0, "Website service detail", 60),
        ],
    )

    context = service.get_agent_context(object(), 1, 1, "شو خدماتكم")

    assert "CORE COMPANY INFORMATION" in context
    assert "9111 8075" in context
    assert "Curated service detail" in context
    assert "PDF service detail" in context
    assert "Website service detail" in context
    assert "duplicate core" not in context


def test_employee_prompt_forbids_unconfigured_operations_and_unnecessary_forms():
    prompt = _profile_prompt(
        "Xvond",
        EmployeeProfileUpdate(name="Xvond", reply_language="auto", dialect="auto"),
    )
    assert "CAPABILITY BOUNDARY" in prompt
    assert "not available" in prompt
    assert "do not collect customer fields" in prompt
    assert "give the relevant verified contact detail directly" in prompt
    assert "PDFs and website content" in prompt
