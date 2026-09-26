from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AssistantStatus(StrEnum):
    ANSWER = "answer"
    CLARIFY = "clarify"
    REFUSE = "refuse"
    ESCALATE = "escalate"
    OUT_OF_SCOPE = "out_of_scope"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    RETRIEVAL_UNAVAILABLE = "retrieval_unavailable"


class AssistantIntent(StrEnum):
    LEGAL_AWARENESS = "legal_awareness"
    DEFINITIVE_VERDICT = "definitive_verdict"
    EVIDENCE_CONCEALMENT = "evidence_concealment"
    OUT_OF_SCOPE = "out_of_scope"


class Urgency(StrEnum):
    ROUTINE = "routine"
    SOON = "soon"
    IMMEDIATE = "immediate"


class RiskLevel(StrEnum):
    LOW = "low"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


class RiskCategory(StrEnum):
    NONE = "none"
    IMMEDIATE_DANGER = "immediate_danger"
    THREATS = "threats"
    VIOLENCE = "violence"
    SEXUAL_VIOLENCE = "sexual_violence"
    SELF_HARM = "self_harm"
    CHILD_SAFETY = "child_safety"
    EXTORTION = "extortion"
    ACTIVE_FINANCIAL_FRAUD = "active_financial_fraud"
    IMMINENT_DEADLINE = "imminent_deadline"
    EVIDENCE_CONCEALMENT = "evidence_concealment"
    DEFINITIVE_VERDICT = "definitive_verdict"
    UNSUPPORTED_TOPIC = "unsupported_topic"
    JURISDICTION_REQUIRED = "jurisdiction_required"
    JURISDICTION_MISMATCH = "jurisdiction_mismatch"


class JurisdictionState(StrEnum):
    NOT_PROVIDED = "not_provided"
    PROVIDED = "provided"
    REQUIRED = "required"
    MISMATCH = "mismatch"


class AssistantErrorCode(StrEnum):
    INVALID_REQUEST = "ASSISTANT_INVALID_REQUEST"
    UNSAFE_REQUEST = "ASSISTANT_UNSAFE_REQUEST"
    OUT_OF_SCOPE = "ASSISTANT_OUT_OF_SCOPE"
    PROVIDER_UNAVAILABLE = "ASSISTANT_PROVIDER_UNAVAILABLE"
    GROUNDING_FAILED = "ASSISTANT_GROUNDING_FAILED"
    RESPONSE_INVALID = "ASSISTANT_RESPONSE_INVALID"
    RETRIEVAL_UNAVAILABLE = "ASSISTANT_RETRIEVAL_UNAVAILABLE"


class AssistantRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    message: str = Field(min_length=1, max_length=4000)
    jurisdiction: str | None = Field(default=None, min_length=2, max_length=32)
    topic: str | None = Field(default=None, max_length=120)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("Message cannot be blank.")
        return value

    @field_validator("jurisdiction")
    @classmethod
    def normalize_jurisdiction(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class SafetyClassification(BaseModel):
    intent: AssistantIntent
    urgency: Urgency
    risk_level: RiskLevel
    category: RiskCategory
    jurisdiction_state: JurisdictionState
    escalation_required: bool
    clarification_required: bool
    deterministic: Literal[True] = True


class SafetyGateDecision(BaseModel):
    route: AssistantStatus
    provider_allowed: bool
    reason: RiskCategory


class AssistantStep(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class AssistantProviderContent(BaseModel):
    """Constrained provider response. Claims are sectioned and citations are keys only."""

    model_config = ConfigDict(extra="forbid")

    status: Literal[AssistantStatus.ANSWER, AssistantStatus.CLARIFY]
    what_this_may_mean: str = Field(min_length=1, max_length=3000)
    relevant_facts_or_dependencies: list[str] = Field(default_factory=list, max_length=12)
    next_steps: list[AssistantStep] = Field(default_factory=list, max_length=8)
    urgent_help: str = Field(default="", max_length=1200)
    citation_keys: list[str] = Field(default_factory=list, max_length=8)
    limitations: list[str] = Field(min_length=1, max_length=8)
    uncertainty: str = Field(min_length=1, max_length=1200)
    escalation: str = Field(default="", max_length=1200)


class GroundingCandidate(BaseModel):
    """Internal metadata needed to validate retrieval before rendering citations."""

    model_config = ConfigDict(extra="forbid")

    reference_key: str
    knowledge_slug: str
    knowledge_version: int
    title: str
    content: str
    jurisdiction_code: str
    jurisdiction_name: str
    source_title: str
    source_url: str
    source_publisher: str | None = None
    source_citation: str | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    reviewed_at: datetime | None = None
    review_due_at: datetime | None = None
    publication_state: str
    item_status: str
    source_is_active: bool
    source_effective_from: datetime | None = None
    source_effective_until: datetime | None = None
    source_review_state: str | None = None
    chunk_id: str | None = None
    section_key: str | None = None
    retrieval_methods: list[Literal["fts", "vector"]] = Field(default_factory=list)
    lexical_score: float = 0.0
    vector_score: float = 0.0
    hybrid_score: float = 0.0
    retrieval_config_version: str | None = None


class AssistantSource(BaseModel):
    title: str
    url: str
    citation: str | None = None
    jurisdiction: str
    effective_from: datetime | None = None
    last_reviewed_at: datetime | None = None
    review_due_at: datetime | None = None
    knowledge_reference: str


class AssistantUrgentResource(BaseModel):
    name: str
    category: str
    assistance_type: str
    contact_method: str
    contact_url: str | None = None
    phone: str | None = None
    email: str | None = None
    jurisdiction: str
    source_title: str
    source_url: str
    verified_at: datetime


class AssistantTrace(BaseModel):
    correlation_id: uuid.UUID
    route: AssistantStatus
    risk_level: RiskLevel
    risk_category: RiskCategory
    prompt_id: str
    prompt_version: str
    response_schema_version: str
    retrieval_version: str
    embedding_model: str | None = None
    retrieval_state: str = "not_run"
    provider_name: str | None = None
    model_identifier: str | None = None
    knowledge_references: list[str] = Field(default_factory=list)
    validation_outcomes: dict[str, bool] = Field(default_factory=dict)
    failure_category: AssistantErrorCode | None = None
    provider_status: str | None = None
    provider_latency_ms: int | None = Field(default=None, ge=0)
    started_at: datetime
    completed_at: datetime


class AssistantResponse(BaseModel):
    status: AssistantStatus
    classification: SafetyClassification
    what_this_may_mean: str
    relevant_facts_or_dependencies: list[str]
    next_steps: list[AssistantStep]
    urgent_help: str
    urgent_resources: list[AssistantUrgentResource]
    sources: list[AssistantSource]
    limitations: list[str]
    uncertainty: str
    escalation: str
    error_code: AssistantErrorCode | None = None
    trace: AssistantTrace


class AssistantErrorEnvelope(BaseModel):
    code: AssistantErrorCode
    message: str


class AssistantErrorResponse(BaseModel):
    error: AssistantErrorEnvelope


class ProviderRequest(BaseModel):
    system_instructions: str
    prompt_id: str
    prompt_version: str
    structured_input: AssistantRequest
    governed_context: list[GroundingCandidate]
    response_schema_version: str
    model_configuration: dict[str, str]
    retrieval_config_version: str = ""
    correlation_id: uuid.UUID


class ProviderResponse(BaseModel):
    content: AssistantProviderContent
    provider_name: str
    model_identifier: str | None = None
    request_metadata: dict[str, str] = Field(default_factory=dict)
    latency_ms: int | None = Field(default=None, ge=0)
    finish_state: Literal["complete", "truncated", "blocked"] = "complete"
    failure_category: AssistantErrorCode | None = None
