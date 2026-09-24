from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.assistant.provider import DeterministicMockProvider, ProviderUnavailableError
from app.assistant.router import get_ai_provider
from app.assistant.schemas import ProviderRequest, ProviderResponse
from app.auth.tokens import create_session
from app.db.models import (
    AuditEvent,
    HelpResource,
    Jurisdiction,
    KnowledgeItem,
    KnowledgeVersion,
    PublicationState,
    ResourceStatus,
    Role,
    Source,
    User,
    UserRole,
)
from app.db.session import AsyncSessionLocal
from app.main import app


class RecordingProvider(DeterministicMockProvider):
    def __init__(self) -> None:
        self.called = False

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        self.called = True
        return await super().generate(request)


class FailingProvider:
    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        raise ProviderUnavailableError("sensitive provider error payload")

    async def health(self) -> bool:
        return False

    def model_metadata(self) -> dict[str, str]:
        return {"provider": "test", "model": "offline"}


async def setup_assistant_data() -> tuple[str, str, str, str]:
    suffix = uuid4().hex[:10]
    async with AsyncSessionLocal() as session:
        role = (
            await session.execute(select(Role).where(Role.name == "student"))
        ).scalar_one_or_none()
        if role is None:
            role = Role(name="student", description="Student role")
            session.add(role)
            await session.flush()
        user = User(display_name="Assistant test student")
        session.add(user)
        await session.flush()
        session.add(UserRole(user_id=user.id, role_id=role.id))
        jurisdiction = Jurisdiction(code=f"T-{suffix}", name="Test jurisdiction")
        session.add(jurisdiction)
        await session.flush()
        source = Source(
            jurisdiction_id=jurisdiction.id,
            title="Test official guidance",
            publisher="Public authority",
            source_url="https://example.gov/guidance",
            citation="Guidance 1",
            retrieved_at=datetime.now(UTC),
            is_active=True,
        )
        session.add(source)
        await session.flush()
        item = KnowledgeItem(
            jurisdiction_id=jurisdiction.id,
            category="housing",
            topic="tenant deposit",
            audience="students",
            slug=f"tenant-guidance-{suffix}",
            title="Tenant deposit guidance",
        )
        session.add(item)
        await session.flush()
        version = KnowledgeVersion(
            knowledge_item_id=item.id,
            source_id=source.id,
            version_number=1,
            title="Tenant deposit guidance",
            summary="A governed overview of deposit concerns.",
            content="Keep a copy of agreements and request an itemized explanation.",
            tags=["tenant"],
            keywords=["deposit"],
            synonyms="rental bond",
            publication_state=PublicationState.PUBLISHED,
            effective_from=datetime.now(UTC) - timedelta(days=1),
            reviewed_at=datetime.now(UTC) - timedelta(days=1),
            reviewed_by_id=user.id,
            review_due_at=datetime.now(UTC) + timedelta(days=60),
            published_at=datetime.now(UTC) - timedelta(days=1),
            published_by_id=user.id,
        )
        session.add(version)
        now = datetime.now(UTC)
        session.add(
            HelpResource(
                jurisdiction_id=jurisdiction.id,
                source_id=source.id,
                name="Current student legal aid",
                category="legal_aid",
                resource_type="service",
                assistance_type="legal_advice",
                contact_method="phone",
                phone="18001234567",
                verified_at=now - timedelta(days=1),
                verified_by_id=user.id,
                verification_due_at=now + timedelta(days=60),
                status=ResourceStatus.ACTIVE,
            )
        )
        session.add(
            HelpResource(
                jurisdiction_id=jurisdiction.id,
                source_id=source.id,
                name="Expired student legal aid",
                category="legal_aid",
                resource_type="service",
                assistance_type="legal_advice",
                contact_method="phone",
                phone="18009999999",
                verified_at=now - timedelta(days=90),
                verified_by_id=user.id,
                verification_due_at=now - timedelta(days=1),
                status=ResourceStatus.ACTIVE,
            )
        )
        await session.commit()
        await session.refresh(version)
        assert version.search_vector
        user_id, jurisdiction_code = user.id, jurisdiction.code
        version_id, slug = str(version.id), item.slug
    token, _ = await create_session(user_id)
    return token, jurisdiction_code, version_id, slug


@pytest.mark.asyncio
async def test_assistant_retrieves_postgres_fts_and_audits_metadata_only(
    async_client: httpx.AsyncClient,
) -> None:
    token, jurisdiction, version_id, slug = await setup_assistant_data()
    # This term is present only in governed body content, not the title/category/topic
    # fallback fields, so a hit proves PostgreSQL FTS and the trigger-generated vector.
    body_search = await async_client.get("/api/v1/knowledge/articles", params={"q": "itemized"})
    assert body_search.status_code == 200
    assert any(article["slug"] == slug for article in body_search.json())
    provider = RecordingProvider()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    try:
        response = await async_client.post(
            "/api/v1/assistant/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "tenant deposit", "topic": "secret", "jurisdiction": jurisdiction},
        )
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert provider.called and payload["status"] == "answer"
    assert payload["sources"][0]["knowledge_reference"] == f"{slug}:v1"
    assert f"knowledge:{slug}:v1" in payload["trace"]["knowledge_references"]
    async with AsyncSessionLocal() as session:
        event = (
            (
                await session.execute(
                    select(AuditEvent).where(
                        AuditEvent.action == "assistant.request.completed",
                        AuditEvent.details["correlation_id"].as_string()
                        == payload["trace"]["correlation_id"],
                    )
                )
            )
            .scalars()
            .first()
        )
        assert event is not None
        assert "secret" not in str(event.details)
        assert version_id not in str(event.details)
        assert event.request_id == payload["trace"]["correlation_id"]


@pytest.mark.asyncio
async def test_high_risk_skips_provider_and_missing_auth_is_401(
    async_client: httpx.AsyncClient,
) -> None:
    token, jurisdiction, _, _ = await setup_assistant_data()
    provider = RecordingProvider()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    try:
        response = await async_client.post(
            "/api/v1/assistant/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "I am in immediate danger", "jurisdiction": jurisdiction},
        )
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)
    assert response.status_code == 200 and response.json()["status"] == "escalate"
    assert not provider.called
    urgent = response.json()["urgent_resources"]
    assert [resource["name"] for resource in urgent] == ["Current student legal aid"]
    unauthenticated = await async_client.post(
        "/api/v1/assistant/messages",
        json={"message": "tenant rights", "jurisdiction": jurisdiction},
    )
    assert unauthenticated.status_code == 401
    csrf_missing = await async_client.post(
        "/api/v1/assistant/messages",
        cookies={"lexaware_session": token},
        json={"message": "tenant rights", "jurisdiction": jurisdiction},
    )
    assert csrf_missing.status_code == 403


@pytest.mark.asyncio
async def test_inactive_and_expired_source_is_excluded_from_assistant_context(
    async_client: httpx.AsyncClient,
) -> None:
    token, jurisdiction, version_id, _ = await setup_assistant_data()
    provider = RecordingProvider()
    async with AsyncSessionLocal() as session:
        version = await session.get(KnowledgeVersion, version_id)
        assert version is not None
        source = await session.get(Source, version.source_id)
        assert source is not None
        source_id = source.id
        source.is_active = False
        await session.commit()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    try:
        inactive = await async_client.post(
            "/api/v1/assistant/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "tenant deposit", "jurisdiction": jurisdiction},
        )
        async with AsyncSessionLocal() as session:
            source = await session.get(Source, source_id)
            assert source is not None
            source.is_active = True
            source.effective_until = datetime.now(UTC) - timedelta(days=1)
            await session.commit()
        expired = await async_client.post(
            "/api/v1/assistant/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "tenant deposit", "jurisdiction": jurisdiction},
        )
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)
        async with AsyncSessionLocal() as session:
            source = await session.get(Source, source_id)
            if source is not None:
                source.is_active = True
                source.effective_until = None
                await session.commit()
    assert inactive.status_code == 200 and inactive.json()["status"] == "clarify"
    assert expired.status_code == 200 and expired.json()["status"] == "clarify"
    assert not provider.called


@pytest.mark.asyncio
async def test_expired_review_content_is_not_retrieved(async_client: httpx.AsyncClient) -> None:
    token, jurisdiction, version_id, _ = await setup_assistant_data()
    async with AsyncSessionLocal() as session:
        version = await session.get(KnowledgeVersion, version_id)
        assert version is not None
        version.review_due_at = datetime.now(UTC) - timedelta(days=1)
        await session.commit()
    provider = RecordingProvider()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    try:
        response = await async_client.post(
            "/api/v1/assistant/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "tenant deposit", "jurisdiction": jurisdiction},
        )
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)
    assert response.status_code == 200 and response.json()["status"] == "clarify"
    assert not provider.called


@pytest.mark.asyncio
async def test_provider_failure_is_safe_and_validation_does_not_echo_input(
    async_client: httpx.AsyncClient,
) -> None:
    token, jurisdiction, _, _ = await setup_assistant_data()
    app.dependency_overrides[get_ai_provider] = FailingProvider
    try:
        response = await async_client.post(
            "/api/v1/assistant/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "tenant deposit", "jurisdiction": jurisdiction},
        )
        invalid = await async_client.post(
            "/api/v1/assistant/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "sensitive-invalid-text", "extra": "invalid"},
        )
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)
    assert response.status_code == 200
    assert response.json()["error_code"] == "ASSISTANT_PROVIDER_UNAVAILABLE"
    assert "sensitive provider error payload" not in response.text
    assert invalid.status_code == 422 and "sensitive-invalid-text" not in invalid.text
