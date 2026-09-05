from types import SimpleNamespace

from backend.app.modules.knowledge.service import KnowledgeService


def _chunk(text):
    return SimpleNamespace(normalized_text=text, content=text)


def _document(source_type, title="Xvond Services"):
    return SimpleNamespace(source_type=source_type, title=title)


def test_levantine_attached_l_prefix_matches_services():
    service = KnowledgeService()
    tokens = service.tokenize("شو لخدمات")
    assert "خدمات" in tokens
    assert "services" in tokens


def test_possessive_services_form_matches_services():
    service = KnowledgeService()
    tokens = service.tokenize("شو خدماتكن")
    assert "خدمات" in tokens


def test_pdf_gets_services_intent_boost():
    service = KnowledgeService()
    score = service._score_match(
        "شو لخدمات",
        _chunk("نقدم حلول الذكاء الاصطناعي والأتمتة والمواقع والتطبيقات"),
        _document("pdf"),
    )
    assert score is not None
    assert score > 0


def test_website_gets_services_intent_boost():
    service = KnowledgeService()
    score = service._score_match(
        "شو بتقدمو",
        _chunk("Xvond تقدم خدمات الذكاء الاصطناعي للأعمال"),
        _document("website"),
    )
    assert score is not None
    assert score > 0


def test_contact_intent_matches_pdf_contact_information():
    service = KnowledgeService()
    score = service._score_match(
        "كيف فيني اتواصل معكن",
        _chunk("الهاتف 9111 8075 البريد الإلكتروني support@xvond.com"),
        _document("pdf", title="Xvond Contact"),
    )
    assert "contact" in service.detect_intents("كيف فيني اتواصل معكن")
    assert score is not None
    assert score > 0
