
import re
from dataclasses import dataclass

from backend.app.modules.knowledge.models import (
    AgentKnowledge,
    KnowledgeChunk,
    KnowledgeDocument,
)


@dataclass
class KnowledgeMatch:
    document_id: int
    title: str
    chunk_index: int
    content: str
    score: float


class KnowledgeService:

    DEFAULT_CHUNK_SIZE = 1400
    DEFAULT_OVERLAP = 180
    DEFAULT_MAX_CHUNKS = 6
    DEFAULT_MAX_CONTEXT_CHARS = 7000

    def normalize(
        self,
        text: str,
    ) -> str:

        text = (
            text
            .lower()
            .replace("\r", " ")
            .replace("\n", " ")
        )

        text = re.sub(
            r"[^\w\u0600-\u06FF]+",
            " ",
            text,
        )

        return " ".join(
            text.split()
        )

    def tokenize(
        self,
        text: str,
    ) -> set[str]:

        normalized = self.normalize(
            text
        )

        return {
            token
            for token in normalized.split()
            if len(token) >= 2
        }

    def split_content(
        self,
        content: str,
        chunk_size: int | None = None,
        overlap: int | None = None,
    ) -> list[str]:

        chunk_size = (
            chunk_size
            or self.DEFAULT_CHUNK_SIZE
        )

        overlap = (
            overlap
            if overlap is not None
            else self.DEFAULT_OVERLAP
        )

        content = (
            content
            .strip()
        )

        if not content:
            return []

        if len(content) <= chunk_size:
            return [content]

        paragraphs = [
            item.strip()
            for item in re.split(
                r"\n\s*\n",
                content,
            )
            if item.strip()
        ]

        chunks = []
        current = ""

        for paragraph in paragraphs:

            if (
                current
                and len(current)
                + len(paragraph)
                + 2
                > chunk_size
            ):
                chunks.append(
                    current.strip()
                )

                tail = (
                    current[-overlap:]
                    if overlap > 0
                    else ""
                )

                current = (
                    tail
                    + "\n\n"
                    + paragraph
                ).strip()

            else:
                current = (
                    current
                    + "\n\n"
                    + paragraph
                ).strip()

            while len(current) > chunk_size:

                cut = current[:chunk_size]

                boundary = max(
                    cut.rfind(". "),
                    cut.rfind("? "),
                    cut.rfind("! "),
                    cut.rfind("\n"),
                )

                if boundary < int(
                    chunk_size * 0.55
                ):
                    boundary = chunk_size

                piece = (
                    current[:boundary]
                    .strip()
                )

                if piece:
                    chunks.append(piece)

                start = max(
                    0,
                    boundary - overlap,
                )

                current = (
                    current[start:]
                    .strip()
                )

        if current:
            chunks.append(
                current.strip()
            )

        result = []
        seen = set()

        for chunk in chunks:

            normalized = self.normalize(
                chunk
            )

            if (
                not normalized
                or normalized in seen
            ):
                continue

            seen.add(normalized)
            result.append(chunk)

        return result

    def rebuild_document_index(
        self,
        db,
        document: KnowledgeDocument,
    ) -> int:

        (
            db.query(KnowledgeChunk)
            .filter(
                KnowledgeChunk.document_id
                == document.id
            )
            .delete(
                synchronize_session=False
            )
        )

        chunks = self.split_content(
            document.content or ""
        )

        for index, content in enumerate(
            chunks
        ):

            db.add(
                KnowledgeChunk(
                    company_id=document.company_id,
                    document_id=document.id,
                    chunk_index=index,
                    content=content,
                    normalized_text=self.normalize(
                        content
                    ),
                )
            )

        db.flush()

        return len(chunks)

    def backfill_company_index(
        self,
        db,
        company_id: int,
    ) -> int:

        documents = (
            db.query(KnowledgeDocument)
            .filter(
                KnowledgeDocument.company_id
                == company_id
            )
            .all()
        )

        indexed = 0

        for document in documents:

            exists = (
                db.query(KnowledgeChunk)
                .filter(
                    KnowledgeChunk.document_id
                    == document.id
                )
                .first()
            )

            if exists is None:

                self.rebuild_document_index(
                    db,
                    document,
                )

                indexed += 1

        return indexed

    def search_agent_knowledge(
        self,
        db,
        company_id: int,
        agent_id: int,
        query: str,
        max_chunks: int | None = None,
    ) -> list[KnowledgeMatch]:

        max_chunks = (
            max_chunks
            or self.DEFAULT_MAX_CHUNKS
        )

        query_normalized = self.normalize(
            query
        )

        query_tokens = self.tokenize(
            query
        )

        if not query_tokens:
            return []

        rows = (
            db.query(
                KnowledgeChunk,
                KnowledgeDocument,
            )
            .join(
                KnowledgeDocument,
                KnowledgeDocument.id
                == KnowledgeChunk.document_id,
            )
            .join(
                AgentKnowledge,
                AgentKnowledge.document_id
                == KnowledgeDocument.id,
            )
            .filter(
                KnowledgeChunk.company_id
                == company_id,
                KnowledgeDocument.company_id
                == company_id,
                KnowledgeDocument.enabled.is_(True),
                AgentKnowledge.agent_id
                == agent_id,
                AgentKnowledge.enabled.is_(True),
            )
            .all()
        )

        matches = []

        for chunk, document in rows:

            chunk_tokens = set(
                chunk.normalized_text.split()
            )

            title_normalized = self.normalize(
                document.title or ""
            )

            title_tokens = set(
                title_normalized.split()
            )

            common_chunk = (
                query_tokens
                & chunk_tokens
            )

            common_title = (
                query_tokens
                & title_tokens
            )

            if (
                not common_chunk
                and not common_title
            ):
                continue

            score = 0.0

            score += (
                len(common_chunk)
                * 3.0
            )

            score += (
                len(common_title)
                * 5.0
            )

            if (
                query_normalized
                and query_normalized
                in chunk.normalized_text
            ):
                score += 12.0

            coverage = (
                len(common_chunk)
                / max(
                    1,
                    len(query_tokens),
                )
            )

            score += (
                coverage
                * 6.0
            )

            # Minimum relevance gate:
            # Do not inject weakly related knowledge into the agent context.
            # A match needs either meaningful token coverage,
            # multiple matching terms, a title match, or an exact phrase.
            exact_phrase = bool(
                query_normalized
                and query_normalized
                in chunk.normalized_text
            )

            meaningful_match = (
                exact_phrase
                or len(common_chunk) >= 2
                or len(common_title) >= 1
                or coverage >= 0.60
            )

            if not meaningful_match:
                continue

            matches.append(
                KnowledgeMatch(
                    document_id=document.id,
                    title=document.title,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    score=score,
                )
            )

        matches.sort(
            key=lambda item: (
                item.score,
                -item.chunk_index,
            ),
            reverse=True,
        )

        selected = []
        per_document = {}

        for match in matches:

            count = per_document.get(
                match.document_id,
                0,
            )

            # Avoid one huge document
            # swallowing all retrieval slots.
            if count >= 3:
                continue

            selected.append(match)

            per_document[
                match.document_id
            ] = count + 1

            if len(selected) >= max_chunks:
                break

        return selected

    def get_agent_context(
        self,
        db,
        company_id: int,
        agent_id: int,
        query: str,
    ) -> str:

        self.backfill_company_index(
            db,
            company_id,
        )

        matches = (
            self.search_agent_knowledge(
                db=db,
                company_id=company_id,
                agent_id=agent_id,
                query=query,
            )
        )

        if not matches:
            return ""

        parts = []
        used_chars = 0

        for match in matches:

            block = (
                f"[Knowledge: {match.title} "
                f"| chunk {match.chunk_index + 1}]\n"
                f"{match.content}"
            )

            if (
                used_chars
                + len(block)
                > self.DEFAULT_MAX_CONTEXT_CHARS
            ):
                remaining = (
                    self.DEFAULT_MAX_CONTEXT_CHARS
                    - used_chars
                )

                if remaining > 250:
                    parts.append(
                        block[:remaining]
                    )

                break

            parts.append(block)
            used_chars += len(block)

        return "\n\n".join(parts)


knowledge_service = KnowledgeService()
