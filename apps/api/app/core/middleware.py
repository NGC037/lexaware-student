"""ASGI middleware for LexAware Student API."""

from __future__ import annotations

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings


class RequestBodyTooLarge(Exception):
    pass


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
                # Convert list to dict to overwrite any pre-existing headers
                # (like those set by FileResponse) instead of appending duplicates.
                headers_dict = {
                    k.decode("latin-1").lower(): v.decode("latin-1")
                    for k, v in message.get("headers", [])
                }
                headers_dict["x-content-type-options"] = "nosniff"
                headers_dict["x-frame-options"] = "DENY"
                headers_dict["x-xss-protection"] = "0"
                headers_dict["referrer-policy"] = "strict-origin-when-cross-origin"
                headers_dict["permissions-policy"] = "geolocation=(), microphone=(), camera=()"

                if is_production:
                    headers_dict["strict-transport-security"] = (
                        "max-age=31536000; includeSubDomains"
                    )

                message = dict(message)
                message["headers"] = [
                    (k.encode("latin-1"), v.encode("latin-1")) for k, v in headers_dict.items()
                ]
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
