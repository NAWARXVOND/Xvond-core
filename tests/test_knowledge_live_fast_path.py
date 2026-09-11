from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def test_live_knowledge_backfill_is_throttled():
    code = source("backend/app/modules/knowledge/service.py")
    assert "LIVE_BACKFILL_TTL_SECONDS = 300.0" in code
    assert "def _backfill_live_if_due" in code
    assert "self._backfill_live_if_due(db, company_id)" in code


def test_company_backfill_avoids_per_document_existence_query():
    code = source("backend/app/modules/knowledge/service.py")
    assert "existing_document_ids" in code
    assert ".distinct()" in code
    assert "missing_docs = [doc for doc in docs if doc.id not in existing_document_ids]" in code


def test_trivial_chat_skips_full_knowledge_scan_but_keeps_core_profile():
    code = source("backend/app/modules/knowledge/service.py")
    assert "trivial_query = not knowledge_embedding_client._should_embed_query" in code
    assert "matches = [] if trivial_query else self.search_agent_knowledge" in code
    assert "core, core_document_id = self._core_business_information" in code
