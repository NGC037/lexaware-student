import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.db.models import User
from app.db.session import get_db_session
from app.help.schemas import (
    HelpResourceAdminRead,
    HelpResourceCreate,
    HelpResourceUpdate,
    StudentHelpResourceRead,
    VerifyHelpResource,
)
from app.help.service import (
    create_help_resource,
    list_student_help_resources,
    retire_help_resource,
    update_help_resource,
    verify_help_resource,
)

help_router = APIRouter(prefix="/help", tags=["help directory"])
admin_help_router = APIRouter(prefix="/admin/help", tags=["help governance"])


@help_router.get(
    "",
    response_model=list[StudentHelpResourceRead],
    summary="List current verified student help resources",
)
async def list_help_resources_endpoint(
    category: str | None = Query(default=None, max_length=80),
    jurisdiction: str | None = Query(default=None, max_length=32),
    assistance_type: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=1_000_000),
    db: AsyncSession = Depends(get_db_session),
) -> list[StudentHelpResourceRead]:
    """Return active, source-backed resources whose verification remains current."""
    return await list_student_help_resources(
        db,
        category=category,
        jurisdiction_code=jurisdiction,
        assistance_type=assistance_type,
        limit=limit,
        offset=offset,
    )


@admin_help_router.post(
    "/resources",
    response_model=HelpResourceAdminRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an inactive help resource draft",
)
async def create_help_resource_endpoint(
    payload: HelpResourceCreate,
    current_user: User = Depends(require_role("admin", "reviewer", "publisher")),
    db: AsyncSession = Depends(get_db_session),
) -> HelpResourceAdminRead:
    resource = await create_help_resource(db, current_user.id, payload)
    return HelpResourceAdminRead.model_validate(resource)


@admin_help_router.put(
    "/resources/{resource_id}",
    response_model=HelpResourceAdminRead,
    summary="Update a retired help resource draft",
)
async def update_help_resource_endpoint(
    resource_id: uuid.UUID,
    payload: HelpResourceUpdate,
    current_user: User = Depends(require_role("admin", "reviewer", "publisher")),
    db: AsyncSession = Depends(get_db_session),
) -> HelpResourceAdminRead:
    resource = await update_help_resource(db, current_user.id, resource_id, payload)
    return HelpResourceAdminRead.model_validate(resource)


@admin_help_router.post(
    "/resources/{resource_id}/verify",
    response_model=HelpResourceAdminRead,
    summary="Verify and activate a help resource",
)
async def verify_help_resource_endpoint(
    resource_id: uuid.UUID,
    payload: VerifyHelpResource,
    current_user: User = Depends(require_role("admin", "publisher")),
    db: AsyncSession = Depends(get_db_session),
) -> HelpResourceAdminRead:
    resource = await verify_help_resource(db, current_user.id, resource_id, payload)
    return HelpResourceAdminRead.model_validate(resource)


@admin_help_router.post(
    "/resources/{resource_id}/retire",
    response_model=HelpResourceAdminRead,
    summary="Retire and hide a help resource",
)
async def retire_help_resource_endpoint(
    resource_id: uuid.UUID,
    current_user: User = Depends(require_role("admin", "publisher")),
    db: AsyncSession = Depends(get_db_session),
) -> HelpResourceAdminRead:
    resource = await retire_help_resource(db, current_user.id, resource_id)
    return HelpResourceAdminRead.model_validate(resource)
