from __future__ import annotations

from typing import Protocol

from app.assistant.schemas import (
    AssistantProviderContent,
    AssistantStatus,
    ProviderRequest,
    ProviderResponse,
)


class ProviderUnavailableError(Exception):
    """Provider is disabled or unavailable; messages are never returned to clients."""


class AIProvider(Protocol):
    async def generate(self, request: ProviderRequest) -> ProviderResponse: ...

    async def health(self) -> bool: ...

    def model_metadata(self) -> dict[str, str]: ...


class DisabledProvider:
    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        raise ProviderUnavailableError("No AI provider is configured.")

    async def health(self) -> bool:
        return False

    def model_metadata(self) -> dict[str, str]:
        return {"provider": "disabled", "model": "none"}


class DeterministicMockProvider:
    """Explicit test/development provider; never configured as a production model."""

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        reference = request.governed_context[0].reference_key
        title = request.governed_context[0].title
        return ProviderResponse(
            content=AssistantProviderContent(
                status=AssistantStatus.ANSWER,
                what_this_may_mean=(
                    f"The approved guidance titled {title!r} may be relevant. "
                    "Your options depend on the facts and applicable rules."
                ),
                relevant_facts_or_dependencies=[
                    "The applicable jurisdiction and exact facts matter."
                ],
                next_steps=[],
                citation_keys=[reference],
                limitations=["This is general legal awareness, not legal advice."],
                uncertainty="A qualified local adviser can assess your circumstances.",
            ),
            provider_name="deterministic-mock",
            model_identifier="mock-v1",
        )

    async def health(self) -> bool:
        return True

    def model_metadata(self) -> dict[str, str]:
        return {"provider": "deterministic-mock", "model": "mock-v1"}
