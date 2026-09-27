from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.db.models import (
    AuditEvent,
    ComplaintGuide,
    ComplaintGuideVersion,
    HelpResource,
    Jurisdiction,
    KnowledgeItem,
    KnowledgeStatus,
    KnowledgeVersion,
    ProvenanceAnchor,
    PublicationState,
    ResourceStatus,
    Source,
    User,
)
from app.db.session import AsyncSessionLocal
from app.dev_demo_cleanup import CleanupPlan, _apply_plan, collect_cleanup_plan, run_cleanup
from app.provenance.service import queue_anchor


def _fixture_steps() -> list[dict[str, object]]:
    return [
        {"position": index, "instruction": f"Guidance for {name}."}
        for index, name in enumerate(
            ("immediate_safety", "safety", "evidence", "reporting", "prepare"), start=1
        )
    ]


async def _create_cleanup_fixtures() -> tuple[str, str, str, str]:
    suffix = uuid4().hex
    async with AsyncSessionLocal() as db:
        actor = User(display_name="Cleanup integration actor")
        jurisdiction = Jurisdiction(code=f"T-{suffix[:10]}", name="Test jurisdiction")
        db.add_all([actor, jurisdiction])
        await db.flush()
        source = Source(
            jurisdiction_id=jurisdiction.id,
            title="Test official guidance",
            publisher="Public authority",
            source_url="https://example.gov/guidance",
            citation="Guidance 1",
            retrieved_at=datetime.now(UTC),
        )
        db.add(source)
        await db.flush()

        item = KnowledgeItem(
            jurisdiction_id=jurisdiction.id,
            category="housing",
            topic="tenant deposit",
            slug=f"tenant-guidance-{suffix}",
            title="Tenant deposit guidance",
        )
        db.add(item)
        await db.flush()
        knowledge_version = KnowledgeVersion(
            knowledge_item_id=item.id,
            source_id=source.id,
            version_number=1,
            title="Tenant deposit guidance",
            content="Keep a copy of agreements and request an itemized explanation.",
            publication_state=PublicationState.PUBLISHED,
            effective_from=datetime.now(UTC) - timedelta(days=1),
            reviewed_at=datetime.now(UTC) - timedelta(days=1),
            reviewed_by_id=actor.id,
            published_at=datetime.now(UTC) - timedelta(days=1),
            published_by_id=actor.id,
        )
        db.add(knowledge_version)
        legitimate_item = KnowledgeItem(
            jurisdiction_id=jurisdiction.id,
            category="housing",
            topic="rental agreement",
            slug=f"legitimate-guidance-{suffix}",
            title="Reviewed rental guidance",
        )
        db.add(legitimate_item)
        await db.flush()
        legitimate_version = KnowledgeVersion(
            knowledge_item_id=legitimate_item.id,
            source_id=source.id,
            version_number=1,
            title="Reviewed rental guidance",
            content="Keep the signed rental agreement and consult a local adviser.",
            publication_state=PublicationState.PUBLISHED,
            reviewed_at=datetime.now(UTC),
            reviewed_by_id=actor.id,
        )
        db.add(legitimate_version)

        guide = ComplaintGuide(slug=f"safety-guide-{suffix}")
        mixed_guide = ComplaintGuide(slug=f"mixed-guide-{suffix}")
        db.add_all([guide, mixed_guide])
        await db.flush()
        guide_fixture_version = ComplaintGuideVersion(
            guide_id=guide.id,
            version_number=1,
            title="Getting help safely",
            category="safety",
            jurisdiction_id=jurisdiction.id,
            short_description="Fixture guidance.",
            guidance_steps=_fixture_steps(),
            publication_state=PublicationState.PUBLISHED,
        )
        mixed_fixture_version = ComplaintGuideVersion(
            guide_id=mixed_guide.id,
            version_number=1,
            title="Getting help safely",
            category="safety",
            jurisdiction_id=jurisdiction.id,
            short_description="Fixture guidance.",
            guidance_steps=_fixture_steps(),
            publication_state=PublicationState.PUBLISHED,
        )
        mixed_legitimate_version = ComplaintGuideVersion(
            guide_id=mixed_guide.id,
            version_number=2,
            title="Reviewed safety guidance",
            category="safety",
            jurisdiction_id=jurisdiction.id,
            short_description="Reviewed content that must be preserved.",
            guidance_steps=[{"position": 1, "instruction": "Contact the local authority."}],
            publication_state=PublicationState.PUBLISHED,
        )
        db.add_all([guide_fixture_version, mixed_fixture_version, mixed_legitimate_version])

        fixture_help = HelpResource(
            jurisdiction_id=jurisdiction.id,
            source_id=source.id,
            name="Current student legal aid",
            category="legal_aid",
            resource_type="service",
            assistance_type="legal_advice",
            contact_method="phone",
            phone="18001234567",
            verified_at=datetime.now(UTC),
            verified_by_id=actor.id,
            verification_due_at=datetime.now(UTC) + timedelta(days=30),
            status=ResourceStatus.ACTIVE,
        )
        legitimate_help = HelpResource(
            jurisdiction_id=jurisdiction.id,
            source_id=source.id,
            name="Current student legal aid",
            category="legal_aid",
            resource_type="service",
            assistance_type="legal_advice",
            contact_method="phone",
            phone="1800114000",
            status=ResourceStatus.ACTIVE,
        )
        db.add_all([fixture_help, legitimate_help])
        await db.flush()
        await queue_anchor(
            db,
            object_type="knowledge_version",
            object_id=knowledge_version.id,
            version=1,
            content_hash="a" * 64,
            actor_id=actor.id,
        )
        await queue_anchor(
            db,
            object_type="help_resource",
            object_id=fixture_help.id,
            version=1,
            content_hash="b" * 64,
            actor_id=actor.id,
        )
        await db.commit()
        return (
            str(actor.id),
            str(knowledge_version.id),
            str(legitimate_version.id),
            str(guide.id),
            str(mixed_guide.id),
            str(fixture_help.id),
            str(legitimate_help.id),
        )


@pytest.mark.asyncio
async def test_cleanup_dry_run_is_read_only_and_apply_uses_governance_and_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (
        actor_id,
        knowledge_version_id,
        legitimate_version_id,
        fixture_guide_id,
        mixed_guide_id,
        fixture_help_id,
        legitimate_help_id,
    ) = await _create_cleanup_fixtures()
    monkeypatch.setattr(
        "app.dev_demo_cleanup.get_settings",
        lambda: Settings(environment="development", postgres_host="localhost"),
    )
    enabled = {"DEV_DEMO_CLEANUP_ENABLED": "true"}

    async with AsyncSessionLocal() as db:
        audit_count_before_dry_run = await db.scalar(select(func.count(AuditEvent.id)))
    plan = await run_cleanup(apply=False, environ=enabled)
    assert knowledge_version_id in {
        candidate.record_id for candidate in plan.for_kind("knowledge_version")
    }
    assert fixture_guide_id in {
        candidate.record_id for candidate in plan.for_kind("complaint_guide")
    }
    assert mixed_guide_id not in {
        candidate.record_id for candidate in plan.for_kind("complaint_guide")
    }
    assert fixture_help_id in {candidate.record_id for candidate in plan.for_kind("help_resource")}
    # Apply only this test's explicit records; other test modules share the disposable DB.
    target_ids = {knowledge_version_id, fixture_guide_id, fixture_help_id}
    plan = CleanupPlan(tuple(candidate for candidate in plan.candidates if candidate.record_id in target_ids))
    assert len(plan.candidates) == 3
    assert "DRY RUN ONLY" in capsys.readouterr().out

    async with AsyncSessionLocal() as db:
        version = await db.get(KnowledgeVersion, knowledge_version_id)
        legitimate_version = await db.get(KnowledgeVersion, legitimate_version_id)
        guide = await db.get(ComplaintGuide, fixture_guide_id)
        mixed_guide = await db.get(ComplaintGuide, mixed_guide_id)
        fixture_help = await db.get(HelpResource, fixture_help_id)
        legitimate_help = await db.get(HelpResource, legitimate_help_id)
        assert version is not None and version.publication_state == PublicationState.PUBLISHED
        assert legitimate_version is not None
        assert legitimate_version.publication_state == PublicationState.PUBLISHED
        assert guide is not None and guide.status == KnowledgeStatus.ACTIVE
        assert mixed_guide is not None and mixed_guide.status == KnowledgeStatus.ACTIVE
        assert fixture_help is not None and fixture_help.status == ResourceStatus.ACTIVE
        assert legitimate_help is not None and legitimate_help.status == ResourceStatus.ACTIVE
        assert await db.scalar(select(func.count(AuditEvent.id))) == audit_count_before_dry_run

        actor = await db.get(User, actor_id)
        assert actor is not None
        await _apply_plan(db, actor, plan)
        applied_output = capsys.readouterr().out
        assert "Successfully processed 3 candidate record(s)." in applied_output
        assert "Audit events created: 6" in applied_output
        assert "Provenance revoke operations queued: 2" in applied_output

    async with AsyncSessionLocal() as db:
        version = await db.get(KnowledgeVersion, knowledge_version_id)
        legitimate_version = await db.get(KnowledgeVersion, legitimate_version_id)
        guide = await db.get(ComplaintGuide, fixture_guide_id)
        mixed_guide = await db.get(ComplaintGuide, mixed_guide_id)
        fixture_help = await db.get(HelpResource, fixture_help_id)
        legitimate_help = await db.get(HelpResource, legitimate_help_id)
        assert version is not None and version.publication_state == PublicationState.ARCHIVED
        assert legitimate_version is not None
        assert legitimate_version.publication_state == PublicationState.PUBLISHED
        assert guide is not None and guide.status == KnowledgeStatus.ARCHIVED
        assert mixed_guide is not None and mixed_guide.status == KnowledgeStatus.ACTIVE
        assert fixture_help is not None and fixture_help.status == ResourceStatus.RETIRED
        assert fixture_help.verified_at is None and fixture_help.verified_by_id is None
        assert legitimate_help is not None and legitimate_help.status == ResourceStatus.ACTIVE
        anchors = (
            (
                await db.execute(
                    select(ProvenanceAnchor).where(
                        ProvenanceAnchor.object_type.in_(("knowledge_version", "help_resource")),
                        ProvenanceAnchor.action == "revoke",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(anchors) == 2
        assert all(anchor.anchor_status == "pending" for anchor in anchors)
        assert (
            await db.scalar(
                select(func.count(AuditEvent.id)).where(
                    AuditEvent.action == "provenance.revoke_requested"
                )
            )
            == 2
        )

        second_plan = await collect_cleanup_plan(db)
        assert not target_ids.intersection(
            {candidate.record_id for candidate in second_plan.candidates}
        )
        before_audits = await db.scalar(select(func.count(AuditEvent.id)))
        idempotent_plan = CleanupPlan(
            tuple(candidate for candidate in second_plan.candidates if candidate.record_id in target_ids)
        )
        await _apply_plan(db, actor, idempotent_plan)
        assert await db.scalar(select(func.count(AuditEvent.id))) == before_audits
        capsys.readouterr()
