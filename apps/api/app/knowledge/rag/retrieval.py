"""Governed PostgreSQL FTS and pgvector hybrid candidate retrieval."""

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.schemas import GroundingCandidate
from app.db.models import (
    Jurisdiction,
    KnowledgeChunk,
    KnowledgeItem,
    KnowledgeVersion,
    Source,
)
from app.knowledge.eligibility import student_knowledge_eligibility
from app.knowledge.rag.config import RetrievalConfig
from app.knowledge.rag.embeddings import (
    EmbeddingProvider,
    EmbeddingProviderError,
    validate_embeddings,
)


class RetrievalState(StrEnum):
    OK = "ok"
    NO_RESULTS = "no_results"
    JURISDICTION_REQUIRED = "jurisdiction_required"


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    grounding: GroundingCandidate
    lexical_score: float
    vector_score: float
    hybrid_score: float
    section_key: str
    chunk_id: str | None


@dataclass(slots=True)
class _Accumulator:
    grounding: GroundingCandidate
    lexical_score: float
    vector_score: float = 0.0
    section_key: str = "content"
    chunk_id: str | None = None
    retrieval_methods: set[Literal["fts", "vector"]] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class HybridRetrievalResult:
    state: RetrievalState
    candidates: list[RankedCandidate]
    config_version: str


def _grounding(
    row: tuple[KnowledgeItem, KnowledgeVersion, Jurisdiction, Source], text: str
) -> GroundingCandidate:
    item, version, jurisdiction, source = row[:4]
    return GroundingCandidate(
        reference_key=f"knowledge:{item.slug}:v{version.version_number}",
        knowledge_slug=item.slug,
        knowledge_version=version.version_number,
        title=version.title or item.title,
        content=text,
        jurisdiction_code=jurisdiction.code,
        jurisdiction_name=jurisdiction.name,
        source_title=source.title,
        source_url=source.source_url,
        source_publisher=source.publisher,
        source_citation=source.citation,
        effective_from=version.effective_from,
        effective_until=version.effective_until,
        reviewed_at=version.reviewed_at,
        review_due_at=version.review_due_at,
        publication_state=version.publication_state.value,
        item_status=item.status.value,
        source_is_active=source.is_active,
        source_effective_from=source.effective_from,
        source_effective_until=source.effective_until,
        source_review_state="active" if source.is_active else "inactive",
    )


async def hybrid_search(
    db: AsyncSession,
    *,
    query: str,
    jurisdiction_code: str | None,
    provider: EmbeddingProvider,
    top_k: int = 5,
    config: RetrievalConfig | None = None,
) -> HybridRetrievalResult:
    selected = config or RetrievalConfig()
    if jurisdiction_code is None or not jurisdiction_code.strip():
        return HybridRetrievalResult(RetrievalState.JURISDICTION_REQUIRED, [], selected.version)
    if not 1 <= top_k <= 20:
        raise ValueError("top_k must be between 1 and 20")
    if provider.model_identifier != selected.embedding_model:
        raise EmbeddingProviderError("Embedding provider model does not match retrieval config.")
    normalized = re.sub(r"[\x00-\x1f\x7f]+", " ", query).strip()
    if not normalized:
        return HybridRetrievalResult(RetrievalState.NO_RESULTS, [], selected.version)
    jurisdiction = func.lower(Jurisdiction.code) == jurisdiction_code.strip().lower()
    joins = (
        select(KnowledgeItem, KnowledgeVersion, Jurisdiction, Source)
        .join(KnowledgeVersion, KnowledgeVersion.knowledge_item_id == KnowledgeItem.id)
        .join(Jurisdiction, Jurisdiction.id == KnowledgeItem.jurisdiction_id)
        .join(Source, Source.id == KnowledgeVersion.source_id)
        .where(*student_knowledge_eligibility(), jurisdiction)
    )

    tsquery = func.plainto_tsquery(selected.fts_configuration, normalized)
    vector = KnowledgeVersion.search_vector.cast(TSVECTOR)
    escaped = normalized.casefold().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    lexical_statement = (
        joins.add_columns(func.ts_rank_cd(vector, tsquery).label("rank"))
        .where(
            vector.op("@@")(tsquery)
            | func.lower(KnowledgeItem.title).ilike(pattern, escape="\\")
            | func.lower(KnowledgeItem.category).ilike(pattern, escape="\\")
            | func.lower(KnowledgeItem.topic).ilike(pattern, escape="\\")
        )
        .order_by(
            func.ts_rank_cd(vector, tsquery).desc(),
            KnowledgeItem.slug,
            KnowledgeVersion.version_number,
        )
        .limit(selected.fts_candidates)
    )
    lexical_rows = (await db.execute(lexical_statement)).all()

    try:
        query_vectors = await provider.embed_texts([normalized], task_type="RETRIEVAL_QUERY")
        validate_embeddings(
            [normalized], query_vectors, expected_dimension=selected.embedding_dimension
        )
    except EmbeddingProviderError:
        raise
    except Exception as exc:
        raise EmbeddingProviderError("Embedding provider failed.") from exc
    if provider.dimension != selected.embedding_dimension:
        raise EmbeddingProviderError(
            "Embedding provider dimension does not match retrieval config."
        )
    query_vector = query_vectors[0]
    distance = KnowledgeChunk.embedding.cosine_distance(query_vector)
    vector_statement = (
        select(
            KnowledgeItem,
            KnowledgeVersion,
            Jurisdiction,
            Source,
            KnowledgeChunk,
            distance.label("distance"),
        )
        .join(KnowledgeVersion, KnowledgeVersion.knowledge_item_id == KnowledgeItem.id)
        .join(KnowledgeChunk, KnowledgeChunk.knowledge_version_id == KnowledgeVersion.id)
        .join(Jurisdiction, Jurisdiction.id == KnowledgeItem.jurisdiction_id)
        .join(Source, Source.id == KnowledgeVersion.source_id)
        .where(
            *student_knowledge_eligibility(),
            jurisdiction,
            KnowledgeChunk.embedding_model == provider.model_identifier,
            KnowledgeChunk.embedding_dimension == selected.embedding_dimension,
            KnowledgeChunk.indexed_version_updated_at == KnowledgeVersion.updated_at,
        )
        .order_by(distance, KnowledgeItem.slug, KnowledgeVersion.version_number, KnowledgeChunk.id)
        .limit(selected.vector_candidates)
    )
    vector_rows = (await db.execute(vector_statement)).all()

    # Normalize lexical raw rank by r/(1+r); cosine distance maps to [0,1] similarity.
    merged: dict[str, _Accumulator] = {}
    for row in lexical_rows:
        item, version, jur, source, raw_score = row
        key = f"knowledge:{item.slug}:v{version.version_number}"
        lexical_score = float(raw_score) / (1.0 + float(raw_score))
        merged[key] = _Accumulator(
            grounding=_grounding((item, version, jur, source), version.content),
            lexical_score=lexical_score,
            retrieval_methods={"fts"},
        )
    for row in vector_rows:
        item, version, jur, source, chunk, raw_distance = row
        key = f"knowledge:{item.slug}:v{version.version_number}"
        vector_score = min(1.0, max(0.0, 1.0 - float(raw_distance)))
        if vector_score < selected.minimum_vector_similarity:
            continue
        current = merged.get(key)
        if current is None or vector_score > current.vector_score:
            methods = set(current.retrieval_methods) if current else set()
            methods.add("vector")
            merged[key] = _Accumulator(
                grounding=_grounding((item, version, jur, source), chunk.chunk_text),
                lexical_score=current.lexical_score if current else 0.0,
                vector_score=vector_score,
                section_key=chunk.section_key,
                chunk_id=str(chunk.id),
                retrieval_methods=methods,
            )
        elif current is not None:
            current.retrieval_methods.add("vector")
    ranked: list[RankedCandidate] = []
    for values in merged.values():
        lexical_score = values.lexical_score
        vector_score = values.vector_score
        hybrid_score = (
            selected.lexical_weight * lexical_score + selected.vector_weight * vector_score
        )
        grounding = values.grounding.model_copy(
            update={
                "chunk_id": values.chunk_id,
                "section_key": values.section_key,
                "retrieval_methods": sorted(values.retrieval_methods),
                "lexical_score": lexical_score,
                "vector_score": vector_score,
                "hybrid_score": selected.lexical_weight * lexical_score
                + selected.vector_weight * vector_score,
                "retrieval_config_version": selected.version,
            }
        )
        ranked.append(
            RankedCandidate(
                grounding=grounding,
                lexical_score=lexical_score,
                vector_score=vector_score,
                hybrid_score=hybrid_score,
                section_key=values.section_key,
                chunk_id=values.chunk_id,
            )
        )
    ranked.sort(
        key=lambda candidate: (
            -candidate.hybrid_score,
            -candidate.lexical_score,
            -candidate.vector_score,
            candidate.grounding.jurisdiction_code.casefold(),
            candidate.grounding.knowledge_slug,
            candidate.grounding.knowledge_version,
            candidate.chunk_id or "",
        )
    )
    ranked = ranked[:top_k]
    state = RetrievalState.OK if ranked else RetrievalState.NO_RESULTS
    return HybridRetrievalResult(state, ranked, selected.version)
