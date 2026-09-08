from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.auth.dependencies import require_role
from app.auth.router import auth_router
from app.auth.schemas import UserResponse
from app.core.config import get_settings
from app.core.redis import check_redis_connection
from app.db.health import check_database_connection
from app.db.models import User
from app.db.session import engine
from app.knowledge.router import admin_knowledge_router, knowledge_router

settings = get_settings()

router = APIRouter()
router.include_router(auth_router)
router.include_router(knowledge_router)
router.include_router(admin_knowledge_router)


@router.get(
    "/admin-test",
    response_model=UserResponse,
    tags=["authorization"],
    summary="Admin-only endpoint for testing role authorization",
)
async def admin_only_test(
    current_user: User = Depends(require_role("admin")),
) -> UserResponse:
    """Protected endpoint accessible only by users with the 'admin' role."""
    email = current_user.credential.email if current_user.credential else ""
    roles = [ur.role.name for ur in current_user.roles]
    return UserResponse(
        id=current_user.id,
        email=email,
        display_name=current_user.display_name,
        roles=roles,
        status=current_user.status.value,
    )


@router.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Return a lightweight liveness response."""
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@router.get("/ready", tags=["system"])
async def readiness() -> JSONResponse:
    """Return infrastructure readiness status."""
    database_ready = await check_database_connection(engine)
    redis_ready = await check_redis_connection()

    ready = database_ready and redis_ready

    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "service": settings.app_name,
            "dependencies": {
                "database": "ok" if database_ready else "unavailable",
                "redis": "ok" if redis_ready else "unavailable",
            },
        },
    )
