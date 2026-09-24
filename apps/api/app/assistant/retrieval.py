from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.schemas import AssistantRequest, GroundingCandidate
from app.knowledge.service import get_student_article_by_slug, get_student_articles


async def retrieve_governed_context(
    db: AsyncSession, request: AssistantRequest
) -> list[GroundingCandidate]:
    # The optional topic is metadata and may be a sensitive free-form label; search only
    # the user message and never retain either value beyond this request.
    query = request.message
    articles = await get_student_articles(
        db, jurisdiction_code=request.jurisdiction, query=query, limit=5, offset=0
    )
    candidates: list[GroundingCandidate] = []
    for article in articles:
        detail = await get_student_article_by_slug(db, article.slug)
        if detail is None or not detail.reviewed_by_present:
            continue
        candidates.append(
            GroundingCandidate(
                reference_key=f"knowledge:{detail.slug}:v{detail.version_number}",
                knowledge_slug=detail.slug,
                knowledge_version=detail.version_number,
                title=detail.title,
                content="\n\n".join(
                    part
                    for part in (
                        detail.summary or "",
                        detail.content,
                        detail.applicability_notes or "",
                        detail.escalation_guidance or "",
                    )
                    if part
                ),
                jurisdiction_code=detail.jurisdiction.code,
                jurisdiction_name=detail.jurisdiction.name,
                source_title=detail.source.title,
                source_url=detail.source.source_url,
                source_publisher=detail.source.publisher,
                source_citation=detail.source.citation,
                effective_from=detail.effective_from,
                effective_until=detail.version_effective_until,
                reviewed_at=detail.last_reviewed_at,
                review_due_at=detail.review_due_at,
                publication_state=detail.publication_state,
                item_status=detail.item_status,
                source_is_active=detail.source.is_active,
                source_effective_from=detail.source.effective_from,
                source_effective_until=detail.source.effective_until,
            )
        )
    return candidates
