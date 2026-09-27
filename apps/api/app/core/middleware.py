"""ASGI middleware for LexAware Student API."""

from __future__ import annotations

import json
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings
from app.core.metrics import http_metrics


class RequestBodyTooLarge(Exception):
    pass


class RequestCorrelationIdMiddleware:
    """Attach a server-generated correlation ID to every HTTP request/response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        correlation_id = str(uuid.uuid4())
        scope.setdefault("state", {})["correlation_id"] = correlation_id
        started_at = time.perf_counter()
        scope["state"]["request_started_at"] = started_at

        async def send_with_correlation_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                if scope.get("path") != "/metrics":
                    route = getattr(scope.get("route"), "path", "unmatched")
                    api_prefix = get_settings().api_v1_prefix.rstrip("/")
                    if (
                        route != "unmatched"
                        and scope.get("path", "").startswith(f"{api_prefix}/")
                        and not route.startswith(f"{api_prefix}/")
                    ):
                        route = f"{api_prefix}{route}"
                    method = scope.get("method", "OTHER").upper()
                    if method not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}:
                        method = "OTHER"
                    http_metrics.observe(
                        method,
                        route,
                        int(message["status"]),
                        time.perf_counter() - started_at,
                    )
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"x-correlation-id"
                ]
                headers.append((b"x-correlation-id", correlation_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_correlation_id)


class UploadBodySizeLimitMiddleware:
    """Bound multipart upload bodies before Starlette spools parsed file parts."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        settings = get_settings()
        self.path = f"{settings.api_v1_prefix.rstrip('/')}/documents"
        self.max_body_bytes = settings.document_max_upload_bytes + 65_536

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or scope.get("path", "").rstrip("/") != self.path
        ):
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_body_bytes:
                    await self._reject(send)
                    return
            except ValueError:
                await self._reject(send)
                return

        received_bytes = 0

        async def limited_receive() -> Message:
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_body_bytes:
                    raise RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestBodyTooLarge:
            await self._reject(send)

    @staticmethod
    async def _reject(send: Send) -> None:
        body = json.dumps(
            {
                "detail": {
                    "code": "request_too_large",
                    "message": "The upload exceeds the request size limit.",
                }
            }
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


class SecurityHeadersMiddleware:
    """Append defensive HTTP security headers to all responses.

    Headers applied:
    - ``X-Content-Type-Options: nosniff`` - prevent MIME sniffing.
    - ``X-Frame-Options: DENY`` - prevent clickjacking via framing.
    - ``X-XSS-Protection: 0`` - disable legacy browser XSS filter
      (per OWASP guidance; modern browsers use CSP instead).
    - ``Referrer-Policy: strict-origin-when-cross-origin`` - limit
      referrer leakage across origins.
    - ``Permissions-Policy: geolocation=(), microphone=(), camera=()``
      - explicitly deny unused browser APIs.
    - ``Strict-Transport-Security`` - sent in production only.
      Sending HSTS over HTTP on localhost causes browsers to cache the
      directive and refuse plain HTTP to localhost for up to a year,
      creating a hard-to-recover developer experience problem.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        settings = get_settings()
        self._is_production = settings.is_production

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        is_production = self._is_production

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                security_headers = {
                    "x-content-type-options": "nosniff",
                    "x-frame-options": "DENY",
                    "x-xss-protection": "0",
                    "referrer-policy": "strict-origin-when-cross-origin",
                    "permissions-policy": "geolocation=(), microphone=(), camera=()",
                }
                if is_production:
                    security_headers["strict-transport-security"] = (
                        "max-age=31536000; includeSubDomains"
                    )

                # Preserve repeated headers such as Set-Cookie. Rebuilding all
                # headers in a dict silently dropped one of the auth cookies.
                replaced = {name.encode("latin-1") for name in security_headers}
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() not in replaced
                ]
                headers.extend(
                    (name.encode("latin-1"), value.encode("latin-1"))
                    for name, value in security_headers.items()
                )

                message = dict(message)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
