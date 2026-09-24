from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.classifier import classify_request
from app.assistant.grounding import (
    GroundingValidationError,
    contains_definitive_claim,
    validate_provider_content,
)
from app.assistant.prompts import PROMPT_METADATA, load_system_instructions
from app.assistant.provider import AIProvider, ProviderUnavailableError
from app.assistant.retrieval import retrieve_governed_context
from app.assistant.safety import select_route
from app.assistant.schemas import (
    AssistantErrorCode,
    AssistantRequest,
    AssistantResponse,
    AssistantSource,
    AssistantStatus,
    AssistantTrace,
    AssistantUrgentResource,
    JurisdictionState,
    ProviderRequest,
    RiskCategory,
    SafetyClassification,
)
from app.auth.service import record_audit_event
from app.db.models import AuditEvent, Jurisdiction
from app.help.service import list_student_help_resources

RETRIEVAL_VERSION = "postgres-fts-v1"


def _response(
    status_value: AssistantStatus,
    classification: SafetyClassification,
    correlation_id: uuid.UUID,
    started_at: datetime,
    *,
    message: str,
    error: AssistantErrorCode | None = None,
    sources: list[AssistantSource] | None = None,
    resources: list[AssistantUrgentResource] | None = None,
    provider_name: str | None = None,
    model_identifier: str | None = None,
    knowledge_references: list[str] | None = None,
    failure_category: AssistantErrorCode | None = None,
    validation: dict[str, bool] | None = None,
) -> AssistantResponse:
    now = datetime.now(UTC)
    return AssistantResponse(
        status=status_value,
        classification=classification,
        what_this_may_mean=message,
        relevant_facts_or_dependencies=[],
        next_steps=[],
        urgent_help=message if status_value == AssistantStatus.ESCALATE else "",
        urgent_resources=resources or [],
        sources=sources or [],
        limitations=["This service provides general legal awareness, not legal advice."],
        uncertainty="A qualified local adviser can assess your circumstances.",
        escalation=message if status_value == AssistantStatus.ESCALATE else "",
        error_code=error,
        trace=AssistantTrace(
            correlation_id=correlation_id,
            route=status_value,
            risk_level=classification.risk_level,
            risk_category=classification.category,
            prompt_id=PROMPT_METADATA.prompt_id,
            prompt_version=PROMPT_METADATA.version,
            response_schema_version=PROMPT_METADATA.response_schema_version,
            retrieval_version=RETRIEVAL_VERSION,
            provider_name=provider_name,
            model_identifier=model_identifier,
            knowledge_references=knowledge_references or [],
            validation_outcomes=validation or {},
            failure_category=failure_category,
            started_at=started_at,
            completed_at=now,
        ),
    )


async def _record_trace(
    db: AsyncSession,
    actor_id: uuid.UUID,
    response: AssistantResponse,
    provider_name: str | None,
    model_identifier: str | None,
) -> None:
    trace = response.trace
    correlation_id = str(trace.correlation_id)
    await record_audit_event(
        db,
        action="assistant.request.completed",
        resource_type="assistant_request",
        actor_id=actor_id,
        details={
            "correlation_id": correlation_id,
            "route": trace.route.value,
            "risk_level": trace.risk_level.value,
            "risk_category": trace.risk_category.value,
            "provider": provider_name,
            "model": model_identifier,
            "prompt_id": trace.prompt_id,
            "prompt_version": trace.prompt_version,
            "retrieval_version": trace.retrieval_version,
            "knowledge_references": trace.knowledge_references,
            "validation_outcomes": trace.validation_outcomes,
            "failure_category": trace.failure_category.value if trace.failure_category else None,
            "started_at": trace.started_at.isoformat(),
            "completed_at": trace.completed_at.isoformat(),
        },
    )
    event = await db.execute(
        select(AuditEvent).where(
            AuditEvent.action == "assistant.request.completed",
            AuditEvent.details["correlation_id"].as_string() == correlation_id,
        )
    )
    audit_event = event.scalar_one()
    audit_event.request_id = correlation_id
    await db.commit()


async def handle_assistant_request(
    db: AsyncSession,
    actor_id: uuid.UUID,
    request: AssistantRequest,
    provider: AIProvider,
    correlation_id: uuid.UUID,
) -> AssistantResponse:
    started = datetime.now(UTC)
    classification = classify_request(request)
    decision = select_route(classification)
    error: AssistantErrorCode | None = None
    resources: list[AssistantUrgentResource] = []
    sources: list[AssistantSource] = []
    provider_name: str | None = None
    model_identifier: str | None = None
    references: list[str] = []
    validation: dict[str, bool] = {"safety_gate": True}
    failure: AssistantErrorCode | None = None
    response_status = decision.route

    jurisdiction = None
    if request.jurisdiction:
        jurisdiction = (
            await db.execute(
                select(Jurisdiction).where(
                    func.lower(Jurisdiction.code) == request.jurisdiction.casefold()
                )
            )
        ).scalar_one_or_none()
        if jurisdiction is None and decision.route == AssistantStatus.ANSWER:
            classification = classification.model_copy(
                update={
                    "category": RiskCategory.JURISDICTION_MISMATCH,
                    "jurisdiction_state": JurisdictionState.MISMATCH,
                    "clarification_required": True,
                }
            )
            response_status = AssistantStatus.CLARIFY
            decision = decision.model_copy(update={"provider_allowed": False})

    message = ""
    if response_status == AssistantStatus.ESCALATE:
        if classification.category == RiskCategory.IMMINENT_DEADLINE:
            message = (
                "There may be a short deadline. Contact a qualified local legal adviser or "
                "legal-aid service promptly, and do not ignore any notice or hearing date."
            )
            help_resources = []
        else:
            message = (
                "If you are in immediate danger, move to a safer place if possible and contact "
                "local emergency services or a trusted person now."
            )
            help_resources = (
                await list_student_help_resources(db, jurisdiction_code=jurisdiction.code, limit=20)
                if jurisdiction
                else []
            )
        resources = [
            AssistantUrgentResource(
                name=item.name,
                category=item.category,
                assistance_type=item.assistance_type,
                contact_method=item.contact_method,
                contact_url=item.contact_url,
                phone=item.phone,
                email=str(item.contact_email) if item.contact_email else None,
                jurisdiction=item.jurisdiction.name,
                source_title=item.source_title,
                source_url=item.source_url,
                verified_at=item.verified_at,
            )
            for item in help_resources
        ]
    elif response_status == AssistantStatus.REFUSE:
        error = AssistantErrorCode.UNSAFE_REQUEST
        message = (
            "I can’t help conceal, alter, or destroy evidence or provide a definitive "
            "legal verdict. "
            "I can offer general information about lawful next steps."
        )
    elif response_status == AssistantStatus.OUT_OF_SCOPE:
        error = AssistantErrorCode.OUT_OF_SCOPE
        message = "I can help with general legal awareness and student support topics."
    elif response_status == AssistantStatus.CLARIFY:
        message = (
            "Please provide a supported jurisdiction code so I can look for applicable, "
            "current guidance."
            if classification.jurisdiction_state
            in {JurisdictionState.REQUIRED, JurisdictionState.MISMATCH}
            else "I need a little more information before I can look for relevant guidance."
        )
        error = AssistantErrorCode.INVALID_REQUEST
    elif decision.provider_allowed:
        if jurisdiction is None:
            response_status = AssistantStatus.CLARIFY
            error = AssistantErrorCode.INVALID_REQUEST
            message = (
                "Please provide a supported jurisdiction code so I can look for "
                "applicable guidance."
            )
        else:
            candidates = await retrieve_governed_context(db, request)
            references = [candidate.reference_key for candidate in candidates]
            if not candidates:
                response_status = AssistantStatus.CLARIFY
                error = AssistantErrorCode.GROUNDING_FAILED
                failure = error
                message = (
                    "I could not find current approved guidance for that question and jurisdiction."
                )
                validation["retrieval_available"] = False
            else:
                try:
                    provider_request = ProviderRequest(
                        system_instructions=load_system_instructions(),
                        prompt_id=PROMPT_METADATA.prompt_id,
                        prompt_version=PROMPT_METADATA.version,
                        structured_input=request,
                        governed_context=candidates,
                        response_schema_version=PROMPT_METADATA.response_schema_version,
                        model_configuration={"temperature": "0", "response_format": "json"},
                        correlation_id=correlation_id,
                    )
                    generated = await provider.generate(provider_request)
                    provider_name = generated.provider_name
                    model_identifier = generated.model_identifier
                    if generated.finish_state != "complete":
                        raise GroundingValidationError("Provider response incomplete.")
                    if contains_definitive_claim(generated.content):
                        raise GroundingValidationError("Provider response has a definitive claim.")
                    sources = validate_provider_content(
                        generated.content, candidates, jurisdiction.code
                    )
                    response_status = generated.content.status
                    validation.update(
                        {"provider_complete": True, "grounded": True, "safe_claims": True}
                    )
                    result = AssistantResponse(
                        status=response_status,
                        classification=classification,
                        what_this_may_mean=generated.content.what_this_may_mean,
                        relevant_facts_or_dependencies=generated.content.relevant_facts_or_dependencies,
                        next_steps=generated.content.next_steps,
                        urgent_help=generated.content.urgent_help,
                        urgent_resources=[],
                        sources=sources,
                        limitations=generated.content.limitations,
                        uncertainty=generated.content.uncertainty,
                        escalation=generated.content.escalation,
                        trace=AssistantTrace(
                            correlation_id=correlation_id,
                            route=response_status,
                            risk_level=classification.risk_level,
                            risk_category=classification.category,
                            prompt_id=PROMPT_METADATA.prompt_id,
                            prompt_version=PROMPT_METADATA.version,
                            response_schema_version=PROMPT_METADATA.response_schema_version,
                            retrieval_version=RETRIEVAL_VERSION,
                            provider_name=provider_name,
                            model_identifier=model_identifier,
                            knowledge_references=references,
                            validation_outcomes=validation,
                            started_at=started,
                            completed_at=datetime.now(UTC),
                        ),
                    )
                    await _record_trace(db, actor_id, result, provider_name, model_identifier)
                    return result
                except ProviderUnavailableError:
                    response_status = AssistantStatus.PROVIDER_UNAVAILABLE
                    error = AssistantErrorCode.PROVIDER_UNAVAILABLE
                    failure = error
                    message = "The assistant is temporarily unavailable. Please try again later."
                    validation["provider_complete"] = False
                except Exception:
                    response_status = AssistantStatus.CLARIFY
                    error = AssistantErrorCode.GROUNDING_FAILED
                    failure = error
                    message = (
                        "I could not validate a safe, grounded response. Please try again later."
                    )
                    sources = []
                    validation["grounded"] = False

    result = _response(
        response_status,
        classification,
        correlation_id,
        started,
        message=message or "I could not complete this request safely.",
        error=error,
        sources=sources,
        resources=resources,
        provider_name=provider_name,
        model_identifier=model_identifier,
        knowledge_references=references,
        failure_category=failure,
        validation=validation,
    )
    await _record_trace(db, actor_id, result, provider_name, model_identifier)
    return result
