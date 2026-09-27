from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role, verify_csrf_protection
from app.db.models import (
    AuditEvent,
    ComplaintGuideVersion,
    Document,
    DocumentProcessingJob,
    HelpResource,
    KnowledgeVersion,
    PublicationState,
    ResourceStatus,
    User,
)
from app.db.session import get_db_session

router = APIRouter(prefix="/admin/operations", tags=["admin operations"])
LIMIT = 100


class TriageItem(BaseModel):
    id: str
    category: str
    status: str
    created_at: datetime
    label: str | None = None


class OperationsOverview(BaseModel):
    stale_content: list[TriageItem]
    failed_analyses: list[TriageItem]
    provider_errors: list[TriageItem]
    user_reports: list[TriageItem]
    unresolved_feedback: list[TriageItem]


async def _resolved_ids(db: AsyncSession, request_ids: list[str]) -> set[str]:
    if not request_ids:
        return set()
    values = await db.scalars(
        select(AuditEvent.request_id).where(
            AuditEvent.action == "assistant.feedback.resolved",
            AuditEvent.request_id.in_(request_ids),
        )
    )
    return {value for value in values if value}


@router.get("", response_model=OperationsOverview)
async def operations_overview(
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db_session),
) -> OperationsOverview:
    """Return bounded operational queues with no user or document content."""
    now = datetime.now(UTC)
    knowledge = await db.scalars(
        select(KnowledgeVersion)
        .where(
            KnowledgeVersion.publication_state == PublicationState.PUBLISHED,
            KnowledgeVersion.review_due_at <= now,
        )
        .order_by(KnowledgeVersion.review_due_at.asc())
        .limit(LIMIT)
    )
    guides = await db.scalars(
        select(ComplaintGuideVersion)
        .where(
            ComplaintGuideVersion.publication_state == PublicationState.PUBLISHED,
            ComplaintGuideVersion.review_due_at <= now,
        )
        .order_by(ComplaintGuideVersion.review_due_at.asc())
        .limit(LIMIT)
    )
    resources = await db.scalars(
        select(HelpResource)
        .where(
            HelpResource.status == ResourceStatus.ACTIVE,
            or_(HelpResource.verification_due_at <= now, HelpResource.expires_at <= now),
        )
        .order_by(HelpResource.verification_due_at.asc())
        .limit(LIMIT)
    )
    jobs = await db.execute(
        select(DocumentProcessingJob, Document)
        .join(Document, Document.id == DocumentProcessingJob.document_id)
        .where(DocumentProcessingJob.status == "failed", Document.deleted_at.is_(None))
        .order_by(DocumentProcessingJob.updated_at.desc())
        .limit(LIMIT)
    )
    events = await db.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.action == "assistant.request.completed",
            AuditEvent.details["failure_category"].as_string().is_not(None),
        )
        .order_by(AuditEvent.occurred_at.desc())
        .limit(LIMIT)
    )
    feedback = await db.scalars(
        select(AuditEvent)
        .where(AuditEvent.action == "assistant.feedback.submitted")
        .order_by(AuditEvent.occurred_at.desc())
        .limit(LIMIT)
    )
    feedback_rows = list(feedback)
    resolved = await _resolved_ids(db, [row.request_id for row in feedback_rows if row.request_id])

    stale = (
        [
            TriageItem(
                id=str(row.id),
                category="knowledge",
                status="review_due",
                created_at=row.review_due_at or row.updated_at,
                label=row.title,
            )
            for row in knowledge
        ]
        + [
            TriageItem(
                id=str(row.id),
                category="complaint_guide",
                status="review_due",
                created_at=row.review_due_at or row.updated_at,
                label=row.title,
            )
            for row in guides
        ]
        + [
            TriageItem(
                id=str(row.id),
                category="help_resource",
                status="verification_due",
                created_at=row.verification_due_at or row.updated_at,
                label=row.name,
            )
            for row in resources
        ]
    )
    failed = [
        TriageItem(
            id=str(job.id),
            category="document_analysis",
            status=job.failure_code or "failed",
            created_at=job.updated_at,
        )
        for job, _document in jobs
    ]
    provider_errors = [
        TriageItem(
            id=str(event.id),
            category=str((event.details or {}).get("failure_category") or "provider_error"),
            status=str((event.details or {}).get("provider_status") or "failed"),
            created_at=event.occurred_at,
        )
        for event in events
    ]
    user_reports = []
    unresolved = []
    for event in feedback_rows:
        details = event.details or {}
        request_id = event.request_id or ""
        if request_id in resolved:
            continue
        item = TriageItem(
            id=request_id,
            category=str(details.get("rating") or "feedback"),
            status="reported" if details.get("reported") else "needs_review",
            created_at=event.occurred_at,
        )
        unresolved.append(item)
        if details.get("reported"):
            user_reports.append(item)
    return OperationsOverview(
        stale_content=stale[:LIMIT],
        failed_analyses=failed,
        provider_errors=provider_errors,
        user_reports=user_reports,
        unresolved_feedback=unresolved,
    )


@router.post(
    "/feedback/{request_id}/resolve",
    status_code=204,
    dependencies=[Depends(verify_csrf_protection)],
)
async def resolve_feedback(
    request_id: uuid.UUID,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    feedback = await db.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "assistant.feedback.submitted",
            AuditEvent.request_id == str(request_id),
        )
    )
    if feedback is None:
        raise HTTPException(status_code=404, detail="Feedback item not found.")
    already_resolved = await db.scalar(
        select(AuditEvent.id).where(
            AuditEvent.action == "assistant.feedback.resolved",
            AuditEvent.request_id == str(request_id),
        )
    )
    if already_resolved is None:
        db.add(
            AuditEvent(
                action="assistant.feedback.resolved",
                resource_type="assistant_response",
                actor_id=_admin.id,
                request_id=str(request_id),
                details={"resolution": "reviewed"},
            )
        )
        await db.commit()
