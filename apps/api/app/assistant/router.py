from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from app.assistant.provider import (
    AIProvider,
    DeterministicMockProvider,
    DisabledProvider,
    GeminiProvider,
)
from app.assistant.schemas import (
    AssistantErrorCode,
    AssistantErrorEnvelope,
    AssistantErrorResponse,
    AssistantFeedbackRequest,
    AssistantFeedbackResponse,
    AssistantRequest,
    AssistantResponse,
)
from app.assistant.service import handle_assistant_request
from app.auth.dependencies import require_authenticated_user, verify_csrf_protection
from app.core.config import get_settings
from app.core.metrics import http_metrics
from app.db.models import AuditEvent, User
from app.db.session import get_db_session
from app.knowledge.rag.config import RetrievalConfig
from app.knowledge.rag.embeddings import (
    DeterministicFakeEmbeddingProvider,
    DisabledEmbeddingProvider,
    EmbeddingProvider,
)


class AssistantRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original(request)
            except RequestValidationError:
                correlation_id = uuid.uuid4()
                return JSONResponse(
                    status_code=422,
                    content=AssistantErrorResponse(
                        error=AssistantErrorEnvelope(
                            code=AssistantErrorCode.INVALID_REQUEST,
                            message="The assistant request is invalid.",
                        ),
                    ).model_dump(mode="json"),
                    headers={"X-Correlation-ID": str(correlation_id)},
                )

        return handler


assistant_router = APIRouter(
    prefix="/assistant", tags=["AI legal awareness"], route_class=AssistantRoute
)


def get_ai_provider() -> AIProvider:
    """Select only an explicitly configured provider; default remains fail closed."""
    settings = get_settings()
    if settings.ai_provider == "demo" and settings.demo_mode_enabled and not settings.is_production:
        return DeterministicMockProvider()
    if settings.ai_provider == "gemini" and settings.gemini_api_key:
        return GeminiProvider(
            settings.gemini_api_key.get_secret_value(),
            model=settings.gemini_model,
            timeout_seconds=settings.gemini_timeout_seconds,
            temperature=settings.gemini_temperature,
            max_output_tokens=settings.gemini_max_output_tokens,
        )
    return DisabledProvider()


def get_embedding_provider() -> EmbeddingProvider:
    """Select a configured embedding provider; default remains fail closed."""
    settings = get_settings()
    if settings.ai_provider == "demo" and settings.demo_mode_enabled and not settings.is_production:
        return DeterministicFakeEmbeddingProvider(dimension=settings.embedding_dimension)
    if settings.embedding_provider == "gemini" and settings.gemini_api_key:
        from app.knowledge.rag.embeddings import GeminiEmbeddingProvider

        return GeminiEmbeddingProvider(
            settings.gemini_api_key.get_secret_value(),
            dimension=settings.embedding_dimension,
            timeout_seconds=settings.gemini_timeout_seconds,
        )
    return DisabledEmbeddingProvider()


def get_retrieval_config() -> RetrievalConfig:
    """Return configured, schema-compatible retrieval metadata."""
    settings = get_settings()
    if settings.ai_provider == "demo" and settings.demo_mode_enabled and not settings.is_production:
        return RetrievalConfig(
            version=f"{settings.retrieval_config_version}-local-demo",
            embedding_model=DeterministicFakeEmbeddingProvider.model_identifier,
            embedding_dimension=settings.embedding_dimension,
        )
    return RetrievalConfig(
        version=settings.retrieval_config_version,
        embedding_model=settings.embedding_model,
        embedding_dimension=settings.embedding_dimension,
    )


@assistant_router.post(
    "/messages",
    response_model=AssistantResponse,
    responses={422: {"model": AssistantErrorResponse}},
    summary="Request bounded, grounded legal awareness",
    dependencies=[Depends(verify_csrf_protection)],
)
async def create_assistant_message(
    payload: AssistantRequest,
    response: Response,
    x_correlation_id: uuid.UUID | None = Header(default=None),
    user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
    provider: AIProvider = Depends(get_ai_provider),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    retrieval_config: RetrievalConfig = Depends(get_retrieval_config),
) -> AssistantResponse:
    correlation_id = x_correlation_id or uuid.uuid4()
    response.headers["X-Correlation-ID"] = str(correlation_id)
    result = await handle_assistant_request(
        db, user.id, payload, provider, correlation_id, embedding_provider, retrieval_config
    )
    http_metrics.observe_assistant_outcome(result.status.value)
    return result


@assistant_router.post(
    "/messages/{correlation_id}/feedback",
    response_model=AssistantFeedbackResponse,
    dependencies=[Depends(verify_csrf_protection)],
    summary="Submit aggregate feedback for the current user's assistant response",
)
async def submit_assistant_feedback(
    correlation_id: uuid.UUID,
    payload: AssistantFeedbackRequest,
    user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
) -> AssistantFeedbackResponse:
    """Record a rating/report without retaining free-form prompt or comment text."""
    response_event = await db.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "assistant.request.completed",
            AuditEvent.actor_id == user.id,
            AuditEvent.request_id == str(correlation_id),
        )
    )
    if response_event is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Response not found.")

    existing = await db.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "assistant.feedback.submitted",
            AuditEvent.actor_id == user.id,
            AuditEvent.request_id == str(correlation_id),
        )
    )
    if existing is None:
        db.add(
            AuditEvent(
                action="assistant.feedback.submitted",
                resource_type="assistant_response",
                actor_id=user.id,
                request_id=str(correlation_id),
                details={"rating": payload.rating, "reported": payload.report_issue},
            )
        )
        await db.commit()
        http_metrics.observe_feedback(payload.rating, payload.report_issue)
    return AssistantFeedbackResponse()
