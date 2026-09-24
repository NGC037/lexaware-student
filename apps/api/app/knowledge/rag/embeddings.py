"""Vendor-neutral asynchronous text embedding contract and deterministic fake."""

import hashlib
import math
import re
from typing import Protocol

from app.knowledge.rag.config import RetrievalConfig


class EmbeddingProviderError(RuntimeError):
    """Embedding adapter failed or returned invalid output."""


class EmbeddingProvider(Protocol):
    model_identifier: str
    dimension: int

    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    async def health(self) -> bool: ...

    def provider_metadata(self) -> dict[str, str | int]: ...


class DisabledEmbeddingProvider:
    model_identifier = "disabled"

    def __init__(self, dimension: int = RetrievalConfig().embedding_dimension) -> None:
        self.dimension = dimension

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingProviderError("Embedding provider is not configured.")

    async def health(self) -> bool:
        return False

    def provider_metadata(self) -> dict[str, str | int]:
        return {"provider": "disabled", "model": self.model_identifier, "dimension": self.dimension}


class DeterministicFakeEmbeddingProvider:
    """Stable test-only feature hashing; it is not a semantic production model."""

    model_identifier = "deterministic-hash-v1"

    def __init__(self, dimension: int = RetrievalConfig().embedding_dimension) -> None:
        if dimension < 2:
            raise ValueError("Embedding dimension must be at least two.")
        self.dimension = dimension

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    async def health(self) -> bool:
        return True

    def provider_metadata(self) -> dict[str, str | int]:
        return {"provider": "fake", "model": self.model_identifier, "dimension": self.dimension}

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in re.findall(r"[\w]+", text.casefold()):
            raw = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(raw[:4], "big") % self.dimension
            vector[bucket] += 1.0 if raw[4] & 1 else -1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            vector[0] = 1.0
            norm = 1.0
        return [value / norm for value in vector]


def validate_embeddings(
    texts: list[str], vectors: list[list[float]], *, expected_dimension: int
) -> None:
    if len(vectors) != len(texts):
        raise EmbeddingProviderError("Embedding provider returned an invalid result count.")
    for vector in vectors:
        if len(vector) != expected_dimension:
            raise EmbeddingProviderError("Embedding provider returned an invalid dimension.")
        if any(not math.isfinite(value) for value in vector):
            raise EmbeddingProviderError("Embedding provider returned non-finite values.")
        if not any(value != 0 for value in vector):
            raise EmbeddingProviderError("Embedding provider returned a zero vector.")
