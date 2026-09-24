from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.db.models import (
    AuditEvent,
    ComplaintGuideVersion,
    HelpResource,
    Jurisdiction,
    Role,
    User,
    UserCredential,
    UserRole,
)
from app.db.session import AsyncSessionLocal


async def _user(role_name: str) -> dict[str, str]:
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        role = (
            await session.execute(select(Role).where(Role.name == role_name))
        ).scalar_one_or_none()
        if role is None:
            role = Role(name=role_name, description=role_name)
            session.add(role)
            await session.flush()
        user = User(display_name=f"Test {role_name}")
        session.add(user)
        await session.flush()
        from app.auth.service import hash_password

        session.add(
            UserCredential(
                user_id=user.id,
                email=f"{role_name}_{suffix}@example.com",
                password_hash=hash_password("SecurePassword123!"),
            )
        )
        session.add(UserRole(user_id=user.id, role_id=role.id))
        await session.commit()
    from app.auth.tokens import create_session

    token, _ = await create_session(str(user.id))
    return {"lexaware_session": token}


def _steps() -> list[dict[str, object]]:
    sections = [
        "immediate_safety",
        "safety_considerations",
        "preserve_evidence",
        "reporting_options",
        "information_to_prepare",
        "checklist",
        "escalation",
    ]
    return [
        {
            "position": i,
            "section": section,
            "title": f"Step {i}",
            "instruction": f"Guidance for {section}.",
        }
        for i, section in enumerate(sections, start=1)
    ]


async def _guide_payload(jurisdiction_id: str, **changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "slug": f"safety-guide-{uuid4().hex[:8]}",
        "title": "Getting help safely",
        "category": "safety",
        "jurisdiction_id": jurisdiction_id,
        "audience": "students",
        "short_description": "Options for finding support.",
        "guidance_steps": _steps(),
        "effective_from": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
        "effective_until": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        "review_due_at": (datetime.now(UTC) + timedelta(days=60)).isoformat(),
    }
    payload.update(changes)
    return payload


async def _jurisdiction_and_source(
    client: httpx.AsyncClient, admin: dict[str, str]
) -> tuple[str, str]:
    jurisdiction = await client.post(
        "/api/v1/admin/knowledge/jurisdictions",
        json={"code": f"T-{uuid4().hex[:6].upper()}", "name": "Test jurisdiction"},
        cookies=admin,
    )
    assert jurisdiction.status_code == 201
    jurisdiction_id = jurisdiction.json()["id"]
    source = await client.post(
        "/api/v1/admin/knowledge/sources",
        json={
            "jurisdiction_id": jurisdiction_id,
            "title": "Verified support information",
            "publisher": "Test public authority",
            "source_url": "https://example.gov/help",
            "citation": "Support directory",
        },
        cookies=admin,
    )
    assert source.status_code == 201
    return jurisdiction_id, source.json()["id"]


@pytest.mark.asyncio
async def test_complaint_guide_governance_and_student_visibility(
    async_client: httpx.AsyncClient,
) -> None:
    admin = await _user("admin")
    reviewer = await _user("reviewer")
    publisher = await _user("publisher")
    student = await _user("student")
    jurisdiction_id, _ = await _jurisdiction_and_source(async_client, admin)
    payload = await _guide_payload(jurisdiction_id)

    denied = await async_client.post(
        "/api/v1/admin/complaints/guides", json=payload, cookies=student
    )
    assert denied.status_code == 403
    created = await async_client.post(
        "/api/v1/admin/complaints/guides", json=payload, cookies=reviewer
    )
    assert created.status_code == 201, created.text
    guide = created.json()
    version = guide["versions"][0]
    assert version["publication_state"] == "draft"
    assert (await async_client.get(f"/api/v1/complaints/guides/{guide['slug']}")).status_code == 404
    assert "summary" not in guide and "reporter_id" not in guide

    null_required = await async_client.put(
        f"/api/v1/admin/complaints/guides/versions/{version['id']}",
        json={"title": None},
        cookies=reviewer,
    )
    assert null_required.status_code == 422

    bad_sequence = await async_client.put(
        f"/api/v1/admin/complaints/guides/versions/{version['id']}",
        json={"guidance_steps": []},
        cookies=reviewer,
    )
    assert bad_sequence.status_code == 200
    incomplete = await async_client.post(
        f"/api/v1/admin/complaints/guides/versions/{version['id']}/submit-review", cookies=reviewer
    )
    assert incomplete.status_code == 400
    await async_client.put(
        f"/api/v1/admin/complaints/guides/versions/{version['id']}",
        json={"guidance_steps": _steps()},
        cookies=reviewer,
    )
    submitted = await async_client.post(
        f"/api/v1/admin/complaints/guides/versions/{version['id']}/submit-review", cookies=reviewer
    )
    assert submitted.status_code == 200
    approved = await async_client.post(
        f"/api/v1/admin/complaints/guides/versions/{version['id']}/review",
        json={"decision": "approve", "notes": "Reviewed."},
        cookies=reviewer,
    )
    assert approved.status_code == 200
    publish = await async_client.post(
        f"/api/v1/admin/complaints/guides/versions/{version['id']}/publish", cookies=publisher
    )
    assert publish.status_code == 200, publish.text

    listing = await async_client.get(
        "/api/v1/complaints/guides", params={"category": "SAFETY", "jurisdiction": "T-" + "INVALID"}
    )
    assert listing.status_code == 200 and not listing.json()
    detail = await async_client.get(f"/api/v1/complaints/guides/{guide['slug']}")
    assert detail.status_code == 200
    assert [step["position"] for step in detail.json()["guidance_steps"]] == list(range(1, 8))
    assert detail.json()["jurisdiction"]["id"] == jurisdiction_id
    assert detail.json()["guidance_steps"][0]["section"] == "immediate_safety"
    assert detail.json()["guidance_steps"][-1]["section"] == "escalation"
    assert "reviewed_by_id" not in detail.json()
    assert (
        await async_client.get("/api/v1/complaints/guides", params={"audience": "staff"})
    ).json() == []
    assert (
        await async_client.get("/api/v1/complaints/guides", params={"category": "safety"})
    ).json()

    future_payload = await _guide_payload(
        jurisdiction_id,
        slug=f"future-guide-{uuid4().hex[:8]}",
        effective_from=(datetime.now(UTC) + timedelta(days=2)).isoformat(),
    )
    future_created = await async_client.post(
        "/api/v1/admin/complaints/guides", json=future_payload, cookies=reviewer
    )
    future_version = future_created.json()["versions"][0]
    for path, data in (
        ("", {"guidance_steps": _steps()}),
        ("/submit-review", None),
    ):
        response = (
            await async_client.put(
                f"/api/v1/admin/complaints/guides/versions/{future_version['id']}{path}",
                json=data,
                cookies=reviewer,
            )
            if path == ""
            else await async_client.post(
                f"/api/v1/admin/complaints/guides/versions/{future_version['id']}{path}",
                cookies=reviewer,
            )
        )
        assert response.status_code == 200
    await async_client.post(
        f"/api/v1/admin/complaints/guides/versions/{future_version['id']}/review",
        json={"decision": "approve"},
        cookies=reviewer,
    )
    await async_client.post(
        f"/api/v1/admin/complaints/guides/versions/{future_version['id']}/publish",
        cookies=publisher,
    )
    assert (
        await async_client.get(f"/api/v1/complaints/guides/{future_payload['slug']}")
    ).status_code == 404
    async with AsyncSessionLocal() as session:
        expired_version = await session.get(ComplaintGuideVersion, future_version["id"])
        assert expired_version is not None
        expired_version.effective_from = datetime.now(UTC) - timedelta(days=3)
        expired_version.effective_until = datetime.now(UTC) - timedelta(days=1)
        await session.commit()
    assert (
        await async_client.get(f"/api/v1/complaints/guides/{future_payload['slug']}")
    ).status_code == 404
    unpublished = await async_client.post(
        f"/api/v1/admin/complaints/guides/versions/{future_version['id']}/unpublish",
        cookies=publisher,
    )
    assert unpublished.status_code == 200
    assert (
        await async_client.get(f"/api/v1/complaints/guides/{future_payload['slug']}")
    ).status_code == 404
    archived = await async_client.post(
        f"/api/v1/admin/complaints/guides/{guide['id']}/archive", cookies=publisher
    )
    assert archived.status_code == 204
    assert (await async_client.get(f"/api/v1/complaints/guides/{guide['slug']}")).status_code == 404

    async with AsyncSessionLocal() as session:
        events = (
            (
                await session.execute(
                    select(AuditEvent).where(
                        AuditEvent.resource_type.in_(("complaint_guide", "complaint_guide_version"))
                    )
                )
            )
            .scalars()
            .all()
        )
        assert {event.action for event in events} >= {
            "complaint.guide.created",
            "complaint.guide.version.submitted_review",
            "complaint.guide.version.approved",
            "complaint.guide.version.published",
        }
        assert all("Reviewed." not in str(event.details) for event in events)


@pytest.mark.asyncio
async def test_help_resources_require_current_verification_and_source_scope(
    async_client: httpx.AsyncClient,
) -> None:
    admin = await _user("admin")
    reviewer = await _user("reviewer")
    student = await _user("student")
    jurisdiction_id, source_id = await _jurisdiction_and_source(async_client, admin)
    category = f"support-{uuid4().hex[:8]}"
    other_jurisdiction = await async_client.post(
        "/api/v1/admin/knowledge/jurisdictions",
        json={"code": f"X-{uuid4().hex[:6].upper()}", "name": "Other jurisdiction"},
        cookies=admin,
    )
    bad_scope = await async_client.post(
        "/api/v1/admin/help/resources",
        json={
            "jurisdiction_id": other_jurisdiction.json()["id"],
            "source_id": source_id,
            "name": "Campus support",
            "category": "safety",
            "resource_type": "hotline",
            "assistance_type": "counselling",
            "contact_method": "phone",
            "phone": "+18005550100",
        },
        cookies=admin,
    )
    assert bad_scope.status_code == 400
    payload = {
        "jurisdiction_id": jurisdiction_id,
        "source_id": source_id,
        "name": "Campus support",
        "category": category,
        "resource_type": "hotline",
        "assistance_type": "counselling",
        "contact_method": "multiple",
        "phone": "+18005550100",
        "contact_url": "https://example.gov/support",
        "description": "Student support contact.",
        "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
    }
    invalid_contact = dict(payload, contact_url=None)
    invalid_contact["contact_method"] = "website"
    invalid = await async_client.post(
        "/api/v1/admin/help/resources", json=invalid_contact, cookies=admin
    )
    assert invalid.status_code == 422
    unsafe_url = dict(payload, contact_method="website", contact_url="javascript:alert(1)")
    assert (
        await async_client.post("/api/v1/admin/help/resources", json=unsafe_url, cookies=admin)
    ).status_code == 422
    naive_expiry = dict(payload, expires_at="2030-01-01T00:00:00")
    assert (
        await async_client.post("/api/v1/admin/help/resources", json=naive_expiry, cookies=admin)
    ).status_code == 422
    created = await async_client.post(
        "/api/v1/admin/help/resources", json=payload, cookies=reviewer
    )
    assert created.status_code == 201, created.text
    resource = created.json()
    assert resource["status"] == "retired"
    assert (await async_client.get("/api/v1/help", params={"category": category})).json() == []
    assert (
        await async_client.post(
            f"/api/v1/admin/help/resources/{resource['id']}/verify",
            json={"verification_due_at": (datetime.now(UTC) - timedelta(days=1)).isoformat()},
            cookies=admin,
        )
    ).status_code == 400
    verified = await async_client.post(
        f"/api/v1/admin/help/resources/{resource['id']}/verify",
        json={"verification_due_at": (datetime.now(UTC) + timedelta(days=7)).isoformat()},
        cookies=admin,
    )
    assert verified.status_code == 200, verified.text
    assert "verified_by_id" not in verified.json()
    results = (await async_client.get("/api/v1/help", params={"jurisdiction": "invalid"})).json()
    assert results == []
    async with AsyncSessionLocal() as session:
        jurisdiction = await session.get(Jurisdiction, jurisdiction_id)
        assert jurisdiction is not None
        jurisdiction_code = jurisdiction.code
    assert (
        await async_client.get("/api/v1/help", params={"jurisdiction": jurisdiction_code})
    ).json()
    results = (await async_client.get("/api/v1/help", params={"category": category})).json()
    assert len(results) == 1
    record = results[0]
    assert record["status"] == "verified_current"
    assert record["source_title"] == "Verified support information"
    assert "verified_by_id" not in record and "source_id" not in record
    assert (
        await async_client.get("/api/v1/help", params={"assistance_type": "legal"})
    ).json() == []

    async with AsyncSessionLocal() as session:
        stale_resource = await session.get(HelpResource, resource["id"])
        assert stale_resource is not None
        stale_resource.verification_due_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
    assert (await async_client.get("/api/v1/help", params={"category": category})).json() == []
    async with AsyncSessionLocal() as session:
        stale_resource = await session.get(HelpResource, resource["id"])
        assert stale_resource is not None
        stale_resource.verification_due_at = datetime.now(UTC) + timedelta(days=7)
        stale_resource.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
    assert (await async_client.get("/api/v1/help", params={"category": category})).json() == []

    denied = await async_client.post(
        f"/api/v1/admin/help/resources/{resource['id']}/retire", cookies=student
    )
    assert denied.status_code == 403
    retired = await async_client.post(
        f"/api/v1/admin/help/resources/{resource['id']}/retire", cookies=admin
    )
    assert retired.status_code == 200
    assert (await async_client.get("/api/v1/help", params={"category": category})).json() == []
    async with AsyncSessionLocal() as session:
        help_events = (
            (
                await session.execute(
                    select(AuditEvent).where(AuditEvent.resource_type == "help_resource")
                )
            )
            .scalars()
            .all()
        )
        assert {event.action for event in help_events} >= {
            "help.resource.created",
            "help.resource.verified",
            "help.resource.retired",
        }
