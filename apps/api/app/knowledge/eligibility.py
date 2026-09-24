"""Canonical SQL boundary for student-visible governed knowledge."""

from datetime import UTC, datetime

from sqlalchemy import or_
from sqlalchemy.sql.elements import ColumnElement

from app.db.models import KnowledgeItem, KnowledgeStatus, KnowledgeVersion, PublicationState, Source


def student_knowledge_eligibility(now: datetime | None = None) -> tuple[ColumnElement[bool], ...]:
    current = now or datetime.now(UTC)
    return (
        KnowledgeItem.status == KnowledgeStatus.ACTIVE,
        KnowledgeVersion.publication_state == PublicationState.PUBLISHED,
        KnowledgeVersion.reviewed_at.is_not(None),
        KnowledgeVersion.reviewed_by_id.is_not(None),
        Source.jurisdiction_id == KnowledgeItem.jurisdiction_id,
        or_(KnowledgeVersion.review_due_at.is_(None), KnowledgeVersion.review_due_at > current),
        Source.is_active.is_(True),
        or_(Source.effective_from.is_(None), Source.effective_from <= current),
        or_(Source.effective_until.is_(None), Source.effective_until > current),
        or_(KnowledgeVersion.effective_from.is_(None), KnowledgeVersion.effective_from <= current),
        or_(
            KnowledgeVersion.effective_until.is_(None), KnowledgeVersion.effective_until >= current
        ),
    )
