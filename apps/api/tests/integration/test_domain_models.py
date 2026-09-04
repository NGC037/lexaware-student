from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    Document,
    DocumentAccess,
    DocumentPermission,
    Jurisdiction,
    KnowledgeItem,
    KnowledgeVersion,
    PublicationState,
    Role,
    Source,
    User,
    UserRole,
)
from app.db.session import AsyncSessionLocal


async def test_domain_models_preserve_ownership_and_relationships() -> None:
    suffix = uuid4().hex
    async with AsyncSessionLocal() as session:
        user = User(external_subject=f"integration-user-{suffix}")
        role = Role(name=f"integration-reviewer-{suffix}")
        jurisdiction = Jurisdiction(code=f"IN-{suffix[:8]}", name="India")
        session.add_all([user, role, jurisdiction])
        await session.flush()

        source = Source(
            jurisdiction=jurisdiction,
            title=f"Integration source {suffix}",
            source_url="https://example.invalid/source",
            retrieved_at=datetime.now(UTC),
            content_hash=f"integration-source-hash-{suffix}",
        )
        item = KnowledgeItem(
            jurisdiction=jurisdiction,
            slug=f"integration-knowledge-{suffix}",
            title="Integration knowledge",
        )
        document = Document(
            owner=user,
            storage_key=f"integration/documents/{suffix}",
            original_filename="notice.pdf",
            media_type="application/pdf",
            size_bytes=10,
        )
        session.add_all(
            [
                UserRole(user=user, role=role),
                source,
                item,
                document,
            ]
        )
        await session.flush()

        version = KnowledgeVersion(
            knowledge_item=item,
            source=source,
            version_number=1,
            content="Reviewed content",
            publication_state=PublicationState.APPROVED,
        )
        grant = DocumentAccess(
            document=document,
            user=user,
            granted_by=user,
            permission=DocumentPermission.VIEW,
        )
        session.add_all([version, grant])
        await session.flush()

        assert document.owner is user
        assert grant.document is document
        assert version.source is source
        assert item.jurisdiction is jurisdiction


async def test_domain_constraints_reject_duplicate_access_and_invalid_version() -> None:
    suffix = uuid4().hex
    async with AsyncSessionLocal() as session:
        user = User(external_subject=f"constraint-user-{suffix}")
        jurisdiction = Jurisdiction(code=f"IN-CT-{suffix[:8]}", name="Chhattisgarh")
        source = Source(
            jurisdiction=jurisdiction,
            title=f"Constraint source {suffix}",
            source_url="https://example.invalid/constraint-source",
            retrieved_at=datetime.now(UTC),
            content_hash=f"constraint-source-hash-{suffix}",
        )
        item = KnowledgeItem(
            jurisdiction=jurisdiction,
            slug=f"constraint-knowledge-{suffix}",
            title="Constraint knowledge",
        )
        document = Document(
            owner=user,
            storage_key=f"constraint/documents/{suffix}",
            original_filename="document.txt",
            media_type="text/plain",
            size_bytes=0,
        )
        session.add_all([user, jurisdiction, source, item, document])
        await session.flush()

        session.add(
            KnowledgeVersion(
                knowledge_item=item,
                source=source,
                version_number=0,
                content="Invalid version",
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()

    async with AsyncSessionLocal() as session:
        user = User(external_subject=f"duplicate-user-{suffix}")
        jurisdiction = Jurisdiction(code=f"IN-DUP-{suffix[:8]}", name="Delhi")
        document = Document(
            owner=user,
            storage_key=f"duplicate/documents/{suffix}",
            original_filename="document.txt",
            media_type="text/plain",
            size_bytes=0,
        )
        session.add_all([user, jurisdiction, document])
        await session.flush()
        session.add(
            DocumentAccess(document=document, user=user, granted_by=user, permission="view")
        )
        await session.flush()
        session.add(
            DocumentAccess(document=document, user=user, granted_by=user, permission="view")
        )
        with pytest.raises(IntegrityError):
            await session.flush()
