from __future__ import annotations

import re

from app.assistant.schemas import (
    AssistantIntent,
    AssistantRequest,
    JurisdictionState,
    RiskCategory,
    RiskLevel,
    SafetyClassification,
    Urgency,
)

_PATTERNS: tuple[tuple[RiskCategory, tuple[str, ...]], ...] = (
    (
        RiskCategory.IMMEDIATE_DANGER,
        (
            r"\bin immediate danger\b",
            r"\bunsafe right now\b",
            r"\bbreaking in\b",
            r"\bfollowing me now\b",
        ),
    ),
    (
        RiskCategory.SELF_HARM,
        (r"\bkill myself\b", r"\bend my life\b", r"\bsuicid(?:e|al)\b", r"\bself[- ]harm\b"),
    ),
    (
        RiskCategory.SEXUAL_VIOLENCE,
        (
            r"\bsexual(?:ly)? (?:assault|abuse|violence)\b",
            r"\braped?\b",
            r"\bnon[- ]consensual sex\b",
        ),
    ),
    (
        RiskCategory.CHILD_SAFETY,
        (
            r"\bchild (?:is being|being) abused\b",
            r"\bchild safety\b",
            r"\bminor (?:is being )?abused\b",
        ),
    ),
    (
        RiskCategory.THREATS,
        (r"\bthreaten(?:ed|ing|s)?\b", r"\bthreats? to (?:kill|hurt|harm)\b"),
    ),
    (
        RiskCategory.VIOLENCE,
        (
            r"\bviolence\b",
            r"\bphysical(?:ly)? (?:hit|hurt|attacked|assaulted)\b",
            r"\bbeing beaten\b",
        ),
    ),
    (
        RiskCategory.EXTORTION,
        (
            r"\bextort(?:ion|ed|ing)?\b",
            r"\bblackmail(?:ed|ing)?\b",
            r"\bpay or (?:they|he|she) will release\b",
        ),
    ),
    (
        RiskCategory.ACTIVE_FINANCIAL_FRAUD,
        (
            r"\b(?:money|funds) (?:is|are) being transferred right now\b",
            r"\bactive financial fraud\b",
            r"\bbank account (?:is )?being drained\b",
            r"\bcurrently transferring money without my consent\b",
        ),
    ),
    (
        RiskCategory.IMMINENT_DEADLINE,
        (
            r"\bdeadline (?:is )?(?:today|tomorrow|in \d+ days?)\b",
            r"\bhearing (?:is )?(?:today|tomorrow)\b",
            r"\brespond by tomorrow\b",
        ),
    ),
    (
        RiskCategory.EVIDENCE_CONCEALMENT,
        (
            r"\b(?:hide|destroy|delete|conceal|alter) (?:the )?(?:evidence|records|messages)\b",
            r"\bcover up (?:the )?(?:evidence|crime)\b",
        ),
    ),
    (
        RiskCategory.DEFINITIVE_VERDICT,
        (
            r"\bis (?:this|that|it) illegal\b",
            r"\bis this (?:definitely|certainly) (?:legal|illegal)\b",
            r"\bwill i definitely win\b",
            r"\bcan you guarantee\b",
            r"\bdefinitely unenforceable\b",
            r"\bdefinitely enforceable\b",
            r"\bguarantee (?:that|i will|you will)\b",
        ),
    ),
)

_LEGAL_SIGNALS = re.compile(
    r"\b(?:law|legal|rights?|tenant|landlord|rent|deposit|contract|clause|employment|salary|"
    r"internship|college|university|ragging|harass(?:ment|ed)|complaint|disciplin(?:ary|e)|"
    r"consumer|police|reporting|fraud|extortion|evidence|court|deadline|notice|agreement)\b",
    re.IGNORECASE,
)
_OUT_OF_SCOPE_SIGNALS = re.compile(
    r"\b(?:weather|recipe|football score|movie recommendation|debug my code|write code|"
    r"stock price|medical diagnosis)\b",
    re.IGNORECASE,
)


def classify_request(request: AssistantRequest) -> SafetyClassification:
    """Deterministic first-pass routing signals; this is not a complete safety classifier."""
    text = f"{request.message} {request.topic or ''}".casefold()
    category = RiskCategory.NONE
    for candidate, expressions in _PATTERNS:
        if any(re.search(expression, text, flags=re.IGNORECASE) for expression in expressions):
            category = candidate
            break

    if category in {
        RiskCategory.IMMEDIATE_DANGER,
        RiskCategory.THREATS,
        RiskCategory.VIOLENCE,
        RiskCategory.SEXUAL_VIOLENCE,
        RiskCategory.SELF_HARM,
        RiskCategory.CHILD_SAFETY,
        RiskCategory.EXTORTION,
        RiskCategory.ACTIVE_FINANCIAL_FRAUD,
    }:
        return SafetyClassification(
            intent=AssistantIntent.LEGAL_AWARENESS,
            urgency=Urgency.IMMEDIATE,
            risk_level=RiskLevel.CRITICAL,
            category=category,
            jurisdiction_state=(
                JurisdictionState.PROVIDED
                if request.jurisdiction
                else JurisdictionState.NOT_PROVIDED
            ),
            escalation_required=True,
            clarification_required=False,
        )

    if category == RiskCategory.IMMINENT_DEADLINE:
        return SafetyClassification(
            intent=AssistantIntent.LEGAL_AWARENESS,
            urgency=Urgency.SOON,
            risk_level=RiskLevel.HIGH,
            category=category,
            jurisdiction_state=(
                JurisdictionState.PROVIDED
                if request.jurisdiction
                else JurisdictionState.NOT_PROVIDED
            ),
            escalation_required=True,
            clarification_required=False,
        )

    if category == RiskCategory.EVIDENCE_CONCEALMENT:
        return SafetyClassification(
            intent=AssistantIntent.EVIDENCE_CONCEALMENT,
            urgency=Urgency.ROUTINE,
            risk_level=RiskLevel.HIGH,
            category=category,
            jurisdiction_state=(
                JurisdictionState.PROVIDED
                if request.jurisdiction
                else JurisdictionState.NOT_PROVIDED
            ),
            escalation_required=False,
            clarification_required=False,
        )

    if category == RiskCategory.DEFINITIVE_VERDICT:
        return SafetyClassification(
            intent=AssistantIntent.DEFINITIVE_VERDICT,
            urgency=Urgency.ROUTINE,
            risk_level=RiskLevel.ELEVATED,
            category=category,
            jurisdiction_state=(
                JurisdictionState.PROVIDED
                if request.jurisdiction
                else JurisdictionState.NOT_PROVIDED
            ),
            escalation_required=False,
            clarification_required=False,
        )

    has_legal_intent = bool(_LEGAL_SIGNALS.search(text))
    if not has_legal_intent or _OUT_OF_SCOPE_SIGNALS.search(text):
        return SafetyClassification(
            intent=AssistantIntent.OUT_OF_SCOPE,
            urgency=Urgency.ROUTINE,
            risk_level=RiskLevel.LOW,
            category=RiskCategory.UNSUPPORTED_TOPIC,
            jurisdiction_state=(
                JurisdictionState.PROVIDED
                if request.jurisdiction
                else JurisdictionState.NOT_PROVIDED
            ),
            escalation_required=False,
            clarification_required=False,
        )

    missing_jurisdiction = request.jurisdiction is None
    return SafetyClassification(
        intent=AssistantIntent.LEGAL_AWARENESS,
        urgency=Urgency.ROUTINE,
        risk_level=RiskLevel.LOW,
        category=(
            RiskCategory.JURISDICTION_REQUIRED if missing_jurisdiction else RiskCategory.NONE
        ),
        jurisdiction_state=(
            JurisdictionState.REQUIRED if missing_jurisdiction else JurisdictionState.PROVIDED
        ),
        escalation_required=False,
        clarification_required=missing_jurisdiction,
    )
