"""Explicit, eligibility-gated and idempotent chunk indexing."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Jurisdiction, KnowledgeChunk, KnowledgeItem, KnowledgeVersion, Source
from app.knowledge.eligibility import student_knowledge_eligibility
from app.knowledge.rag.chunking import KnowledgeSection, chunk_sections
from app.knowledge.rag.config import RetrievalConfig
from app.knowledge.rag.embeddings import (
    EmbeddingProvider,
    EmbeddingProviderError,
    validate_embeddings,
)


@dataclass(frozen=True, slots=True)
class IndexingResult:
    indexed: bool
    chunk_count: int
    reason: str


async def index_knowledge_version(
    db: AsyncSession,
    version_id: uuid.UUID,
    provider: EmbeddingProvider,
    config: RetrievalConfig | None = None,
) -> IndexingResult:
    selected = config or RetrievalConfig()
    result = await db.execute(
        select(KnowledgeItem, KnowledgeVersion, Source, Jurisdiction)
        .join(KnowledgeVersion, KnowledgeVersion.knowledge_item_id == KnowledgeItem.id)
        .join(Source, Source.id == KnowledgeVersion.source_id)
        .join(Jurisdiction, Jurisdiction.id == KnowledgeItem.jurisdiction_id)
        .where(KnowledgeVersion.id == version_id, *student_knowledge_eligibility())
    )
    row = result.first()
    if row is None:
        return IndexingResult(indexed=False, chunk_count=0, reason="not_eligible")
    if provider.model_identifier != selected.embedding_model:
        raise EmbeddingProviderError("Embedding provider model does not match retrieval config.")
    item, version, _source, _jurisdiction = row

    sections = [
        KnowledgeSection("title", "Title", version.title or item.title),
        KnowledgeSection("summary", "Summary", version.summary or ""),
        KnowledgeSection("content", "Guidance", version.content),
        KnowledgeSection("applicability", "Applicability", version.applicability_notes or ""),
        KnowledgeSection("escalation", "Escalation", version.escalation_guidance or ""),
        KnowledgeSection(
            "discovery",
            "Search terms",
            "\n".join([*version.tags, *version.keywords, version.synonyms or ""]),
        ),
    ]
    chunks = chunk_sections(version.id, sections, selected)
    if not chunks:
        return IndexingResult(indexed=False, chunk_count=0, reason="empty_content")
    texts = [chunk.text for chunk in chunks]
    try:
        vectors = await provider.embed_texts(texts, task_type="RETRIEVAL_DOCUMENT")
        validate_embeddings(texts, vectors, expected_dimension=selected.embedding_dimension)
    except EmbeddingProviderError:
        raise
    except Exception as exc:
        raise EmbeddingProviderError("Embedding provider failed.") from exc
    if provider.dimension != selected.embedding_dimension:
        raise EmbeddingProviderError(
            "Embedding provider dimension does not match retrieval config."
        )

    # Compute/validate all vectors before deleting previous rows so an adapter failure leaves
    # the last good index intact. Governance is read again on every search.
    await db.execute(
        delete(KnowledgeChunk).where(KnowledgeChunk.knowledge_version_id == version.id)
    )
    indexed_at = datetime.now(UTC)
    for chunk, vector in zip(chunks, vectors, strict=True):
        db.add(
            KnowledgeChunk(
                id=chunk.chunk_id,
                knowledge_version_id=version.id,
                section_key=chunk.section_key,
                section_title=chunk.section_title,
                ordinal=chunk.ordinal,
                chunk_text=chunk.text,
                content_hash=chunk.content_hash,
                chunking_version=chunk.chunking_version,
                indexed_version_updated_at=version.updated_at,
                embedding_model=provider.model_identifier,
                embedding_dimension=provider.dimension,
                embedding=vector,
                created_at=indexed_at,
                updated_at=indexed_at,
            )
        )
    await db.commit()
    return IndexingResult(indexed=True, chunk_count=len(chunks), reason="indexed")
