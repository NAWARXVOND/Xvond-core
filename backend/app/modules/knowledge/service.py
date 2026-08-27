import re
from dataclasses import dataclass

from backend.app.modules.knowledge.models import AgentKnowledge, KnowledgeChunk, KnowledgeDocument


@dataclass
class KnowledgeMatch:
    document_id: int
    title: str
    source_type: str
    chunk_index: int
    content: str
    score: float


class KnowledgeService:
    DEFAULT_CHUNK_SIZE = 1400
    DEFAULT_OVERLAP = 180
    DEFAULT_MAX_CHUNKS = 7
    DEFAULT_MAX_CONTEXT_CHARS = 8500
    MAX_CHUNKS_PER_DOCUMENT = 3

    STOP_WORDS = {
        "the", "a", "an", "is", "are", "do", "does", "what", "how", "can", "i", "we", "you",
        "في", "من", "على", "عن", "الى", "الي", "هل", "شو", "ايش", "وش", "ما", "هو", "هي", "هذا", "هذه",
        "عند", "عندكم", "لو", "اذا", "بدي", "ابي", "اريد", "ممكن", "فيه", "فيها", "فيكم", "فيكن",
    }

    ARABIC_EQUIVALENTS = {
        "اسعار": {"السعر", "سعر", "الاسعار", "أسعار", "الأسعار", "بكم", "تكلفة", "تكلفه", "ثمن"},
        "خدمات": {"خدمة", "الخدمات", "خدمات", "بتعملو", "تقدمون", "عندكم"},
        "حجز": {"موعد", "مواعيد", "احجز", "الحجز", "حجز", "احجزلي", "موعدي"},
        "دوام": {"ساعات", "الدوام", "دوام", "مفتوح", "تفتحون", "تسكرون", "اغلاق", "إغلاق"},
        "موقع": {"العنوان", "عنوان", "وين", "الموقع", "موقع", "فرع", "فروع"},
        "طلب": {"طلب", "اطلب", "طلبات", "اوردر", "أوردر", "توصيل", "دليفري"},
        "دفع": {"دفع", "الدفع", "بطاقة", "كاش", "نقد", "تحويل"},
        "سياسة": {"سياسة", "سياسات", "الغاء", "إلغاء", "استرجاع", "تبديل", "شروط"},
    }

    INTENT_CATEGORY_HINTS = {
        "price": {"services_prices", "menu", "products"},
        "services": {"services_prices", "menu", "products", "general"},
        "hours": {"hours", "branches", "general", "business_profile"},
        "location": {"branches", "general", "business_profile"},
        "booking": {"booking_rules", "services_prices", "hours", "general"},
        "order": {"order_rules", "menu", "products", "delivery_payment"},
        "delivery_payment": {"delivery_payment", "policies", "order_rules"},
        "policy": {"policies", "booking_rules", "order_rules"},
    }

    def normalize(self, text):
        text = (text or "").lower().replace("\r", " ").replace("\n", " ")
        text = (
            text.replace("أ", "ا")
            .replace("إ", "ا")
            .replace("آ", "ا")
            .replace("ة", "ه")
            .replace("ى", "ي")
        )
        text = re.sub(r"[^\w\u0600-\u06FF]+", " ", text)
        return " ".join(text.split())

    def _base_tokens(self, text):
        stop = {self.normalize(word) for word in self.STOP_WORDS}
        return {
            token
            for token in self.normalize(text).split()
            if len(token) >= 2 and token not in stop
        }

    def tokenize(self, text):
        tokens = self._base_tokens(text)
        expanded = set(tokens)
        for canonical, variants in self.ARABIC_EQUIVALENTS.items():
            normalized_variants = {self.normalize(x) for x in variants} | {
                self.normalize(canonical)
            }
            if tokens & normalized_variants:
                expanded |= normalized_variants
        return expanded

    def _ordered_phrases(self, text, size=2):
        base = self._base_tokens(text)
        tokens = [
            token for token in self.normalize(text).split() if token in base
        ]
        if len(tokens) < size:
            return set()
        return {
            " ".join(tokens[index : index + size])
            for index in range(len(tokens) - size + 1)
        }

    def detect_intents(self, query):
        q = self.normalize(query)
        t = self.tokenize(query)
        intents = set()

        def has(words):
            normalized_words = {self.normalize(x) for x in words}
            return bool(t & normalized_words) or any(word in q for word in normalized_words)

        if has({"سعر", "اسعار", "بكم", "تكلفة", "price", "prices", "cost"}):
            intents.add("price")
        if has({"خدمات", "خدمة", "service", "services", "menu", "منيو"}):
            intents.add("services")
        if has({"دوام", "ساعات", "مفتوح", "اغلاق", "hours", "open", "close"}):
            intents.add("hours")
        if has({"وين", "عنوان", "موقع", "فرع", "location", "address", "branch"}):
            intents.add("location")
        if has({"حجز", "موعد", "احجز", "booking", "appointment", "reserve"}):
            intents.add("booking")
        if has({"طلب", "اطلب", "توصيل", "order", "delivery"}):
            intents.add("order")
        if has({"دفع", "بطاقة", "كاش", "payment", "pay", "cash", "card"}):
            intents.add("delivery_payment")
        if has({"سياسة", "الغاء", "استرجاع", "تبديل", "policy", "cancel", "refund", "return"}):
            intents.add("policy")
        return intents

    def split_content(self, content, chunk_size=None, overlap=None):
        chunk_size = chunk_size or self.DEFAULT_CHUNK_SIZE
        overlap = self.DEFAULT_OVERLAP if overlap is None else overlap
        content = (content or "").strip()
        if not content:
            return []
        if len(content) <= chunk_size:
            return [content]
        chunks = []
        start = 0
        while start < len(content):
            end = min(len(content), start + chunk_size)
            piece = content[start:end].strip()
            if piece:
                chunks.append(piece)
            if end >= len(content):
                break
            start = max(start + 1, end - overlap)
        return chunks

    def rebuild_document_index(self, db, document):
        db.query(KnowledgeChunk).filter(
            KnowledgeChunk.document_id == document.id
        ).delete(synchronize_session=False)
        chunks = self.split_content(document.content or "")
        for index, content in enumerate(chunks):
            db.add(
                KnowledgeChunk(
                    company_id=document.company_id,
                    document_id=document.id,
                    chunk_index=index,
                    content=content,
                    normalized_text=self.normalize(content),
                )
            )
        db.flush()
        return len(chunks)

    def backfill_company_index(self, db, company_id):
        docs = (
            db.query(KnowledgeDocument)
            .filter(KnowledgeDocument.company_id == company_id)
            .all()
        )
        indexed = 0
        for doc in docs:
            if (
                db.query(KnowledgeChunk)
                .filter(KnowledgeChunk.document_id == doc.id)
                .first()
                is None
            ):
                self.rebuild_document_index(db, doc)
                indexed += 1
        return indexed

    def _score_match(self, query, chunk, document):
        qnorm = self.normalize(query)
        qtokens = self.tokenize(query)
        if not qtokens:
            return None

        chunk_norm = self.normalize(chunk.normalized_text or chunk.content)
        title_norm = self.normalize(document.title or "")
        ctokens = self.tokenize(chunk_norm)
        ttokens = self.tokenize(title_norm)
        common = qtokens & ctokens
        title_common = qtokens & ttokens
        intents = self.detect_intents(query)

        exact_query = bool(qnorm and len(qnorm) >= 4 and qnorm in chunk_norm)
        query_phrases = self._ordered_phrases(query)
        chunk_phrases = self._ordered_phrases(chunk_norm)
        phrase_matches = query_phrases & chunk_phrases

        category_boost = sum(
            8
            for intent in intents
            if document.source_type in self.INTENT_CATEGORY_HINTS.get(intent, set())
        )

        if not common and not title_common and not phrase_matches and category_boost == 0:
            return None

        coverage = len(common) / max(1, len(qtokens))
        phrase_coverage = (
            len(phrase_matches) / max(1, len(query_phrases)) if query_phrases else 0
        )
        return (
            len(common) * 3
            + len(title_common) * 5
            + coverage * 7
            + len(phrase_matches) * 7
            + phrase_coverage * 5
            + (14 if exact_query else 0)
            + category_boost
        )

    def search_agent_knowledge(self, db, company_id, agent_id, query, max_chunks=None):
        max_chunks = max_chunks or self.DEFAULT_MAX_CHUNKS
        if not self.tokenize(query):
            return []

        rows = (
            db.query(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .join(AgentKnowledge, AgentKnowledge.document_id == KnowledgeDocument.id)
            .filter(
                KnowledgeChunk.company_id == company_id,
                KnowledgeDocument.company_id == company_id,
                KnowledgeDocument.enabled.is_(True),
                AgentKnowledge.agent_id == agent_id,
                AgentKnowledge.enabled.is_(True),
            )
            .all()
        )

        matches = []
        for chunk, doc in rows:
            score = self._score_match(query, chunk, doc)
            if score is None:
                continue
            matches.append(
                KnowledgeMatch(
                    doc.id,
                    doc.title,
                    doc.source_type,
                    chunk.chunk_index,
                    chunk.content,
                    score,
                )
            )

        matches.sort(key=lambda item: (item.score, -item.chunk_index), reverse=True)
        selected = []
        per_document = {}
        for match in matches:
            if per_document.get(match.document_id, 0) >= self.MAX_CHUNKS_PER_DOCUMENT:
                continue
            selected.append(match)
            per_document[match.document_id] = per_document.get(match.document_id, 0) + 1
            if len(selected) >= max_chunks:
                break
        return selected

    def get_agent_context(self, db, company_id, agent_id, query):
        self.backfill_company_index(db, company_id)
        matches = self.search_agent_knowledge(db, company_id, agent_id, query)
        if not matches:
            return ""
        parts = []
        used = 0
        for match in matches:
            block = (
                f"[Knowledge: {match.title} | category: {match.source_type} | "
                f"chunk {match.chunk_index + 1}]\n{match.content}"
            )
            if used + len(block) > self.DEFAULT_MAX_CONTEXT_CHARS:
                remain = self.DEFAULT_MAX_CONTEXT_CHARS - used
                if remain > 250:
                    parts.append(block[:remain])
                break
            parts.append(block)
            used += len(block)
        return "\n\n".join(parts)


knowledge_service = KnowledgeService()
