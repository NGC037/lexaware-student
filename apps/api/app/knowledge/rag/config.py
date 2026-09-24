"""Immutable retrieval configuration version."""

from dataclasses import asdict, dataclass

from app.knowledge.rag_config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    CHUNKING_VERSION,
    FTS_CANDIDATE_LIMIT,
    LEXICAL_WEIGHT,
    RETRIEVAL_CONFIG_VERSION,
    VECTOR_CANDIDATE_LIMIT,
    VECTOR_DIMENSION,
    VECTOR_WEIGHT,
)


@dataclass(frozen=True, slots=True)
class RetrievalConfig:
    version: str = RETRIEVAL_CONFIG_VERSION
    fts_configuration: str = "english"
    embedding_model: str = "deterministic-hash-v1"
    embedding_dimension: int = VECTOR_DIMENSION
    chunking_version: str = CHUNKING_VERSION
    chunk_size: int = CHUNK_SIZE
    chunk_overlap: int = CHUNK_OVERLAP
    fts_candidates: int = FTS_CANDIDATE_LIMIT
    vector_candidates: int = VECTOR_CANDIDATE_LIMIT
    lexical_weight: float = LEXICAL_WEIGHT
    vector_weight: float = VECTOR_WEIGHT
    minimum_vector_similarity: float = 0.35
    similarity_metric: str = "cosine"
    ranking_strategy: str = "weighted-normalized-sum-v1"
    filter_policy: str = "student-governance-v1"

    def as_metadata(self) -> dict[str, str | int | float]:
        return asdict(self)
