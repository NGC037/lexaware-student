from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.redis import check_redis_connection
from app.db.health import check_database_connection
from app.db.session import engine

settings = get_settings()

router = APIRouter()


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
