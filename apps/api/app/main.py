from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from app.api.router import router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.metrics import http_metrics
from app.core.middleware import (
    RequestCorrelationIdMiddleware,
    SecurityHeadersMiddleware,
    UploadBodySizeLimitMiddleware,
)
from app.core.redis import close_redis_connection
from app.db.session import engine

settings = get_settings()
setup_logging()
logger = logging.getLogger(__name__)


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

    # Configure CORS for browser authentication with credentials (cookies)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_app_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(UploadBodySizeLimitMiddleware)
    application.add_middleware(RequestCorrelationIdMiddleware)

    application.include_router(
        router,
        prefix=settings.api_v1_prefix,
    )

    @application.get("/metrics", include_in_schema=False)
    async def metrics_endpoint() -> PlainTextResponse:
        """Expose aggregate process metrics for a trusted internal scraper."""
        return PlainTextResponse(http_metrics.render(), media_type="text/plain; version=0.0.4")

    # HTTPException and RequestValidationError have their own handlers in
    # FastAPI and must NOT be caught here - they produce correct 4xx responses.
    # Only truly unhandled exceptions reach this handler.
    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, HTTPException | RequestValidationError):
            raise exc
        # Log only method, path, and exception type - no payloads or tracebacks
        # that could contain sensitive application data.
        logger.exception(
            "Unhandled exception [%s %s] %s",
            request.method,
            request.url.path,
            type(exc).__name__,
        )
        route = getattr(request.scope.get("route"), "path", "unmatched")
        started_at = getattr(request.state, "request_started_at", time.perf_counter())
        http_metrics.observe(
            request.method
            if request.method in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}
            else "OTHER",
            route,
            500,
            time.perf_counter() - started_at,
        )
        return JSONResponse(
            status_code=500,
            headers={
                "X-Correlation-ID": str(getattr(request.state, "correlation_id", "unavailable"))
            },
            content={
                "detail": {
                    "code": "internal_server_error",
                    "message": "An unexpected server error occurred.",
                    "correlation_id": getattr(request.state, "correlation_id", None),
                }
            },
        )

    return application


app = create_application()
