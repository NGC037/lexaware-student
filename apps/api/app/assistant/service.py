from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
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
from app.knowledge.rag.config import RetrievalConfig
from app.knowledge.rag.embeddings import EmbeddingProvider, EmbeddingProviderError
from app.knowledge.rag.retrieval import RetrievalState

RETRIEVAL_VERSION = RetrievalConfig().version


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
    retrieval_state: str = "not_run",
    retrieval_version: str = RETRIEVAL_VERSION,
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
            retrieval_version=retrieval_version,
            retrieval_state=retrieval_state,
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
            "retrieval_state": trace.retrieval_state,
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
    embedding_provider: EmbeddingProvider,
    retrieval_config: RetrievalConfig | None = None,
) -> AssistantResponse:
    started = datetime.now(UTC)
    selected_retrieval_config = retrieval_config or RetrievalConfig()
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
    retrieval_state = "not_run"
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
        if classification.jurisdiction_state in {
            JurisdictionState.REQUIRED,
            JurisdictionState.MISMATCH,
        }:
            retrieval_state = "jurisdiction_required"
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
            retrieval_state = "jurisdiction_required"
            message = (
                "Please provide a supported jurisdiction code so I can look for "
                "applicable guidance."
            )
        else:
            try:
                retrieval = await retrieve_governed_context(
                    db, request, embedding_provider, selected_retrieval_config
                )
            except EmbeddingProviderError, SQLAlchemyError:
                retrieval_state = "failure"
                response_status = AssistantStatus.RETRIEVAL_UNAVAILABLE
                error = AssistantErrorCode.RETRIEVAL_UNAVAILABLE
                failure = error
                message = "Current guidance could not be searched safely. Please try again later."
                validation["retrieval_available"] = False
                retrieval = None
            if retrieval is None:
                candidates = []
            else:
                retrieval_state = retrieval.state.value
                candidates = [candidate.grounding for candidate in retrieval.candidates]
            references = [candidate.reference_key for candidate in candidates]
            if retrieval is not None and retrieval.state == RetrievalState.JURISDICTION_REQUIRED:
                retrieval_state = "jurisdiction_required"
                response_status = AssistantStatus.CLARIFY
                error = AssistantErrorCode.INVALID_REQUEST
                message = (
                    "Please provide a supported jurisdiction code so I can look for applicable "
                    "guidance."
                )
            elif retrieval is not None and not candidates:
                response_status = AssistantStatus.CLARIFY
                error = AssistantErrorCode.GROUNDING_FAILED
                failure = error
                message = (
                    "I could not find current approved guidance for that question and jurisdiction."
                )
                validation["retrieval_available"] = True
            elif retrieval is not None:
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
                            retrieval_version=selected_retrieval_config.version,
                            retrieval_state="grounded",
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
        retrieval_state=retrieval_state,
        retrieval_version=selected_retrieval_config.version,
    )
    await _record_trace(db, actor_id, result, provider_name, model_identifier)
    return result
