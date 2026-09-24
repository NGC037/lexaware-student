import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.service import record_audit_event
from app.complaints.schemas import (
    ComplaintGuideAdminRead,
    ComplaintGuideCreate,
    ComplaintGuideRead,
    ComplaintGuideUpdate,
    ComplaintGuideVersionAdminRead,
    ComplaintGuideVersionCreate,
    GuidanceStep,
    GuideReviewDecision,
    JurisdictionSummary,
)
from app.db.models import (
    ComplaintGuide,
    ComplaintGuideVersion,
    Jurisdiction,
    KnowledgeStatus,
    PublicationState,
)

_REQUIRED_SECTIONS = {
    "immediate_safety",
    "safety_considerations",
    "preserve_evidence",
    "reporting_options",
    "information_to_prepare",
    "checklist",
    "escalation",
}


def _steps_json(steps: list[GuidanceStep]) -> list[dict[str, object]]:
    return [step.model_dump() for step in sorted(steps, key=lambda step: step.position)]


def _validate_complete_sequence(steps: list[dict[str, object]]) -> None:
    sections = [step.get("section") for step in steps]
    missing = _REQUIRED_SECTIONS.difference(sections)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=("Guide needs safety, reporting, checklist, and escalation guidance sections."),
        )
    positions = [int(str(step["position"])) for step in steps]
    ordered = [
        step for _, step in sorted(zip(positions, steps, strict=True), key=lambda pair: pair[0])
    ]
    if positions != list(range(1, len(positions) + 1)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Guidance positions must be sequential, starting at 1.",
        )
    if ordered[0].get("section") != "immediate_safety":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Immediate safety guidance must be the first step.",
        )
    if ordered[-1].get("section") != "escalation":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Escalation guidance must be the final step.",
        )


def _validate_publish_window(version: ComplaintGuideVersion, now: datetime) -> None:
    if version.effective_until is not None and version.effective_until < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expired guidance cannot be published.",
        )
    if version.effective_from and version.effective_until:
        if version.effective_until < version.effective_from:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The effective-until date must not precede the effective-from date.",
            )
    if version.review_due_at is None or version.review_due_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A future review date is required before publication.",
        )


def _guide_read(
    guide: ComplaintGuide, version: ComplaintGuideVersion, jurisdiction: Jurisdiction
) -> ComplaintGuideRead:
    assert version.reviewed_at is not None
    return ComplaintGuideRead(
        id=guide.id,
        slug=guide.slug,
        version_number=version.version_number,
        title=version.title,
        category=version.category,
        audience=version.audience,
        short_description=version.short_description,
        jurisdiction=JurisdictionSummary(
            id=jurisdiction.id, code=jurisdiction.code, name=jurisdiction.name
        ),
        guidance_steps=[GuidanceStep.model_validate(step) for step in version.guidance_steps],
        reviewed_at=version.reviewed_at,
    )


async def _require_jurisdiction(db: AsyncSession, jurisdiction_id: uuid.UUID) -> None:
    if await db.get(Jurisdiction, jurisdiction_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jurisdiction not found.")


def _version_from_content(
    guide_id: uuid.UUID,
    version_number: int,
    content: ComplaintGuideCreate | ComplaintGuideVersionCreate,
) -> ComplaintGuideVersion:
    return ComplaintGuideVersion(
        guide_id=guide_id,
        version_number=version_number,
        title=content.title.strip(),
        category=content.category.strip().lower(),
        jurisdiction_id=content.jurisdiction_id,
        audience=content.audience.strip().lower(),
        short_description=content.short_description.strip(),
        guidance_steps=_steps_json(content.guidance_steps),
        publication_state=PublicationState.DRAFT,
        effective_from=content.effective_from,
        effective_until=content.effective_until,
        review_due_at=content.review_due_at,
        change_summary=content.change_summary.strip() if content.change_summary else None,
    )


async def create_complaint_guide(
    db: AsyncSession, actor_id: uuid.UUID, req: ComplaintGuideCreate
) -> ComplaintGuideAdminRead:
    await _require_jurisdiction(db, req.jurisdiction_id)
    normalized_slug = req.slug.strip().lower()
    if (
        await db.execute(select(ComplaintGuide.id).where(ComplaintGuide.slug == normalized_slug))
    ).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A guide with this slug already exists.")
    guide = ComplaintGuide(slug=normalized_slug, status=KnowledgeStatus.ACTIVE)
    db.add(guide)
    await db.flush()
    version = _version_from_content(guide.id, 1, req)
    db.add(version)
    await db.flush()
    await record_audit_event(
        db,
        action="complaint.guide.created",
        resource_type="complaint_guide",
        resource_id=guide.id,
        actor_id=actor_id,
        details={"slug": guide.slug, "category": version.category},
    )
    await record_audit_event(
        db,
        action="complaint.guide.version.created",
        resource_type="complaint_guide_version",
        resource_id=version.id,
        actor_id=actor_id,
        details={"guide_id": str(guide.id), "version_number": version.version_number},
    )
    await db.commit()
    return await get_admin_complaint_guide(db, guide.id)


async def create_complaint_guide_version(
    db: AsyncSession,
    actor_id: uuid.UUID,
    guide_id: uuid.UUID,
    req: ComplaintGuideVersionCreate,
) -> ComplaintGuideVersionAdminRead:
    stmt = (
        select(ComplaintGuide)
        .where(ComplaintGuide.id == guide_id)
        .options(selectinload(ComplaintGuide.versions))
    )
    guide = (await db.execute(stmt)).scalar_one_or_none()
    if guide is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Complaint guide not found."
        )
    if guide.status != KnowledgeStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Guide is archived.")
    if any(
        version.publication_state in (PublicationState.DRAFT, PublicationState.IN_REVIEW)
        for version in guide.versions
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Complete or reject the existing draft before creating another.",
        )
    await _require_jurisdiction(db, req.jurisdiction_id)
    version_number = max((version.version_number for version in guide.versions), default=0) + 1
    version = _version_from_content(guide.id, version_number, req)
    db.add(version)
    await db.flush()
    await record_audit_event(
        db,
        action="complaint.guide.version.created",
        resource_type="complaint_guide_version",
        resource_id=version.id,
        actor_id=actor_id,
        details={"guide_id": str(guide.id), "version_number": version.version_number},
    )
    await db.commit()
    await db.refresh(version)
    return _version_admin_read(version)


def _version_admin_read(version: ComplaintGuideVersion) -> ComplaintGuideVersionAdminRead:
    return ComplaintGuideVersionAdminRead(
        id=version.id,
        version_number=version.version_number,
        title=version.title,
        category=version.category,
        jurisdiction_id=version.jurisdiction_id,
        audience=version.audience,
        short_description=version.short_description,
        guidance_steps=[GuidanceStep.model_validate(step) for step in version.guidance_steps],
        publication_state=version.publication_state.value,
        effective_from=version.effective_from,
        effective_until=version.effective_until,
        reviewed_at=version.reviewed_at,
        published_at=version.published_at,
        review_due_at=version.review_due_at,
        change_summary=version.change_summary,
        created_at=version.created_at,
        updated_at=version.updated_at,
    )


async def get_admin_complaint_guide(
    db: AsyncSession, guide_id: uuid.UUID
) -> ComplaintGuideAdminRead:
    stmt = (
        select(ComplaintGuide)
        .where(ComplaintGuide.id == guide_id)
        .options(selectinload(ComplaintGuide.versions))
    )
    guide = (await db.execute(stmt)).scalar_one_or_none()
    if guide is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Complaint guide not found."
        )
    return ComplaintGuideAdminRead(
        id=guide.id,
        slug=guide.slug,
        status=guide.status.value,
        versions=[_version_admin_read(version) for version in guide.versions],
        created_at=guide.created_at,
        updated_at=guide.updated_at,
    )


async def list_admin_complaint_guides(db: AsyncSession) -> list[ComplaintGuideAdminRead]:
    guides = (
        (await db.execute(select(ComplaintGuide).order_by(ComplaintGuide.slug))).scalars().all()
    )
    return [await get_admin_complaint_guide(db, guide.id) for guide in guides]


async def update_complaint_guide_draft(
    db: AsyncSession, actor_id: uuid.UUID, version_id: uuid.UUID, req: ComplaintGuideUpdate
) -> ComplaintGuideVersionAdminRead:
    version = await db.get(ComplaintGuideVersion, version_id)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Complaint guide version not found."
        )
    if version.publication_state != PublicationState.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft guide versions can be edited.",
        )
    changes = req.model_dump(exclude_unset=True)
    jurisdiction_id = changes.get("jurisdiction_id")
    if jurisdiction_id is not None:
        await _require_jurisdiction(db, jurisdiction_id)
    if "guidance_steps" in changes and changes["guidance_steps"] is not None:
        typed_steps = [GuidanceStep.model_validate(step) for step in changes["guidance_steps"]]
        changes["guidance_steps"] = _steps_json(typed_steps)
    for key, value in changes.items():
        if key in {"category", "audience"} and value is not None:
            value = value.strip().lower()
        elif key in {"title", "short_description", "change_summary"} and value is not None:
            value = value.strip()
        setattr(version, key, value)
    await record_audit_event(
        db,
        action="complaint.guide.version.updated",
        resource_type="complaint_guide_version",
        resource_id=version.id,
        actor_id=actor_id,
        details={"version_number": version.version_number},
    )
    await db.commit()
    await db.refresh(version)
    return _version_admin_read(version)


async def submit_complaint_guide_for_review(
    db: AsyncSession, actor_id: uuid.UUID, version_id: uuid.UUID
) -> ComplaintGuideVersionAdminRead:
    version = await db.get(ComplaintGuideVersion, version_id)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Complaint guide version not found."
        )
    if version.publication_state != PublicationState.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only draft guides can be submitted."
        )
    _validate_complete_sequence(version.guidance_steps)
    version.publication_state = PublicationState.IN_REVIEW
    await record_audit_event(
        db,
        action="complaint.guide.version.submitted_review",
        resource_type="complaint_guide_version",
        resource_id=version.id,
        actor_id=actor_id,
        details={"version_number": version.version_number},
    )
    await db.commit()
    await db.refresh(version)
    return _version_admin_read(version)


async def review_complaint_guide(
    db: AsyncSession,
    actor_id: uuid.UUID,
    version_id: uuid.UUID,
    req: GuideReviewDecision,
) -> ComplaintGuideVersionAdminRead:
    version = await db.get(ComplaintGuideVersion, version_id)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Complaint guide version not found."
        )
    if version.publication_state != PublicationState.IN_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only guides in review can receive a review decision.",
        )
    if req.decision == "approve":
        version.publication_state = PublicationState.APPROVED
        version.reviewed_at = datetime.now(UTC)
        version.reviewed_by_id = actor_id
        action = "complaint.guide.version.approved"
    else:
        version.publication_state = PublicationState.DRAFT
        version.reviewed_at = None
        version.reviewed_by_id = None
        action = "complaint.guide.version.rejected"
    await record_audit_event(
        db,
        action=action,
        resource_type="complaint_guide_version",
        resource_id=version.id,
        actor_id=actor_id,
        details={"version_number": version.version_number},
    )
    await db.commit()
    await db.refresh(version)
    return _version_admin_read(version)


async def publish_complaint_guide(
    db: AsyncSession, actor_id: uuid.UUID, version_id: uuid.UUID
) -> ComplaintGuideVersionAdminRead:
    version = await db.get(ComplaintGuideVersion, version_id)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Complaint guide version not found."
        )
    if version.publication_state != PublicationState.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only approved guides can be published."
        )
    if version.reviewed_at is None or version.reviewed_by_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formal review is required for publication.",
        )
    now = datetime.now(UTC)
    _validate_publish_window(version, now)
    _validate_complete_sequence(version.guidance_steps)

    guide = await db.get(ComplaintGuide, version.guide_id)
    if guide is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Complaint guide not found."
        )
    if guide.status != KnowledgeStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Archived guides cannot be published."
        )

    published_versions = (
        await db.execute(
            select(ComplaintGuideVersion).where(
                ComplaintGuideVersion.guide_id == guide.id,
                ComplaintGuideVersion.publication_state == PublicationState.PUBLISHED,
            )
        )
    ).scalars()
    for previous in published_versions:
        previous.publication_state = PublicationState.SUPERSEDED
        await record_audit_event(
            db,
            action="complaint.guide.version.superseded",
            resource_type="complaint_guide_version",
            resource_id=previous.id,
            actor_id=actor_id,
            details={"superseded_by_version": version.version_number},
        )
    version.publication_state = PublicationState.PUBLISHED
    version.published_at = now
    version.published_by_id = actor_id
    await record_audit_event(
        db,
        action="complaint.guide.version.published",
        resource_type="complaint_guide_version",
        resource_id=version.id,
        actor_id=actor_id,
        details={"guide_id": str(guide.id), "version_number": version.version_number},
    )
    await db.commit()
    await db.refresh(version)
    return _version_admin_read(version)


async def unpublish_complaint_guide_version(
    db: AsyncSession, actor_id: uuid.UUID, version_id: uuid.UUID
) -> ComplaintGuideVersionAdminRead:
    version = await db.get(ComplaintGuideVersion, version_id)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Complaint guide version not found."
        )
    if version.publication_state != PublicationState.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only published guides can be unpublished.",
        )
    version.publication_state = PublicationState.ARCHIVED
    await record_audit_event(
        db,
        action="complaint.guide.version.unpublished",
        resource_type="complaint_guide_version",
        resource_id=version.id,
        actor_id=actor_id,
        details={"version_number": version.version_number},
    )
    await db.commit()
    await db.refresh(version)
    return _version_admin_read(version)


async def archive_complaint_guide(
    db: AsyncSession, actor_id: uuid.UUID, guide_id: uuid.UUID
) -> None:
    guide = await db.get(ComplaintGuide, guide_id)
    if guide is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Complaint guide not found."
        )
    guide.status = KnowledgeStatus.ARCHIVED
    active_versions = (
        await db.execute(
            select(ComplaintGuideVersion).where(
                ComplaintGuideVersion.guide_id == guide.id,
                ComplaintGuideVersion.publication_state.in_(
                    (
                        PublicationState.DRAFT,
                        PublicationState.IN_REVIEW,
                        PublicationState.APPROVED,
                        PublicationState.PUBLISHED,
                    )
                ),
            )
        )
    ).scalars()
    for version in active_versions:
        version.publication_state = PublicationState.ARCHIVED
        await record_audit_event(
            db,
            action="complaint.guide.version.archived",
            resource_type="complaint_guide_version",
            resource_id=version.id,
            actor_id=actor_id,
            details={"version_number": version.version_number},
        )
    await record_audit_event(
        db,
        action="complaint.guide.archived",
        resource_type="complaint_guide",
        resource_id=guide.id,
        actor_id=actor_id,
        details={"status": "archived"},
    )
    await db.commit()


async def list_student_complaint_guides(
    db: AsyncSession,
    category: str | None = None,
    jurisdiction_code: str | None = None,
    audience: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _slug: str | None = None,
) -> list[ComplaintGuideRead]:
    now = datetime.now(UTC)
    stmt = (
        select(ComplaintGuide, ComplaintGuideVersion, Jurisdiction)
        .join(ComplaintGuideVersion, ComplaintGuide.id == ComplaintGuideVersion.guide_id)
        .join(Jurisdiction, ComplaintGuideVersion.jurisdiction_id == Jurisdiction.id)
        .where(
            ComplaintGuide.status == KnowledgeStatus.ACTIVE,
            ComplaintGuideVersion.publication_state == PublicationState.PUBLISHED,
            ComplaintGuideVersion.reviewed_at.is_not(None),
            ComplaintGuideVersion.reviewed_by_id.is_not(None),
            ComplaintGuideVersion.review_due_at >= now,
            or_(
                ComplaintGuideVersion.effective_from.is_(None),
                ComplaintGuideVersion.effective_from <= now,
            ),
            or_(
                ComplaintGuideVersion.effective_until.is_(None),
                ComplaintGuideVersion.effective_until >= now,
            ),
        )
    )
    if category:
        stmt = stmt.where(ComplaintGuideVersion.category == category.strip().lower())
    if jurisdiction_code:
        stmt = stmt.where(func.lower(Jurisdiction.code) == jurisdiction_code.strip().lower())
    if audience:
        stmt = stmt.where(ComplaintGuideVersion.audience == audience.strip().lower())
    if _slug:
        stmt = stmt.where(ComplaintGuide.slug == _slug)
    stmt = (
        stmt.order_by(
            ComplaintGuide.slug,
            ComplaintGuideVersion.version_number,
            ComplaintGuideVersion.id,
        )
        .limit(min(max(limit, 1), 100))
        .offset(max(offset, 0))
    )
    rows = (await db.execute(stmt)).all()
    return [_guide_read(guide, version, jurisdiction) for guide, version, jurisdiction in rows]


async def get_student_complaint_guide(db: AsyncSession, slug: str) -> ComplaintGuideRead | None:
    normalized_slug = slug.strip().lower()
    rows = await list_student_complaint_guides(db, _slug=normalized_slug, limit=1)
    return rows[0] if rows else None
