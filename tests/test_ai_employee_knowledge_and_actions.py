from backend.app.core.agent_runtime import GROUNDING_POLICY
from backend.app.modules.knowledge.service import KnowledgeService
from backend.app.modules.tools.builtin import _fact_tokens, _valid_iso_date, _valid_iso_time


def test_grounding_policy_prevents_unsolicited_catalog_dump():
    policy = GROUNDING_POLICY.lower()
    assert "greeting" in policy
    assert "do not advertise" in policy
    assert "incomplete or ambiguous" in policy
    assert "do not invent" in policy


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


def test_business_fact_tokens_handle_arabic_definite_article():
    assert "شعر" in _fact_tokens("قص الشعر")
    assert "قص" in _fact_tokens("قص شعر")


def test_booking_date_and_time_require_iso_values():
    assert _valid_iso_date("2026-08-25") is True
    assert _valid_iso_date("25/08/2026") is False
    assert _valid_iso_time("17:30") is True
    assert _valid_iso_time("5:30 PM") is False
