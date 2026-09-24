from uuid import uuid4

import pytest

from app.knowledge.rag.chunking import KnowledgeSection, chunk_sections, split_section
from app.knowledge.rag.config import RetrievalConfig
from app.knowledge.rag.embeddings import (
    DeterministicFakeEmbeddingProvider,
    EmbeddingProviderError,
    validate_embeddings,
)


def test_chunking_is_stable_and_retains_section_context() -> None:
    version_id = uuid4()
    config = RetrievalConfig(chunk_size=80, chunk_overlap=15)
    sections = [KnowledgeSection("procedure", "Procedure", "Apply first. " * 24)]
    first = chunk_sections(version_id, sections, config)
    second = chunk_sections(version_id, sections, config)
    assert first == second
    assert len(first) > 1
    assert all(chunk.text.startswith("Section: Procedure\n") for chunk in first)
    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]


def test_chunking_overlap_and_complete_text_coverage() -> None:
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"
    chunks = split_section(text, size=32, overlap=8)
    assert len(chunks) > 1
    assert all(
        set(chunks[index].split()[-1:]).intersection(chunks[index + 1].split()[:2])
        for index in range(len(chunks) - 1)
    )
    rebuilt = " ".join(chunks)
    assert all(token in rebuilt for token in text.split())


@pytest.mark.asyncio
async def test_fake_embeddings_are_repeatable_batched_and_dimension_checked() -> None:
    provider = DeterministicFakeEmbeddingProvider(32)
    batch = await provider.embed_texts(["same query", "same query", "other query"])
    assert batch[0] == batch[1]
    assert batch[0] != batch[2]
    assert all(len(vector) == 32 for vector in batch)
    validate_embeddings(["same query"], batch[:1], expected_dimension=32)
    with pytest.raises(EmbeddingProviderError):
        validate_embeddings(["same query"], batch[:1], expected_dimension=31)
