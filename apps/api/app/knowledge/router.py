import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.db.models import User
from app.db.session import get_db_session
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
    ReviewDecisionRequest,
    ScheduleReviewRequest,
    SourceCreate,
    SourceRead,
    StudentArticleDetail,
    StudentArticleListItem,
)
from app.knowledge.service import (
    create_knowledge_item,
    create_new_draft_version,
    create_source,
    get_admin_knowledge_item,
    get_or_create_jurisdiction,
    get_student_article_by_slug,
    get_student_articles,
    get_student_categories,
    list_admin_knowledge_items,
    list_jurisdictions,
    list_sources,
    list_stale_reviews,
    publish_version,
    review_version,
    schedule_version_review,
    submit_version_for_review,
    unpublish_version,
    update_draft_version,
)

# ---------------------------------------------------------------------------
# Student Public Knowledge Router (Strict Read Safety Boundary)
# ---------------------------------------------------------------------------

knowledge_router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@knowledge_router.get(
    "/articles",
    response_model=list[StudentArticleListItem],
    summary="Browse and search published, currently effective articles",
)
async def list_student_articles_endpoint(
    jurisdiction: str | None = Query(
        default=None, description="Jurisdiction code filter (e.g. IN-DL, IN-KA)"
    ),
    category: str | None = Query(
        default=None, description="Category filter (e.g. ragging, tenancy)"
    ),
    q: str | None = Query(default=None, description="Search query string"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> list[StudentArticleListItem]:
    """Retrieve published articles matching filters.

    Never exposes drafts, superseded, or archived content.
    """
    return await get_student_articles(
        db,
        jurisdiction_code=jurisdiction,
        category=category,
        query=q,
        limit=limit,
        offset=offset,
    )


@knowledge_router.get(
    "/articles/{slug}",
    response_model=StudentArticleDetail,
    summary="Retrieve full published article detail by slug",
)
async def get_student_article_endpoint(
    slug: str,
    db: AsyncSession = Depends(get_db_session),
) -> StudentArticleDetail:
    """Retrieve full text and authoritative metadata of a published article."""
    article = await get_student_article_by_slug(db, slug=slug)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found or not currently available.",
        )
    return article


@knowledge_router.get(
    "/categories",
    response_model=list[CategorySummary],
    summary="List article categories and published counts",
)
async def list_categories_endpoint(
    jurisdiction: str | None = Query(default=None, description="Optional jurisdiction code filter"),
    db: AsyncSession = Depends(get_db_session),
) -> list[CategorySummary]:
    """List legal awareness categories with counts of active published articles."""
    return await get_student_categories(db, jurisdiction_code=jurisdiction)


@knowledge_router.get(
    "/jurisdictions",
    response_model=list[JurisdictionRead],
    summary="List available jurisdictions",
)
async def list_jurisdictions_public_endpoint(
    db: AsyncSession = Depends(get_db_session),
) -> list[JurisdictionRead]:
    """List all configured legal jurisdictions (federal, state, municipal)."""
    jurisdictions = await list_jurisdictions(db)
    return [JurisdictionRead.model_validate(j) for j in jurisdictions]


# ---------------------------------------------------------------------------
# Admin / Governance Knowledge Router (Governed Lifecycle)
# ---------------------------------------------------------------------------

admin_knowledge_router = APIRouter(prefix="/admin/knowledge", tags=["knowledge-governance"])


# Jurisdictions & Sources Management


@admin_knowledge_router.post(
    "/jurisdictions",
    response_model=JurisdictionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create or retrieve a jurisdiction (Admin only)",
)
async def create_jurisdiction_endpoint(
    payload: JurisdictionCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db_session),
) -> JurisdictionRead:
    jur = await get_or_create_jurisdiction(db, payload)
    return JurisdictionRead.model_validate(jur)


@admin_knowledge_router.get(
    "/jurisdictions",
    response_model=list[JurisdictionRead],
    summary="List all jurisdictions (Governance)",
)
async def list_admin_jurisdictions_endpoint(
    current_user: User = Depends(require_role("admin", "publisher", "reviewer")),
    db: AsyncSession = Depends(get_db_session),
) -> list[JurisdictionRead]:
    jurisdictions = await list_jurisdictions(db)
    return [JurisdictionRead.model_validate(j) for j in jurisdictions]


@admin_knowledge_router.post(
    "/sources",
    response_model=SourceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a legal authoritative source",
)
async def create_source_endpoint(
    payload: SourceCreate,
    current_user: User = Depends(require_role("admin", "publisher", "reviewer")),
    db: AsyncSession = Depends(get_db_session),
) -> SourceRead:
    src = await create_source(db, actor_id=current_user.id, req=payload)
    return SourceRead.model_validate(src)


@admin_knowledge_router.get(
    "/sources",
    response_model=list[SourceRead],
    summary="List authoritative sources",
)
async def list_sources_endpoint(
    jurisdiction_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(require_role("admin", "publisher", "reviewer")),
    db: AsyncSession = Depends(get_db_session),
) -> list[SourceRead]:
    sources = await list_sources(db, jurisdiction_id=jurisdiction_id)
    return [SourceRead.model_validate(s) for s in sources]


# Knowledge Item & Version Lifecycle Endpoints


@admin_knowledge_router.post(
    "/items",
    response_model=KnowledgeItemAdminDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new governed knowledge item and initial v1 draft",
)
async def create_item_endpoint(
    payload: KnowledgeItemCreate,
    current_user: User = Depends(require_role("admin", "publisher", "reviewer")),
    db: AsyncSession = Depends(get_db_session),
) -> KnowledgeItemAdminDetail:
    item, _ = await create_knowledge_item(db, actor_id=current_user.id, req=payload)
    detail = await get_admin_knowledge_item(db, item_id=item.id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load created item."
        )
    return detail


@admin_knowledge_router.get(
    "/items",
    response_model=list[KnowledgeItemAdminListItem],
    summary="List governed knowledge items",
)
async def list_items_endpoint(
    category: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_role("admin", "publisher", "reviewer")),
    db: AsyncSession = Depends(get_db_session),
) -> list[KnowledgeItemAdminListItem]:
    return await list_admin_knowledge_items(
        db, category=category, status_filter=status_filter, limit=limit, offset=offset
    )


@admin_knowledge_router.get(
    "/items/{item_id}",
    response_model=KnowledgeItemAdminDetail,
    summary="Get detailed governed knowledge item with full version history",
)
async def get_item_endpoint(
    item_id: uuid.UUID,
    current_user: User = Depends(require_role("admin", "publisher", "reviewer")),
    db: AsyncSession = Depends(get_db_session),
) -> KnowledgeItemAdminDetail:
    detail = await get_admin_knowledge_item(db, item_id=item_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge item not found."
        )
    return detail


@admin_knowledge_router.post(
    "/items/{item_id}/versions",
    response_model=KnowledgeVersionSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new draft version for an existing knowledge item",
)
async def create_version_endpoint(
    item_id: uuid.UUID,
    payload: KnowledgeVersionCreate,
    current_user: User = Depends(require_role("admin", "publisher", "reviewer")),
    db: AsyncSession = Depends(get_db_session),
) -> KnowledgeVersionSummary:
    ver = await create_new_draft_version(db, actor_id=current_user.id, item_id=item_id, req=payload)
    return KnowledgeVersionSummary.model_validate(ver)


@admin_knowledge_router.put(
    "/versions/{version_id}",
    response_model=KnowledgeVersionSummary,
    summary="Update draft version content (Only permitted while in 'draft' state)",
)
async def update_version_endpoint(
    version_id: uuid.UUID,
    payload: KnowledgeVersionUpdate,
    current_user: User = Depends(require_role("admin", "publisher", "reviewer")),
    db: AsyncSession = Depends(get_db_session),
) -> KnowledgeVersionSummary:
    ver = await update_draft_version(
        db, actor_id=current_user.id, version_id=version_id, req=payload
    )
    return KnowledgeVersionSummary.model_validate(ver)


@admin_knowledge_router.post(
    "/versions/{version_id}/submit-review",
    response_model=KnowledgeVersionSummary,
    summary="Submit a draft version to the review queue",
)
async def submit_review_endpoint(
    version_id: uuid.UUID,
    current_user: User = Depends(require_role("admin", "publisher", "reviewer")),
    db: AsyncSession = Depends(get_db_session),
) -> KnowledgeVersionSummary:
    ver = await submit_version_for_review(db, actor_id=current_user.id, version_id=version_id)
    return KnowledgeVersionSummary.model_validate(ver)


@admin_knowledge_router.post(
    "/versions/{version_id}/review",
    response_model=KnowledgeVersionSummary,
    summary="Review decision (Approve / Reject) (Reviewer or Admin)",
)
async def review_version_endpoint(
    version_id: uuid.UUID,
    payload: ReviewDecisionRequest,
    current_user: User = Depends(require_role("admin", "reviewer")),
    db: AsyncSession = Depends(get_db_session),
) -> KnowledgeVersionSummary:
    ver = await review_version(
        db,
        reviewer_id=current_user.id,
        version_id=version_id,
        decision=payload.decision,
        notes=payload.notes,
    )
    return KnowledgeVersionSummary.model_validate(ver)


@admin_knowledge_router.post(
    "/versions/{version_id}/publish",
    response_model=KnowledgeVersionSummary,
    summary="Publish an approved version (Publisher or Admin only)",
)
async def publish_version_endpoint(
    version_id: uuid.UUID,
    current_user: User = Depends(require_role("admin", "publisher")),
    db: AsyncSession = Depends(get_db_session),
) -> KnowledgeVersionSummary:
    ver = await publish_version(db, publisher_id=current_user.id, version_id=version_id)
    return KnowledgeVersionSummary.model_validate(ver)


@admin_knowledge_router.post(
    "/versions/{version_id}/unpublish",
    response_model=KnowledgeVersionSummary,
    summary="Unpublish and archive a version (Publisher or Admin only)",
)
async def unpublish_version_endpoint(
    version_id: uuid.UUID,
    reason: str | None = Query(default=None, description="Reason for archiving/unpublishing"),
    current_user: User = Depends(require_role("admin", "publisher")),
    db: AsyncSession = Depends(get_db_session),
) -> KnowledgeVersionSummary:
    ver = await unpublish_version(
        db, publisher_id=current_user.id, version_id=version_id, reason=reason
    )
    return KnowledgeVersionSummary.model_validate(ver)


@admin_knowledge_router.post(
    "/versions/{version_id}/schedule-review",
    response_model=KnowledgeVersionSummary,
    summary="Schedule freshness review date for a version",
)
async def schedule_review_endpoint(
    version_id: uuid.UUID,
    payload: ScheduleReviewRequest,
    current_user: User = Depends(require_role("admin", "publisher", "reviewer")),
    db: AsyncSession = Depends(get_db_session),
) -> KnowledgeVersionSummary:
    ver = await schedule_version_review(
        db, actor_id=current_user.id, version_id=version_id, review_due_at=payload.review_due_at
    )
    return KnowledgeVersionSummary.model_validate(ver)


@admin_knowledge_router.get(
    "/stale-reviews",
    response_model=list[KnowledgeVersionSummary],
    summary="List published articles due for review (FR-27 Content Review Queue)",
)
async def list_stale_reviews_endpoint(
    current_user: User = Depends(require_role("admin", "publisher", "reviewer")),
    db: AsyncSession = Depends(get_db_session),
) -> list[KnowledgeVersionSummary]:
    return await list_stale_reviews(db)
