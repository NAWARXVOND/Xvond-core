from types import SimpleNamespace

from backend.app.core.agent_runtime import GROUNDING_POLICY
from backend.app.core.config.settings import settings
from backend.app.modules.knowledge.embeddings import KnowledgeEmbeddingClient
from backend.app.modules.knowledge.service import KnowledgeService
from backend.app.modules.tools.builtin import _fact_tokens, _valid_iso_date, _valid_iso_time


def test_grounding_policy_prevents_unsolicited_catalog_dump():
    policy = GROUNDING_POLICY.lower()
    assert "greeting" in policy
    assert "advertise" in policy
    assert "incomplete or ambiguous" in policy
    assert "never invent" in policy


def test_knowledge_intent_routing_for_prices_and_booking():
    service = KnowledgeService()
    price_intents = service.detect_intents("شو أسعار الخدمات؟")
    booking_intents = service.detect_intents("بدي احجز موعد")
    assert "price" in price_intents
    assert "services" in price_intents
    assert "booking" in booking_intents
    assert "services_prices" in service.INTENT_CATEGORY_HINTS["price"]
    assert "booking_rules" in service.INTENT_CATEGORY_HINTS["booking"]


def test_knowledge_intent_routing_for_orders_and_delivery():
    service = KnowledgeService()
    intents = service.detect_intents("بدي اطلب مع توصيل وبطاقة")
    assert "order" in intents
    assert "delivery_payment" in intents


def test_knowledge_stop_words_do_not_drive_retrieval():
    service = KnowledgeService()
    assert service.tokenize("شو في عندكم") == set()
    assert "اسعار" in service.tokenize("شو اسعاركم")


def test_generic_business_document_does_not_match_unrelated_chunk():
    service = KnowledgeService()
    chunk = SimpleNamespace(
        normalized_text=service.normalize("نقدم القهوة العربية والتمر"),
        content="نقدم القهوة العربية والتمر",
    )
    document = SimpleNamespace(title="Business Information", source_type="business_profile")
    assert service._score_match("كم سعر تنظيف البشرة؟", chunk, document) is None


def test_exact_phrase_scores_above_loose_token_overlap():
    service = KnowledgeService()
    exact_chunk = SimpleNamespace(
        normalized_text=service.normalize("سعر تنظيف البشرة 20 ريال"),
        content="سعر تنظيف البشرة 20 ريال",
    )
    loose_chunk = SimpleNamespace(
        normalized_text=service.normalize("تنظيف عام وخدمات للعناية بالبشرة"),
        content="تنظيف عام وخدمات للعناية بالبشرة",
    )
    document = SimpleNamespace(title="الخدمات والأسعار", source_type="services_prices")
    exact_score = service._score_match("سعر تنظيف البشرة", exact_chunk, document)
    loose_score = service._score_match("سعر تنظيف البشرة", loose_chunk, document)
    assert exact_score is not None
    assert loose_score is not None
    assert exact_score > loose_score


def test_semantic_cosine_similarity_is_real_vector_math():
    client = KnowledgeEmbeddingClient()
    assert client.cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert client.cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert client.cosine_similarity([1.0], [1.0, 0.0]) is None


def test_semantic_embedding_text_redacts_pii_when_enabled(monkeypatch):
    client = KnowledgeEmbeddingClient()
    monkeypatch.setattr(settings, "AI_PII_REDACTION_ENABLED", True)
    prepared = client._prepare_text("Call +968 9123 4567 or a@example.com")
    assert "+968 9123 4567" not in prepared
    assert "a@example.com" not in prepared
    assert "XVOND_PHONE" in prepared
    assert "XVOND_EMAIL" in prepared


def test_embedding_current_requires_same_provider_and_model():
    service = KnowledgeService()
    chunk = SimpleNamespace(
        embedding=[0.1, 0.2],
        embedding_provider="openai",
        embedding_model=settings.KNOWLEDGE_EMBEDDING_MODEL,
    )
    assert service._embedding_is_current(chunk) is True
    chunk.embedding_model = "old-embedding-model"
    assert service._embedding_is_current(chunk) is False


def test_business_fact_tokens_handle_arabic_definite_article():
    assert "شعر" in _fact_tokens("قص الشعر")
    assert "قص" in _fact_tokens("قص شعر")


def test_booking_date_and_time_require_iso_values():
    assert _valid_iso_date("2026-08-25") is True
    assert _valid_iso_date("25/08/2026") is False
    assert _valid_iso_time("17:30") is True
    assert _valid_iso_time("5:30 PM") is False
