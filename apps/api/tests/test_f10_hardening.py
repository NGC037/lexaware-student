"""Tests for F10 hardening: security headers, exception handler, logging setup."""

from __future__ import annotations

import logging
import uuid

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


def test_all_responses_have_server_generated_correlation_id() -> None:
    response = client.get("/api/v1/health", headers={"X-Correlation-ID": "client-value"})
    correlation_id = response.headers["x-correlation-id"]
    assert str(uuid.UUID(correlation_id)) == correlation_id
    assert correlation_id != "client-value"


def test_metrics_report_aggregate_route_status_and_latency_only() -> None:
    client.get("/api/v1/health?email=private@example.com")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain; version=0.0.4")
    assert (
        'lexaware_http_requests_total{method="GET",route="/api/v1/health",status="200"}'
        in response.text
    )
    assert "lexaware_http_request_duration_seconds_bucket" in response.text
    assert "private@example.com" not in response.text
    assert 'route="/metrics"' not in response.text


async def test_security_headers_preserve_multiple_auth_cookies() -> None:
    from app.core.middleware import SecurityHeadersMiddleware

    sent = []

    async def app(scope, receive, send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"set-cookie", b"lexaware_session=opaque"),
                    (b"set-cookie", b"lexaware_csrf=csrf"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": b"ok"})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def capture(message) -> None:
        sent.append(message)

    middleware = SecurityHeadersMiddleware(app)
    await middleware(
        {"type": "http", "method": "GET", "path": "/"},
        receive,
        capture,
    )
    headers = sent[0]["headers"]
    cookies = [value for name, value in headers if name.lower() == b"set-cookie"]
    assert cookies == [b"lexaware_session=opaque", b"lexaware_csrf=csrf"]
    assert (b"x-content-type-options", b"nosniff") in headers


def test_unhandled_exception_error_includes_response_correlation_id() -> None:
    from fastapi import APIRouter

    crash_router = APIRouter()

    @crash_router.get("/test-crash-correlation")
    async def crash_endpoint() -> None:
        raise RuntimeError("internal details must not leak")

    app.include_router(crash_router, prefix="/api/v1")
    try:
        response = client.get("/api/v1/test-crash-correlation")
        assert response.status_code == 500
        correlation_id = response.headers["x-correlation-id"]
        assert response.json()["detail"]["correlation_id"] == correlation_id
        assert "internal details" not in response.text
    finally:
        app.routes[:] = [
            route
            for route in app.routes
            if getattr(route, "path", "") != "/api/v1/test-crash-correlation"
        ]


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
