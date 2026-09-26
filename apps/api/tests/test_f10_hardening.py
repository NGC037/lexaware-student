"""Tests for F10 hardening: security headers, exception handler, logging setup."""

from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------


def test_security_headers_present_on_health() -> None:
    """Every response must carry the core defensive security headers."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("x-xss-protection") == "0"
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("permissions-policy") == "geolocation=(), microphone=(), camera=()"


def test_hsts_absent_in_non_production() -> None:
    """HSTS must NOT be sent outside production to prevent localhost HSTS lockout."""
    response = client.get("/api/v1/health")
    # Test client runs against the development config (ENVIRONMENT != production).
    assert "strict-transport-security" not in response.headers


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------


def test_unhandled_exception_returns_generic_500() -> None:
    """An unhandled exception must return a safe generic error with no internals."""
    from fastapi import APIRouter

    # Add a temporary route that raises an unhandled RuntimeError.
    crash_router = APIRouter()

    @crash_router.get("/test-crash-f10")
    async def crash_endpoint() -> None:
        raise RuntimeError("internal details that must never leak")

    app.include_router(crash_router, prefix="/api/v1")

    try:
        response = client.get("/api/v1/test-crash-f10")
        assert response.status_code == 500
        body = response.json()
        assert body["detail"]["code"] == "internal_server_error"
        assert body["detail"]["message"] == "An unexpected server error occurred."
        # Internal exception message must not appear in the response body.
        assert "internal details" not in response.text
        assert "RuntimeError" not in response.text
        assert "traceback" not in response.text.lower()
    finally:
        # Remove the test route from the router to avoid contamination.
        app.routes[:] = [
            r for r in app.routes if getattr(r, "path", "") != "/api/v1/test-crash-f10"
        ]


def test_http_exception_not_swallowed_by_global_handler() -> None:
    """HTTPException (404) must NOT be converted to a generic 500."""
    response = client.get("/api/v1/nonexistent-path-that-does-not-exist")
    # FastAPI returns 404 for unknown routes; the global handler must not catch it.
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def test_setup_logging_idempotent() -> None:
    """Calling setup_logging() repeatedly must not attach duplicate handlers."""
    from app.core.logging import setup_logging

    root = logging.getLogger()
    before = len(root.handlers)
    setup_logging()
    setup_logging()
    after = len(root.handlers)
    # Handler count must not increase on subsequent calls.
    assert after == before
