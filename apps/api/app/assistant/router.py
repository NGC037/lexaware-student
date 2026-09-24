from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from app.assistant.provider import AIProvider, DisabledProvider
from app.assistant.schemas import (
    AssistantErrorCode,
    AssistantErrorEnvelope,
    AssistantErrorResponse,
    AssistantRequest,
    AssistantResponse,
)
from app.assistant.service import handle_assistant_request
from app.auth.dependencies import require_authenticated_user, verify_csrf_protection
from app.db.models import User
from app.db.session import get_db_session


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
    """Fail closed until a provider adapter is explicitly configured."""
    return DisabledProvider()


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
) -> AssistantResponse:
    correlation_id = x_correlation_id or uuid.uuid4()
    response.headers["X-Correlation-ID"] = str(correlation_id)
    return await handle_assistant_request(db, user.id, payload, provider, correlation_id)
