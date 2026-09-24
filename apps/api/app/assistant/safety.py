from __future__ import annotations

from app.assistant.schemas import (
    AssistantIntent,
    AssistantStatus,
    RiskCategory,
    SafetyClassification,
    SafetyGateDecision,
)


def select_route(classification: SafetyClassification) -> SafetyGateDecision:
    """Pure safety gate; urgent cases take precedence over jurisdiction clarification."""
    if classification.escalation_required:
        return SafetyGateDecision(
            route=AssistantStatus.ESCALATE,
            provider_allowed=False,
            reason=classification.category,
        )
    if classification.category == RiskCategory.EVIDENCE_CONCEALMENT:
        return SafetyGateDecision(
            route=AssistantStatus.REFUSE,
            provider_allowed=False,
            reason=classification.category,
        )
    if classification.intent == AssistantIntent.DEFINITIVE_VERDICT:
        return SafetyGateDecision(
            route=AssistantStatus.REFUSE,
            provider_allowed=False,
            reason=RiskCategory.DEFINITIVE_VERDICT,
        )
    if classification.intent == AssistantIntent.OUT_OF_SCOPE:
        return SafetyGateDecision(
            route=AssistantStatus.OUT_OF_SCOPE,
            provider_allowed=False,
            reason=RiskCategory.UNSUPPORTED_TOPIC,
        )
    if classification.clarification_required:
        return SafetyGateDecision(
            route=AssistantStatus.CLARIFY,
            provider_allowed=False,
            reason=classification.category,
        )
    return SafetyGateDecision(
        route=AssistantStatus.ANSWER,
        provider_allowed=True,
        reason=classification.category,
    )
