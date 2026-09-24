from __future__ import annotations

import re
from datetime import UTC, datetime

from app.assistant.schemas import AssistantProviderContent, AssistantSource, GroundingCandidate


class GroundingValidationError(ValueError):
    pass


_DEFINITIVE_PATTERNS = re.compile(
    r"\b(?:this is (?:definitely|certainly) illegal|you will definitely win|"
    r"guaranteed? (?:to win|legal|illegal)|definitely (?:legal|illegal|unenforceable))\b",
    re.IGNORECASE,
)


def is_current_candidate(candidate: GroundingCandidate, now: datetime | None = None) -> bool:
    current = now or datetime.now(UTC)
    return all(
        (
            candidate.publication_state == "published",
            candidate.item_status == "active",
            candidate.source_is_active,
            candidate.reviewed_at is not None,
            candidate.review_due_at is None or candidate.review_due_at > current,
            candidate.effective_from is None or candidate.effective_from <= current,
            candidate.effective_until is None or candidate.effective_until > current,
            candidate.source_effective_from is None or candidate.source_effective_from <= current,
            candidate.source_effective_until is None or candidate.source_effective_until > current,
        )
    )


def validate_provider_content(
    content: AssistantProviderContent,
    candidates: list[GroundingCandidate],
    jurisdiction_code: str,
    now: datetime | None = None,
) -> list[AssistantSource]:
    if not candidates:
        raise GroundingValidationError("No governed sources are available.")
    keyed = {candidate.reference_key: candidate for candidate in candidates}
    if not content.citation_keys:
        raise GroundingValidationError("The response has no citations.")
    if len(content.citation_keys) != len(set(content.citation_keys)):
        raise GroundingValidationError("The response contains duplicate citations.")
    if any(key not in keyed for key in content.citation_keys):
        raise GroundingValidationError("The response cites an unknown reference.")

    now = now or datetime.now(UTC)
    sources: list[AssistantSource] = []
    for key in content.citation_keys:
        candidate = keyed[key]
        if not is_current_candidate(candidate, now):
            raise GroundingValidationError("The response cites stale or unpublished content.")
        if candidate.jurisdiction_code.casefold() != jurisdiction_code.casefold():
            raise GroundingValidationError("The response cites content from another jurisdiction.")
        sources.append(
            AssistantSource(
                title=candidate.source_title,
                url=candidate.source_url,
                citation=candidate.source_citation,
                jurisdiction=candidate.jurisdiction_name,
                effective_from=candidate.effective_from,
                last_reviewed_at=candidate.reviewed_at,
                review_due_at=candidate.review_due_at,
                knowledge_reference=f"{candidate.knowledge_slug}:v{candidate.knowledge_version}",
            )
        )
    return sources


def contains_definitive_claim(content: AssistantProviderContent) -> bool:
    fields = [
        content.what_this_may_mean,
        content.urgent_help,
        content.uncertainty,
        content.escalation,
        *(step.text for step in content.next_steps),
        *content.relevant_facts_or_dependencies,
        *content.limitations,
    ]
    return any(_DEFINITIVE_PATTERNS.search(value) for value in fields)
