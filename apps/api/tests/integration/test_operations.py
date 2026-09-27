from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from test_knowledge import create_test_user_with_role

from app.db.models import AuditEvent, Document, DocumentProcessingJob, DocumentStatus
from app.db.session import AsyncSessionLocal


@pytest.mark.asyncio
async def test_operations_dashboard_requires_admin(async_client: httpx.AsyncClient) -> None:
    admin, _ = await create_test_user_with_role("admin")
    student, _ = await create_test_user_with_role("student")

    assert (await async_client.get("/api/v1/admin/operations")).status_code == 401
    assert (await async_client.get("/api/v1/admin/operations", cookies=student)).status_code == 403
    response = await async_client.get("/api/v1/admin/operations", cookies=admin)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "stale_content",
        "failed_analyses",
        "provider_errors",
        "user_reports",
        "unresolved_feedback",
    }
    assert all(isinstance(items, list) for items in body.values())


@pytest.mark.asyncio
async def test_operations_queues_show_safe_triage_metadata_and_resolve_feedback(
    async_client: httpx.AsyncClient,
) -> None:
    admin, user = await create_test_user_with_role("admin")
    provider_id, report_id, feedback_id = (str(uuid4()) for _ in range(3))
    provider_event = AuditEvent(
        actor_id=user.id,
        action="assistant.request.completed",
        resource_type="assistant_request",
        request_id=provider_id,
        details={
            "failure_category": "provider_timeout",
            "provider_status": "unavailable",
            "prompt": "must never be returned",
        },
    )
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        document = Document(
            owner_id=user.id,
            storage_key=f"private/{uuid4()}",
            original_filename="private-student-file.pdf",
            media_type="application/pdf",
            size_bytes=100,
            status=DocumentStatus.FAILED,
        )
        session.add(document)
        await session.flush()
        job = DocumentProcessingJob(
            document_id=document.id,
            status="failed",
            available_at=now,
            failure_code="analysis_failed",
        )
        session.add(job)
        await session.flush()
        session.add_all(
            [
                provider_event,
                AuditEvent(
                    actor_id=user.id,
                    action="assistant.feedback.submitted",
                    resource_type="assistant_response",
                    request_id=report_id,
                    details={"rating": "not_helpful", "reported": True},
                ),
                AuditEvent(
                    actor_id=user.id,
                    action="assistant.feedback.submitted",
                    resource_type="assistant_response",
                    request_id=feedback_id,
                    details={"rating": "not_helpful", "reported": False},
                ),
            ]
        )
        await session.commit()

    response = await async_client.get("/api/v1/admin/operations", cookies=admin)
    assert response.status_code == 200
    body = response.json()
    assert any(row["id"] == str(job.id) for row in body["failed_analyses"])
    assert any(row["id"] == str(provider_event.id) for row in body["provider_errors"])
    assert any(row["id"] == report_id for row in body["user_reports"])
    assert any(row["id"] == feedback_id for row in body["unresolved_feedback"])
    assert "private-student-file.pdf" not in response.text
    assert "must never be returned" not in response.text
    csrf_response = await async_client.get("/api/v1/auth/csrf", cookies=admin)
    csrf_token = csrf_response.json()["csrf_token"]
    csrf_cookie = csrf_response.cookies.get("lexaware_csrf")
    resolved = await async_client.post(
        f"/api/v1/admin/operations/feedback/{report_id}/resolve",
        cookies=admin | {"lexaware_csrf": csrf_cookie or ""},
        headers={"X-CSRF-Token": csrf_token, "Origin": "http://test"},
    )
    assert resolved.status_code == 204
    after = await async_client.get("/api/v1/admin/operations", cookies=admin)
    assert all(row["id"] != report_id for row in after.json()["unresolved_feedback"])
