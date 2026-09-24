from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.schemas import AssistantRequest
from app.knowledge.rag.config import RetrievalConfig
from app.knowledge.rag.embeddings import EmbeddingProvider
from app.knowledge.rag.retrieval import HybridRetrievalResult, hybrid_search


async def retrieve_governed_context(
    db: AsyncSession,
    request: AssistantRequest,
    embeddings: EmbeddingProvider,
    config: RetrievalConfig,
) -> HybridRetrievalResult:
    # The optional topic is metadata and may be a sensitive free-form label; search only
    # the user message and never retain either value beyond this request.
    query = request.message
    return await hybrid_search(
        db,
        query=query,
        jurisdiction_code=request.jurisdiction,
        provider=embeddings,
        top_k=5,
        config=config,
    )
