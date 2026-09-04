from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api import router as router_module
from app.main import app


def test_readiness_endpoint_reports_ready(monkeypatch) -> None:
    monkeypatch.setattr(
        router_module,
        "check_database_connection",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        router_module,
        "check_redis_connection",
        AsyncMock(return_value=True),
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "LexAware Student",
        "dependencies": {"database": "ok", "redis": "ok"},
    }


def test_readiness_endpoint_reports_unavailable_dependency(monkeypatch) -> None:
    monkeypatch.setattr(
        router_module,
        "check_database_connection",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        router_module,
        "check_redis_connection",
        AsyncMock(return_value=True),
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "service": "LexAware Student",
        "dependencies": {"database": "unavailable", "redis": "ok"},
    }
