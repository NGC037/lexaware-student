"""Small HTTP adapter for the isolated Fabric Gateway service."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import get_settings


class ProvenanceGatewayError(Exception):
    """Safe gateway failure code without exposing upstream details."""

    def __init__(self, code: str = "gateway_unavailable") -> None:
        self.code = code
        super().__init__(code)


def _call(path: str, payload: dict[str, object]) -> dict[str, Any]:
    settings = get_settings()
    token = (
        settings.fabric_gateway_token.get_secret_value()
        if settings.fabric_gateway_token is not None
        else ""
    )
    if not token:
        raise ProvenanceGatewayError("gateway_not_configured")
    request = Request(
        f"{settings.fabric_gateway_endpoint.rstrip('/')}{path}",
        data=json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Gateway-Token": token},
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.provenance_request_timeout_seconds) as response:
            result = json.loads(response.read(16_384))
    except HTTPError as exc:
        raise ProvenanceGatewayError("gateway_rejected") from exc
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise ProvenanceGatewayError("gateway_unavailable") from exc
    if not isinstance(result, dict):
        raise ProvenanceGatewayError("invalid_gateway_response")
    return result


def anchor_record(
    object_type: str,
    object_id: str,
    version: int,
    content_hash: str,
) -> dict[str, Any]:
    return _call(
        "/anchor",
        {
            "object_type": object_type,
            "object_id": object_id,
            "version": version,
            "content_hash": content_hash,
        },
    )


def verify_record(object_type: str, object_id: str, version: int) -> dict[str, Any]:
    return _call(
        "/verify",
        {"object_type": object_type, "object_id": object_id, "version": version},
    )


def transition_record(
    object_type: str,
    object_id: str,
    version: int,
    action: str,
    superseded_by_version: int | None = None,
) -> dict[str, Any]:
    return _call(
        "/transition",
        {
            "object_type": object_type,
            "object_id": object_id,
            "version": version,
            "action": action,
            "superseded_by_version": superseded_by_version,
        },
    )
