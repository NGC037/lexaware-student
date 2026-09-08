import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.service import record_audit_event
from app.db.models import (
    Jurisdiction,
    KnowledgeItem,
    KnowledgeStatus,
    KnowledgeVersion,
    PublicationState,
    Source,
)
from app.knowledge.schemas import (
    CategorySummary,
    JurisdictionCreate,
    JurisdictionRead,
    KnowledgeItemAdminDetail,
    KnowledgeItemAdminListItem,
    KnowledgeItemCreate,
    KnowledgeVersionCreate,
    KnowledgeVersionSummary,
    KnowledgeVersionUpdate,
    SourceCreate,
    SourceRead,
    StudentArticleDetail,
    StudentArticleListItem,
)


class KnowledgeInvariantError(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def validate_publication_invariants(
    version: KnowledgeVersion, item: KnowledgeItem, source: Source
) -> None:
    """Validate all mandatory publication invariants before promoting a version to PUBLISHED."""
    errors: list[str] = []

    title = version.title.strip() if version.title else item.title.strip()
    if not title:
        errors.append("Article title must be present.")

    if not version.content or len(version.content.strip()) < 20:
        errors.append("Article content must be non-empty and substantive (at least 20 characters).")

    if not version.summary or not version.summary.strip():
        errors.append("A plain-language summary is required for student discoverability.")

    if not version.applicability_notes or not version.applicability_notes.strip():
        errors.append("Applicability notes must be provided to define the legal scope.")

    if not version.escalation_guidance or not version.escalation_guidance.strip():
        errors.append("Escalation guidance is mandatory for student safety.")

    if not source.is_active:
        errors.append(f"Associated source '{source.title}' is inactive or deprecated.")

    if not version.reviewed_at or not version.reviewed_by_id:
        errors.append(
            "Article must undergo formal review (reviewed_at and reviewed_by) prior to publication."
        )

    if errors:
        raise KnowledgeInvariantError(f"Publication invariants not met: {'; '.join(errors)}")


# ---------------------------------------------------------------------------
# Jurisdictions & Sources
# ---------------------------------------------------------------------------


async def get_or_create_jurisdiction(db: AsyncSession, req: JurisdictionCreate) -> Jurisdiction:
    stmt = select(Jurisdiction).where(Jurisdiction.code == req.code)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        return existing

    jurisdiction = Jurisdiction(
        code=req.code,
        name=req.name,
        parent_id=req.parent_id,
    )
    db.add(jurisdiction)
    await db.commit()
    await db.refresh(jurisdiction)
    return jurisdiction


async def list_jurisdictions(db: AsyncSession) -> list[Jurisdiction]:
    stmt = select(Jurisdiction).order_by(Jurisdiction.code)
    return list((await db.execute(stmt)).scalars().all())


async def create_source(db: AsyncSession, actor_id: uuid.UUID, req: SourceCreate) -> Source:
    # Validate jurisdiction
    jurisdiction = await db.get(Jurisdiction, req.jurisdiction_id)
    if not jurisdiction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jurisdiction not found.",
        )

    retrieved = req.retrieved_at or datetime.now(UTC)
    source = Source(
        jurisdiction_id=req.jurisdiction_id,
        title=req.title,
        publisher=req.publisher,
        source_url=req.source_url,
        citation=req.citation,
        retrieved_at=retrieved,
        effective_from=req.effective_from,
        effective_until=req.effective_until,
        is_active=True,
    )
    db.add(source)
    await db.flush()

    await record_audit_event(
        db,
        action="knowledge.source.created",
        resource_type="source",
        resource_id=source.id,
        actor_id=actor_id,
        details={"title": source.title, "jurisdiction_id": str(source.jurisdiction_id)},
    )
    await db.commit()
    await db.refresh(source)
    return source


async def list_sources(db: AsyncSession, jurisdiction_id: uuid.UUID | None = None) -> list[Source]:
    stmt = select(Source).order_by(Source.title)
    if jurisdiction_id:
        stmt = stmt.where(Source.jurisdiction_id == jurisdiction_id)
    return list((await db.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# Governance Operations: Items & Versions
# ---------------------------------------------------------------------------


async def create_knowledge_item(
    db: AsyncSession, actor_id: uuid.UUID, req: KnowledgeItemCreate
) -> tuple[KnowledgeItem, KnowledgeVersion]:
    """Create a new governed knowledge item and its initial v1 draft version."""
    # 1. Validate jurisdiction
    jurisdiction = await db.get(Jurisdiction, req.jurisdiction_id)
    if not jurisdiction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jurisdiction not found.")

    # 2. Validate source
    source = await db.get(Source, req.source_id)
    if not source or not source.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Active source reference required."
        )

    # 3. Check slug uniqueness
    slug_stmt = select(KnowledgeItem).where(KnowledgeItem.slug == req.slug.strip().lower())
    if (await db.execute(slug_stmt)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An article with this slug already exists.",
        )

    item = KnowledgeItem(
        jurisdiction_id=req.jurisdiction_id,
        category=req.category.strip().lower(),
        topic=req.topic.strip() if req.topic else None,
        audience=req.audience.strip().lower() if req.audience else "students",
        slug=req.slug.strip().lower(),
        title=req.title.strip(),
        status=KnowledgeStatus.ACTIVE,
    )
    db.add(item)
    await db.flush()

    version = KnowledgeVersion(
        knowledge_item_id=item.id,
        source_id=req.source_id,
        version_number=1,
        title=req.title.strip(),
        summary=req.summary.strip() if req.summary else None,
        content=req.content.strip(),
        applicability_notes=req.applicability_notes.strip() if req.applicability_notes else None,
        escalation_guidance=req.escalation_guidance.strip() if req.escalation_guidance else None,
        publication_state=PublicationState.DRAFT,
        effective_from=req.effective_from,
        effective_until=req.effective_until,
        review_due_at=req.review_due_at,
        change_summary="Initial draft creation",
    )
    db.add(version)
    await db.flush()

    await record_audit_event(
        db,
        action="knowledge.item.created",
        resource_type="knowledge_item",
        resource_id=item.id,
        actor_id=actor_id,
        details={"slug": item.slug, "category": item.category},
    )
    await record_audit_event(
        db,
        action="knowledge.version.created",
        resource_type="knowledge_version",
        resource_id=version.id,
        actor_id=actor_id,
        details={
            "item_id": str(item.id),
            "version_number": 1,
            "state": version.publication_state.value,
        },
    )

    await db.commit()
    await db.refresh(item)
    await db.refresh(version)
    return item, version


async def create_new_draft_version(
    db: AsyncSession,
    actor_id: uuid.UUID,
    item_id: uuid.UUID,
    req: KnowledgeVersionCreate,
) -> KnowledgeVersion:
    """Create a new draft version for an existing item, auto-incrementing version number."""
    item_stmt = (
        select(KnowledgeItem)
        .where(KnowledgeItem.id == item_id)
        .options(selectinload(KnowledgeItem.versions))
    )
    item = (await db.execute(item_stmt)).scalar_one_or_none()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge item not found."
        )

    if item.status == KnowledgeStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create versions for an archived knowledge item.",
        )

    # Check if there is already an unapproved draft or in-review version
    for existing_ver in item.versions:
        if existing_ver.publication_state in (PublicationState.DRAFT, PublicationState.IN_REVIEW):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Version {existing_ver.version_number} is currently in "
                    f"'{existing_ver.publication_state.value}'. "
                    "Complete or archive it before creating a new draft."
                ),
            )

    latest_ver_num = max((v.version_number for v in item.versions), default=0)
    next_ver_num = latest_ver_num + 1

    source_id = req.source_id or (item.versions[-1].source_id if item.versions else None)
    if not source_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Source ID is required."
        )

    source = await db.get(Source, source_id)
    if not source or not source.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Active source required."
        )

    title = req.title.strip() if req.title else item.title

    new_version = KnowledgeVersion(
        knowledge_item_id=item.id,
        source_id=source_id,
        version_number=next_ver_num,
        title=title,
        summary=req.summary.strip() if req.summary else None,
        content=req.content.strip(),
        applicability_notes=req.applicability_notes.strip() if req.applicability_notes else None,
        escalation_guidance=req.escalation_guidance.strip() if req.escalation_guidance else None,
        publication_state=PublicationState.DRAFT,
        effective_from=req.effective_from,
        effective_until=req.effective_until,
        review_due_at=req.review_due_at,
        change_summary=req.change_summary.strip()
        if req.change_summary
        else f"Draft for version {next_ver_num}",
    )
    db.add(new_version)
    await db.flush()

    await record_audit_event(
        db,
        action="knowledge.version.created",
        resource_type="knowledge_version",
        resource_id=new_version.id,
        actor_id=actor_id,
        details={"item_id": str(item.id), "version_number": next_ver_num, "state": "draft"},
    )
    await db.commit()
    await db.refresh(new_version)
    return new_version


async def update_draft_version(
    db: AsyncSession,
    actor_id: uuid.UUID,
    version_id: uuid.UUID,
    req: KnowledgeVersionUpdate,
) -> KnowledgeVersion:
    """Update editable content on a draft version.

    Published or immutable versions reject direct edit.
    """
    version = await db.get(KnowledgeVersion, version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")

    if version.publication_state != PublicationState.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Only versions in 'draft' state can be edited directly. "
                f"Current state: '{version.publication_state.value}'."
            ),
        )

    if req.source_id is not None:
        source = await db.get(Source, req.source_id)
        if not source or not source.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Active source required."
            )
        version.source_id = req.source_id

    if req.title is not None:
        version.title = req.title.strip()
    if req.summary is not None:
        version.summary = req.summary.strip() if req.summary else None
    if req.content is not None:
        version.content = req.content.strip()
    if req.applicability_notes is not None:
        version.applicability_notes = (
            req.applicability_notes.strip() if req.applicability_notes else None
        )
    if req.escalation_guidance is not None:
        version.escalation_guidance = (
            req.escalation_guidance.strip() if req.escalation_guidance else None
        )
    if req.effective_from is not None:
        version.effective_from = req.effective_from
    if req.effective_until is not None:
        version.effective_until = req.effective_until
    if req.review_due_at is not None:
        version.review_due_at = req.review_due_at
    if req.change_summary is not None:
        version.change_summary = req.change_summary.strip() if req.change_summary else None

    await record_audit_event(
        db,
        action="knowledge.version.updated",
        resource_type="knowledge_version",
        resource_id=version.id,
        actor_id=actor_id,
        details={"version_number": version.version_number},
    )
    await db.commit()
    await db.refresh(version)
    return version


async def submit_version_for_review(
    db: AsyncSession, actor_id: uuid.UUID, version_id: uuid.UUID
) -> KnowledgeVersion:
    """Submit a draft version into the review queue."""
    version = await db.get(KnowledgeVersion, version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")

    if version.publication_state != PublicationState.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot submit version in state '{version.publication_state.value}' for review. "
                "Must be in 'draft'."
            ),
        )

    if not version.content or len(version.content.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Substantive content required for review.",
        )

    version.publication_state = PublicationState.IN_REVIEW
    await record_audit_event(
        db,
        action="knowledge.version.submitted_review",
        resource_type="knowledge_version",
        resource_id=version.id,
        actor_id=actor_id,
        details={"version_number": version.version_number, "to_state": "in_review"},
    )
    await db.commit()
    await db.refresh(version)
    return version


async def review_version(
    db: AsyncSession,
    reviewer_id: uuid.UUID,
    version_id: uuid.UUID,
    decision: Literal["approve", "reject"],
    notes: str | None = None,
) -> KnowledgeVersion:
    """Perform formal review decision on an in-review version."""
    version = await db.get(KnowledgeVersion, version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")

    if version.publication_state != PublicationState.IN_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot review version in state '{version.publication_state.value}'. "
                "Must be 'in_review'."
            ),
        )

    now = datetime.now(UTC)
    if decision == "approve":
        version.publication_state = PublicationState.APPROVED
        version.reviewed_at = now
        version.reviewed_by_id = reviewer_id
        if notes:
            version.change_summary = f"[Approved] {notes}"

        await record_audit_event(
            db,
            action="knowledge.version.approved",
            resource_type="knowledge_version",
            resource_id=version.id,
            actor_id=reviewer_id,
            details={"version_number": version.version_number, "notes": notes},
        )
    else:
        version.publication_state = PublicationState.DRAFT
        version.reviewed_at = None
        version.reviewed_by_id = None
        if notes:
            version.change_summary = f"[Rejected] {notes}"

        await record_audit_event(
            db,
            action="knowledge.version.rejected",
            resource_type="knowledge_version",
            resource_id=version.id,
            actor_id=reviewer_id,
            details={"version_number": version.version_number, "notes": notes},
        )

    await db.commit()
    await db.refresh(version)
    return version


async def publish_version(
    db: AsyncSession, publisher_id: uuid.UUID, version_id: uuid.UUID
) -> KnowledgeVersion:
    """Publish an approved version, enforcing invariants and superseding prior versions."""
    version_stmt = (
        select(KnowledgeVersion)
        .where(KnowledgeVersion.id == version_id)
        .options(
            selectinload(KnowledgeVersion.knowledge_item).selectinload(KnowledgeItem.versions),
            selectinload(KnowledgeVersion.source),
        )
    )
    version = (await db.execute(version_stmt)).scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")

    if version.publication_state != PublicationState.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Version must be in 'approved' state before publication. "
                f"Current state: '{version.publication_state.value}'."
            ),
        )

    item = version.knowledge_item
    source = version.source

    # Validate all mandatory publication invariants
    validate_publication_invariants(version, item, source)

    now = datetime.now(UTC)

    # Transition any existing PUBLISHED version for this item to SUPERSEDED
    for other_ver in item.versions:
        if other_ver.id != version.id and other_ver.publication_state == PublicationState.PUBLISHED:
            other_ver.publication_state = PublicationState.SUPERSEDED
            await record_audit_event(
                db,
                action="knowledge.version.superseded",
                resource_type="knowledge_version",
                resource_id=other_ver.id,
                actor_id=publisher_id,
                details={
                    "item_id": str(item.id),
                    "version_number": other_ver.version_number,
                    "superseded_by_version": version.version_number,
                },
            )

    # Promote target version to PUBLISHED
    version.publication_state = PublicationState.PUBLISHED
    version.published_at = now
    version.published_by_id = publisher_id
    if not version.effective_from:
        version.effective_from = now

    # Ensure parent knowledge item is active and has synced canonical title
    item.status = KnowledgeStatus.ACTIVE
    if version.title:
        item.title = version.title

    await record_audit_event(
        db,
        action="knowledge.version.published",
        resource_type="knowledge_version",
        resource_id=version.id,
        actor_id=publisher_id,
        details={
            "item_id": str(item.id),
            "version_number": version.version_number,
            "published_at": now.isoformat(),
        },
    )

    await db.commit()
    await db.refresh(version)
    return version


async def unpublish_version(
    db: AsyncSession,
    publisher_id: uuid.UUID,
    version_id: uuid.UUID,
    reason: str | None = None,
) -> KnowledgeVersion:
    """Unpublish and archive a published knowledge version."""
    version = await db.get(KnowledgeVersion, version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")

    if version.publication_state != PublicationState.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Only currently 'published' versions can be unpublished. "
                f"Current state: '{version.publication_state.value}'."
            ),
        )

    version.publication_state = PublicationState.ARCHIVED
    if reason:
        version.change_summary = f"[Unpublished] {reason}"

    await record_audit_event(
        db,
        action="knowledge.version.unpublished",
        resource_type="knowledge_version",
        resource_id=version.id,
        actor_id=publisher_id,
        details={"version_number": version.version_number, "reason": reason},
    )
    await db.commit()
    await db.refresh(version)
    return version


async def schedule_version_review(
    db: AsyncSession,
    actor_id: uuid.UUID,
    version_id: uuid.UUID,
    review_due_at: datetime,
) -> KnowledgeVersion:
    """Schedule or update the freshness review date for a version."""
    version = await db.get(KnowledgeVersion, version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")

    version.review_due_at = review_due_at
    await record_audit_event(
        db,
        action="knowledge.version.review_scheduled",
        resource_type="knowledge_version",
        resource_id=version.id,
        actor_id=actor_id,
        details={
            "version_number": version.version_number,
            "review_due_at": review_due_at.isoformat(),
        },
    )
    await db.commit()
    await db.refresh(version)
    return version


# ---------------------------------------------------------------------------
# Student-Safe Read Boundary Queries
# ---------------------------------------------------------------------------


async def get_student_articles(
    db: AsyncSession,
    jurisdiction_code: str | None = None,
    category: str | None = None,
    query: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[StudentArticleListItem]:
    """Retrieve published, currently applicable articles for student browsing and search.

    Safety Guarantees:
    - Only KnowledgeStatus.ACTIVE items.
    - Only PublicationState.PUBLISHED versions.
    - Only versions where effective_from <= now <= effective_until (temporal applicability).
    - NEVER returns drafts, in-review, approved, superseded, or archived content.
    """
    now = datetime.now(UTC)

    stmt = (
        select(KnowledgeItem, KnowledgeVersion, Jurisdiction, Source)
        .join(KnowledgeVersion, KnowledgeItem.id == KnowledgeVersion.knowledge_item_id)
        .join(Jurisdiction, KnowledgeItem.jurisdiction_id == Jurisdiction.id)
        .join(Source, KnowledgeVersion.source_id == Source.id)
        .where(
            KnowledgeItem.status == KnowledgeStatus.ACTIVE,
            KnowledgeVersion.publication_state == PublicationState.PUBLISHED,
            or_(
                KnowledgeVersion.effective_from.is_(None),
                KnowledgeVersion.effective_from <= now,
            ),
            or_(
                KnowledgeVersion.effective_until.is_(None),
                KnowledgeVersion.effective_until >= now,
            ),
        )
    )

    if jurisdiction_code:
        code_norm = jurisdiction_code.strip().lower()
        stmt = stmt.where(func.lower(Jurisdiction.code) == code_norm)

    if category:
        cat_norm = category.strip().lower()
        stmt = stmt.where(KnowledgeItem.category == cat_norm)

    if query:
        term = f"%{query.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(KnowledgeItem.title).ilike(term),
                func.lower(KnowledgeVersion.title).ilike(term),
                func.lower(KnowledgeVersion.summary).ilike(term),
                func.lower(KnowledgeItem.category).ilike(term),
                func.lower(KnowledgeItem.topic).ilike(term),
            )
        )

    stmt = stmt.order_by(KnowledgeItem.title).limit(limit).offset(offset)
    results = await db.execute(stmt)

    articles: list[StudentArticleListItem] = []
    for item, ver, jur, src in results.all():
        articles.append(
            StudentArticleListItem(
                id=item.id,
                slug=item.slug,
                title=ver.title or item.title,
                category=item.category,
                topic=item.topic,
                audience=item.audience,
                summary=ver.summary,
                jurisdiction=JurisdictionRead.model_validate(jur),
                effective_from=ver.effective_from,
                last_reviewed_at=ver.reviewed_at,
                source_title=src.title if src else None,
            )
        )

    return articles


async def get_student_article_by_slug(db: AsyncSession, slug: str) -> StudentArticleDetail | None:
    """Retrieve full detail of a published article by slug under strict safety constraints."""
    now = datetime.now(UTC)
    slug_norm = slug.strip().lower()

    stmt = (
        select(KnowledgeItem, KnowledgeVersion, Jurisdiction, Source)
        .join(KnowledgeVersion, KnowledgeItem.id == KnowledgeVersion.knowledge_item_id)
        .join(Jurisdiction, KnowledgeItem.jurisdiction_id == Jurisdiction.id)
        .join(Source, KnowledgeVersion.source_id == Source.id)
        .where(
            KnowledgeItem.slug == slug_norm,
            KnowledgeItem.status == KnowledgeStatus.ACTIVE,
            KnowledgeVersion.publication_state == PublicationState.PUBLISHED,
            or_(
                KnowledgeVersion.effective_from.is_(None),
                KnowledgeVersion.effective_from <= now,
            ),
            or_(
                KnowledgeVersion.effective_until.is_(None),
                KnowledgeVersion.effective_until >= now,
            ),
        )
    )
    result = (await db.execute(stmt)).first()
    if not result:
        return None

    item, ver, jur, src = result
    return StudentArticleDetail(
        id=item.id,
        slug=item.slug,
        title=ver.title or item.title,
        category=item.category,
        topic=item.topic,
        audience=item.audience,
        jurisdiction=JurisdictionRead.model_validate(jur),
        version_number=ver.version_number,
        summary=ver.summary,
        content=ver.content,
        applicability_notes=ver.applicability_notes,
        escalation_guidance=ver.escalation_guidance,
        effective_from=ver.effective_from,
        last_reviewed_at=ver.reviewed_at,
        source=SourceRead.model_validate(src),
    )


async def get_student_categories(
    db: AsyncSession, jurisdiction_code: str | None = None
) -> list[CategorySummary]:
    """List available categories with published article counts."""
    now = datetime.now(UTC)
    stmt = (
        select(KnowledgeItem.category, func.count(KnowledgeItem.id))
        .join(KnowledgeVersion, KnowledgeItem.id == KnowledgeVersion.knowledge_item_id)
        .join(Jurisdiction, KnowledgeItem.jurisdiction_id == Jurisdiction.id)
        .where(
            KnowledgeItem.status == KnowledgeStatus.ACTIVE,
            KnowledgeVersion.publication_state == PublicationState.PUBLISHED,
            or_(
                KnowledgeVersion.effective_from.is_(None),
                KnowledgeVersion.effective_from <= now,
            ),
            or_(
                KnowledgeVersion.effective_until.is_(None),
                KnowledgeVersion.effective_until >= now,
            ),
        )
    )
    if jurisdiction_code:
        stmt = stmt.where(func.lower(Jurisdiction.code) == jurisdiction_code.strip().lower())

    stmt = stmt.group_by(KnowledgeItem.category).order_by(KnowledgeItem.category)
    rows = (await db.execute(stmt)).all()
    return [CategorySummary(category=cat, article_count=cnt) for cat, cnt in rows]


# ---------------------------------------------------------------------------
# Admin Governance Listing & Review Queue (FR-27)
# ---------------------------------------------------------------------------


async def list_admin_knowledge_items(
    db: AsyncSession,
    category: str | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[KnowledgeItemAdminListItem]:
    stmt = (
        select(KnowledgeItem)
        .options(selectinload(KnowledgeItem.versions), selectinload(KnowledgeItem.jurisdiction))
        .order_by(KnowledgeItem.created_at.desc())
    )
    if category:
        stmt = stmt.where(KnowledgeItem.category == category.strip().lower())
    if status_filter:
        stmt = stmt.where(KnowledgeItem.status == status_filter.strip().lower())

    stmt = stmt.limit(limit).offset(offset)
    items = list((await db.execute(stmt)).scalars().all())

    result: list[KnowledgeItemAdminListItem] = []
    for it in items:
        latest_v = max(it.versions, key=lambda v: v.version_number) if it.versions else None
        result.append(
            KnowledgeItemAdminListItem(
                id=it.id,
                jurisdiction_id=it.jurisdiction_id,
                category=it.category,
                topic=it.topic,
                audience=it.audience,
                slug=it.slug,
                title=it.title,
                status=it.status.value,
                latest_version_number=latest_v.version_number if latest_v else 0,
                latest_publication_state=latest_v.publication_state.value if latest_v else "none",
                review_due_at=latest_v.review_due_at if latest_v else None,
                created_at=it.created_at,
            )
        )
    return result


async def get_admin_knowledge_item(
    db: AsyncSession, item_id: uuid.UUID
) -> KnowledgeItemAdminDetail | None:
    stmt = (
        select(KnowledgeItem)
        .where(KnowledgeItem.id == item_id)
        .options(
            selectinload(KnowledgeItem.jurisdiction),
            selectinload(KnowledgeItem.versions),
        )
    )
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item:
        return None

    versions_summary = [
        KnowledgeVersionSummary(
            id=v.id,
            knowledge_item_id=v.knowledge_item_id,
            source_id=v.source_id,
            version_number=v.version_number,
            title=v.title,
            summary=v.summary,
            publication_state=v.publication_state.value,
            effective_from=v.effective_from,
            effective_until=v.effective_until,
            reviewed_at=v.reviewed_at,
            reviewed_by_id=v.reviewed_by_id,
            published_at=v.published_at,
            published_by_id=v.published_by_id,
            review_due_at=v.review_due_at,
            change_summary=v.change_summary,
            created_at=v.created_at,
            updated_at=v.updated_at,
        )
        for v in sorted(item.versions, key=lambda x: x.version_number, reverse=True)
    ]

    return KnowledgeItemAdminDetail(
        id=item.id,
        jurisdiction_id=item.jurisdiction_id,
        category=item.category,
        topic=item.topic,
        audience=item.audience,
        slug=item.slug,
        title=item.title,
        status=item.status.value,
        jurisdiction=JurisdictionRead.model_validate(item.jurisdiction),
        versions=versions_summary,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


async def list_stale_reviews(db: AsyncSession) -> list[KnowledgeVersionSummary]:
    """Find published articles past their scheduled review date (FR-27 content review queue)."""
    now = datetime.now(UTC)
    stmt = (
        select(KnowledgeVersion)
        .where(
            KnowledgeVersion.publication_state == PublicationState.PUBLISHED,
            KnowledgeVersion.review_due_at.is_not(None),
            KnowledgeVersion.review_due_at < now,
        )
        .order_by(KnowledgeVersion.review_due_at.asc())
    )
    versions = list((await db.execute(stmt)).scalars().all())
    return [
        KnowledgeVersionSummary(
            id=v.id,
            knowledge_item_id=v.knowledge_item_id,
            source_id=v.source_id,
            version_number=v.version_number,
            title=v.title,
            summary=v.summary,
            publication_state=v.publication_state.value,
            effective_from=v.effective_from,
            effective_until=v.effective_until,
            reviewed_at=v.reviewed_at,
            reviewed_by_id=v.reviewed_by_id,
            published_at=v.published_at,
            published_by_id=v.published_by_id,
            review_due_at=v.review_due_at,
            change_summary=v.change_summary,
            created_at=v.created_at,
            updated_at=v.updated_at,
        )
        for v in versions
    ]
