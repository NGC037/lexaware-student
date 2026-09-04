from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import router
from app.core.config import get_settings
from app.core.redis import close_redis_connection
from app.db.session import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Release shared infrastructure clients when the API shuts down."""
    yield
    await engine.dispose()
    await close_redis_connection()


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Backend API for LexAware Student, a legal-awareness "
            "and guided-support platform for students."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    application.include_router(
        router,
        prefix=settings.api_v1_prefix,
    )

    return application


app = create_application()
