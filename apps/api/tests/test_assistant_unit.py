from datetime import UTC, datetime, timedelta

import pytest

from app.assistant.classifier import classify_request
from app.assistant.grounding import (
    GroundingValidationError,
    contains_definitive_claim,
    is_current_candidate,
    validate_provider_content,
)
from app.assistant.prompts import load_system_instructions
from app.assistant.provider import DeterministicMockProvider, ProviderUnavailableError
from app.assistant.safety import select_route
from app.assistant.schemas import (
    AssistantProviderContent,
    AssistantRequest,
    AssistantStatus,
    GroundingCandidate,
)


@pytest.mark.parametrize(
    ("message", "jurisdiction", "route"),
    [
        ("How do tenant deposit rules work?", None, AssistantStatus.CLARIFY),
        ("How do tenant deposit rules work?", "IN-KA", AssistantStatus.ANSWER),
        ("I am in immediate danger", None, AssistantStatus.ESCALATE),
        ("Someone threatened to hurt me", None, AssistantStatus.ESCALATE),
        ("I was raped", None, AssistantStatus.ESCALATE),
        ("I want to kill myself", None, AssistantStatus.ESCALATE),
        ("A child is being abused", None, AssistantStatus.ESCALATE),
        ("Someone is blackmailing me", None, AssistantStatus.ESCALATE),
        ("My bank account is being drained", None, AssistantStatus.ESCALATE),
        ("My hearing is tomorrow", None, AssistantStatus.ESCALATE),
        ("How can I destroy the evidence?", None, AssistantStatus.REFUSE),
        ("Can you guarantee I will win my case?", None, AssistantStatus.REFUSE),
        ("What is the football score?", None, AssistantStatus.OUT_OF_SCOPE),
    ],
)
def test_deterministic_classification(
    message: str, jurisdiction: str | None, route: AssistantStatus
) -> None:
    decision = select_route(
        classify_request(AssistantRequest(message=message, jurisdiction=jurisdiction))
    )
    assert decision.route == route
    assert decision.provider_allowed is (route == AssistantStatus.ANSWER)


def candidate(**overrides: object) -> GroundingCandidate:
    now = datetime.now(UTC)
    values: dict[str, object] = {
        "reference_key": "knowledge:tenant:v1",
        "knowledge_slug": "tenant",
        "knowledge_version": 1,
        "title": "Tenant rights",
        "content": "Governed tenant content.",
        "jurisdiction_code": "IN-KA",
        "jurisdiction_name": "Karnataka, India",
        "source_title": "Official Act",
        "source_url": "https://example.gov/act",
        "reviewed_at": now - timedelta(days=1),
        "review_due_at": now + timedelta(days=30),
        "publication_state": "published",
        "item_status": "active",
        "source_is_active": True,
    }
    values.update(overrides)
    return GroundingCandidate(**values)  # type: ignore[arg-type]


def content(**overrides: object) -> AssistantProviderContent:
    values: dict[str, object] = {
        "status": AssistantStatus.ANSWER,
        "what_this_may_mean": "The approved guidance may be relevant to your question.",
        "citation_keys": ["knowledge:tenant:v1"],
        "limitations": ["This is general legal awareness."],
        "uncertainty": "The exact facts may change how it applies.",
    }
    values.update(overrides)
    return AssistantProviderContent(**values)  # type: ignore[arg-type]


def test_grounding_rejects_stale_wrong_jurisdiction_and_unknown_reference() -> None:
    stale = candidate(review_due_at=datetime.now(UTC) - timedelta(seconds=1))
    assert not is_current_candidate(stale)
    with pytest.raises(GroundingValidationError):
        validate_provider_content(content(), [stale], "IN-KA")
    with pytest.raises(GroundingValidationError):
        validate_provider_content(content(), [candidate(jurisdiction_code="IN-TN")], "IN-KA")
    with pytest.raises(GroundingValidationError):
        validate_provider_content(content(citation_keys=["invented"]), [candidate()], "IN-KA")


def test_final_safety_validator_and_prompt_are_bounded() -> None:
    assert contains_definitive_claim(content(what_this_may_mean="You will definitely win."))
    assert "Do not invent laws" in load_system_instructions()


@pytest.mark.asyncio
async def test_mock_provider_and_disabled_provider_contract() -> None:
    request = __import__("app.assistant.schemas", fromlist=["ProviderRequest"]).ProviderRequest(
        system_instructions="instructions",
        prompt_id="test",
        prompt_version="1",
        structured_input=AssistantRequest(message="tenant rights", jurisdiction="IN-KA"),
        governed_context=[candidate()],
        response_schema_version="v1",
        model_configuration={},
        correlation_id=__import__("uuid").uuid4(),
    )
    response = await DeterministicMockProvider().generate(request)
    assert response.content.citation_keys == ["knowledge:tenant:v1"]
    from app.assistant.provider import DisabledProvider

    with pytest.raises(ProviderUnavailableError):
        await DisabledProvider().generate(request)
