import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.complaints.schemas import (
    ComplaintGuideAdminRead,
    ComplaintGuideCreate,
    ComplaintGuideRead,
    ComplaintGuideUpdate,
    ComplaintGuideVersionAdminRead,
    ComplaintGuideVersionCreate,
    GuideReviewDecision,
)
from app.complaints.service import (
    archive_complaint_guide,
    create_complaint_guide,
    create_complaint_guide_version,
    get_admin_complaint_guide,
    get_student_complaint_guide,
    list_admin_complaint_guides,
    list_student_complaint_guides,
    publish_complaint_guide,
    review_complaint_guide,
    submit_complaint_guide_for_review,
    unpublish_complaint_guide_version,
    update_complaint_guide_draft,
)
from app.db.models import User
from app.db.session import get_db_session

complaint_router = APIRouter(prefix="/complaints", tags=["complaint guidance"])
admin_complaint_router = APIRouter(
    prefix="/admin/complaints/guides", tags=["complaint guidance governance"]
)


@complaint_router.get(
    "/guides",
    response_model=list[ComplaintGuideRead],
    summary="Browse current published complaint guidance",
)
async def list_complaint_guides_endpoint(
    category: str | None = Query(default=None, max_length=80),
    jurisdiction: str | None = Query(default=None, max_length=32),
    audience: str | None = Query(default=None, max_length=60),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=1_000_000),
    db: AsyncSession = Depends(get_db_session),
) -> list[ComplaintGuideRead]:
    return await list_student_complaint_guides(
        db,
        category=category,
        jurisdiction_code=jurisdiction,
        audience=audience,
        limit=limit,
        offset=offset,
    )


@complaint_router.get(
    "/guides/{slug}",
    response_model=ComplaintGuideRead,
    summary="Read a current published complaint guide",
)
async def get_complaint_guide_endpoint(
    slug: str,
    db: AsyncSession = Depends(get_db_session),
) -> ComplaintGuideRead:
    guide = await get_student_complaint_guide(db, slug)
    if guide is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint guide not found or not currently available.",
        )
    return guide


@admin_complaint_router.post(
    "",
    response_model=ComplaintGuideAdminRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a complaint guide with an initial draft version",
)
async def create_complaint_guide_endpoint(
    payload: ComplaintGuideCreate,
    current_user: User = Depends(require_role("admin", "reviewer")),
    db: AsyncSession = Depends(get_db_session),
) -> ComplaintGuideAdminRead:
    return await create_complaint_guide(db, current_user.id, payload)


@admin_complaint_router.get(
    "",
    response_model=list[ComplaintGuideAdminRead],
    summary="List complaint guides for governance",
)
async def list_admin_complaint_guides_endpoint(
    current_user: User = Depends(require_role("admin", "reviewer", "publisher")),
    db: AsyncSession = Depends(get_db_session),
) -> list[ComplaintGuideAdminRead]:
    return await list_admin_complaint_guides(db)


@admin_complaint_router.get(
    "/{guide_id}",
    response_model=ComplaintGuideAdminRead,
    summary="Read complaint guide versions for governance",
)
async def get_admin_complaint_guide_endpoint(
    guide_id: uuid.UUID,
    current_user: User = Depends(require_role("admin", "reviewer", "publisher")),
    db: AsyncSession = Depends(get_db_session),
) -> ComplaintGuideAdminRead:
    return await get_admin_complaint_guide(db, guide_id)


@admin_complaint_router.post(
    "/{guide_id}/versions",
    response_model=ComplaintGuideVersionAdminRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new complaint guide draft version",
)
async def create_complaint_guide_version_endpoint(
    guide_id: uuid.UUID,
    payload: ComplaintGuideVersionCreate,
    current_user: User = Depends(require_role("admin", "reviewer")),
    db: AsyncSession = Depends(get_db_session),
) -> ComplaintGuideVersionAdminRead:
    return await create_complaint_guide_version(db, current_user.id, guide_id, payload)


@admin_complaint_router.put(
    "/versions/{version_id}",
    response_model=ComplaintGuideVersionAdminRead,
    summary="Update a complaint guide draft",
)
async def update_complaint_guide_endpoint(
    version_id: uuid.UUID,
    payload: ComplaintGuideUpdate,
    current_user: User = Depends(require_role("admin", "reviewer")),
    db: AsyncSession = Depends(get_db_session),
) -> ComplaintGuideVersionAdminRead:
    return await update_complaint_guide_draft(db, current_user.id, version_id, payload)


@admin_complaint_router.post(
    "/versions/{version_id}/submit-review",
    response_model=ComplaintGuideVersionAdminRead,
    summary="Submit a complete complaint guide to review",
)
async def submit_complaint_guide_endpoint(
    version_id: uuid.UUID,
    current_user: User = Depends(require_role("admin", "reviewer")),
    db: AsyncSession = Depends(get_db_session),
) -> ComplaintGuideVersionAdminRead:
    return await submit_complaint_guide_for_review(db, current_user.id, version_id)


@admin_complaint_router.post(
    "/versions/{version_id}/review",
    response_model=ComplaintGuideVersionAdminRead,
    summary="Approve or reject a complaint guide version",
)
async def review_complaint_guide_endpoint(
    version_id: uuid.UUID,
    payload: GuideReviewDecision,
    current_user: User = Depends(require_role("admin", "reviewer")),
    db: AsyncSession = Depends(get_db_session),
) -> ComplaintGuideVersionAdminRead:
    return await review_complaint_guide(db, current_user.id, version_id, payload)


@admin_complaint_router.post(
    "/versions/{version_id}/publish",
    response_model=ComplaintGuideVersionAdminRead,
    summary="Publish an approved complaint guide version",
)
async def publish_complaint_guide_endpoint(
    version_id: uuid.UUID,
    current_user: User = Depends(require_role("admin", "publisher")),
    db: AsyncSession = Depends(get_db_session),
) -> ComplaintGuideVersionAdminRead:
    return await publish_complaint_guide(db, current_user.id, version_id)


@admin_complaint_router.post(
    "/versions/{version_id}/unpublish",
    response_model=ComplaintGuideVersionAdminRead,
    summary="Archive and unpublish a complaint guide version",
)
async def unpublish_complaint_guide_endpoint(
    version_id: uuid.UUID,
    current_user: User = Depends(require_role("admin", "publisher")),
    db: AsyncSession = Depends(get_db_session),
) -> ComplaintGuideVersionAdminRead:
    return await unpublish_complaint_guide_version(db, current_user.id, version_id)


@admin_complaint_router.post(
    "/{guide_id}/archive",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive a complaint guide and remove it from student reads",
)
async def archive_complaint_guide_endpoint(
    guide_id: uuid.UUID,
    current_user: User = Depends(require_role("admin", "publisher")),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await archive_complaint_guide(db, current_user.id, guide_id)
