"""Vendor-neutral asynchronous text embedding contract and deterministic fake."""

import asyncio
import hashlib
import math
import re
from collections.abc import Callable
from typing import Any, Literal, Protocol

from app.knowledge.rag.config import RetrievalConfig


class EmbeddingProviderError(RuntimeError):
    """Embedding adapter failed or returned invalid output."""


class EmbeddingProvider(Protocol):
    model_identifier: str
    dimension: int

    async def embed_texts(
        self,
        texts: list[str],
        *,
        task_type: Literal["RETRIEVAL_QUERY", "RETRIEVAL_DOCUMENT"] = "RETRIEVAL_DOCUMENT",
    ) -> list[list[float]]: ...

    async def health(self) -> bool: ...

    def provider_metadata(self) -> dict[str, str | int]: ...


class DisabledEmbeddingProvider:
    model_identifier = "disabled"

    def __init__(self, dimension: int = RetrievalConfig().embedding_dimension) -> None:
        self.dimension = dimension

    async def embed_texts(
        self,
        texts: list[str],
        *,
        task_type: Literal["RETRIEVAL_QUERY", "RETRIEVAL_DOCUMENT"] = "RETRIEVAL_DOCUMENT",
    ) -> list[list[float]]:
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

    async def embed_texts(
        self,
        texts: list[str],
        *,
        task_type: Literal["RETRIEVAL_QUERY", "RETRIEVAL_DOCUMENT"] = "RETRIEVAL_DOCUMENT",
    ) -> list[list[float]]:
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


class GeminiEmbeddingProvider:
    """Production Google Gemini embedding adapter with bounded, sanitized failures."""

    model_identifier = "gemini-embedding-001"

    def __init__(
        self,
        api_key: str,
        *,
        dimension: int = 768,
        timeout_seconds: float = 30,
        client: Any | None = None,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("Gemini API key is required.")
        if dimension != 768:
            raise ValueError(
                "Gemini embedding configuration must match the 768-dimensional schema."
            )
        if not 0 < timeout_seconds <= 120:
            raise ValueError("Embedding timeout must be between 0 and 120 seconds.")
        self.dimension = dimension
        self.timeout_seconds = timeout_seconds
        self._types: Any = None
        if client is None:
            try:
                from google import genai
                from google.genai import types

                client = (client_factory or genai.Client)(
                    api_key=api_key,
                    http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
                )
                self._types = types
            except Exception as exc:
                raise EmbeddingProviderError("Gemini embedding provider is unavailable.") from exc
        else:
            try:
                from google.genai import types

                self._types = types
            except ImportError:
                self._types = None
        self._client = client

    async def embed_texts(
        self,
        texts: list[str],
        *,
        task_type: Literal["RETRIEVAL_QUERY", "RETRIEVAL_DOCUMENT"] = "RETRIEVAL_DOCUMENT",
    ) -> list[list[float]]:
        if not texts:
            return []
        try:
            if self._types is not None:
                config = self._types.EmbedContentConfig(
                    task_type=task_type, output_dimensionality=self.dimension
                )
            else:
                config = {"task_type": task_type, "output_dimensionality": self.dimension}
            response = await asyncio.wait_for(
                self._client.aio.models.embed_content(
                    model=self.model_identifier, contents=texts, config=config
                ),
                timeout=self.timeout_seconds,
            )
            embeddings = response.embeddings or []
            vectors = [[float(value) for value in item.values] for item in embeddings]
            validate_embeddings(texts, vectors, expected_dimension=self.dimension)
            # Gemini Embedding 001 requires normalization when requesting fewer than 3072 dims.
            return [_normalize(vector) for vector in vectors]
        except TimeoutError as exc:
            raise EmbeddingProviderError("Gemini embedding request timed out.") from exc
        except EmbeddingProviderError:
            raise
        except Exception as exc:
            raise EmbeddingProviderError("Gemini embedding request failed.") from exc

    async def health(self) -> bool:
        return True

    def provider_metadata(self) -> dict[str, str | int]:
        return {
            "provider": "gemini",
            "model": self.model_identifier,
            "dimension": self.dimension,
        }


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        raise EmbeddingProviderError("Gemini embedding provider returned a zero vector.")
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
