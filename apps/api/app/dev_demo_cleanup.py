"""Dry-run-first, one-shot cleanup for positively identified local test fixtures.

This command is not imported by the ASGI application. It calls the existing
knowledge, complaint, and help governance services when explicitly applied.
"""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import os
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.complaints.service import archive_complaint_guide
from app.core.config import Settings, get_settings
from app.db.models import (
    AuditEvent,
    ComplaintGuide,
    ComplaintGuideVersion,
    HelpResource,
    Jurisdiction,
    KnowledgeItem,
    KnowledgeStatus,
    KnowledgeVersion,
    PublicationState,
    ResourceStatus,
    Role,
    Source,
    User,
    UserCredential,
    UserRole,
    UserStatus,
)
from app.db.session import AsyncSessionLocal, engine
from app.help.service import retire_help_resource
from app.knowledge.service import unpublish_version

_ALLOWED_ENVIRONMENTS = {"development", "local", "demo"}
_ENABLE_FLAG = "DEV_DEMO_CLEANUP_ENABLED"
_CONFIRM_FLAG = "DEV_DEMO_CLEANUP_CONFIRM"
_CONFIRM_VALUE = "ARCHIVE_IDENTIFIED_FIXTURES"
_ACTOR_ENV = "DEV_DEMO_CLEANUP_ACTOR_EMAIL"
CandidateKind = Literal["knowledge_version", "complaint_guide", "help_resource"]


@dataclass(frozen=True)
class Candidate:
    kind: CandidateKind
    record_id: str
    parent_id: str | None
    title: str
    category: str
    reason: str
    version_count: int = 0


@dataclass(frozen=True)
class CleanupPlan:
    candidates: tuple[Candidate, ...]

    def for_kind(self, kind: CandidateKind) -> tuple[Candidate, ...]:
        return tuple(candidate for candidate in self.candidates if candidate.kind == kind)


def validate_cleanup_environment(
    settings: Settings, environ: Mapping[str, str], *, apply: bool
) -> None:
    environment = settings.environment.strip().casefold()
    if environment == "production" or environment not in _ALLOWED_ENVIRONMENTS:
        raise ValueError("Demo fixture cleanup is disabled in this environment.")
    if environ.get(_ENABLE_FLAG, "").strip().casefold() != "true":
        raise ValueError("Set DEV_DEMO_CLEANUP_ENABLED=true to run this command.")
    host = settings.postgres_host.strip().casefold()
    if host not in {"localhost", "localhost."}:
        try:
            if not ipaddress.ip_address(host).is_loopback:
                raise ValueError
        except ValueError:
            raise ValueError("Demo fixture cleanup requires a loopback PostgreSQL host.") from None
    if apply and environ.get(_CONFIRM_FLAG) != _CONFIRM_VALUE:
        raise ValueError(f"--apply requires {_CONFIRM_FLAG}={_CONFIRM_VALUE}.")
    if apply and not environ.get(_ACTOR_ENV, "").strip():
        raise ValueError("--apply requires DEV_DEMO_CLEANUP_ACTOR_EMAIL for audit attribution.")


def _complaint_fixture_reason(
    title: str, jurisdiction_name: str, steps: Sequence[dict[str, object]]
) -> str | None:
    if title != "Getting help safely" or jurisdiction_name != "Test jurisdiction":
        return None
    instructions = [str(step.get("instruction", "")) for step in steps]
    if len(instructions) < 5 or not all(
        value.startswith("Guidance for ") for value in instructions
    ):
        return None
    return (
        'Exact integration fixture signature: title "Getting help safely", '
        'jurisdiction "Test jurisdiction", and generated "Guidance for <section>" steps.'
    )


def _complaint_guide_fixture_reason(
    versions: Sequence[tuple[ComplaintGuideVersion, Jurisdiction]],
) -> str | None:
    """Only archive a parent when every retained version is a known test fixture."""
    if not versions:
        return None
    reasons = [
        _complaint_fixture_reason(version.title, jurisdiction.name, version.guidance_steps)
        for version, jurisdiction in versions
    ]
    if any(reason is None for reason in reasons):
        return None
    return "All guide versions match the exact integration fixture signature."


def _help_fixture_reason(
    resource: HelpResource, jurisdiction: Jurisdiction, source: Source
) -> str | None:
    guidance_fixture = (
        jurisdiction.name == "Test jurisdiction"
        and source.title == "Verified support information"
        and source.publisher == "Test public authority"
        and source.source_url == "https://example.gov/help"
        and source.citation == "Support directory"
        and resource.name == "Campus support"
        and resource.phone == "+18005550100"
    )
    assistant_fixture = (
        jurisdiction.name == "Test jurisdiction"
        and source.title == "Test official guidance"
        and source.publisher == "Public authority"
        and source.source_url == "https://example.gov/guidance"
        and resource.name in {"Current student legal aid", "Expired student legal aid"}
        and resource.phone in {"18001234567", "18009999999"}
    )
    if guidance_fixture:
        return (
            'Exact integration fixture signature: "Campus support", test public authority, '
            "example.gov/help, Support directory, and the fixture phone number."
        )
    if assistant_fixture:
        return (
            "Exact assistant integration fixture signature: test official guidance at "
            "example.gov/guidance, test jurisdiction, fixture resource name, and fixture phone."
        )
    return None


async def collect_cleanup_plan(db: AsyncSession) -> CleanupPlan:
    candidates: list[Candidate] = []

    knowledge_rows = (
        await db.execute(
            select(KnowledgeItem, KnowledgeVersion, Jurisdiction, Source)
            .join(KnowledgeVersion, KnowledgeVersion.knowledge_item_id == KnowledgeItem.id)
            .join(Jurisdiction, Jurisdiction.id == KnowledgeItem.jurisdiction_id)
            .join(Source, Source.id == KnowledgeVersion.source_id)
            .where(
                KnowledgeVersion.publication_state == PublicationState.PUBLISHED,
                Jurisdiction.name == "Test jurisdiction",
                Source.title == "Test official guidance",
                Source.source_url == "https://example.gov/guidance",
                Source.publisher == "Public authority",
                KnowledgeItem.title == "Tenant deposit guidance",
                KnowledgeVersion.title == "Tenant deposit guidance",
                KnowledgeVersion.content
                == "Keep a copy of agreements and request an itemized explanation.",
            )
        )
    ).all()
    for item, version, _jurisdiction, _source in knowledge_rows:
        candidates.append(
            Candidate(
                kind="knowledge_version",
                record_id=str(version.id),
                parent_id=str(item.id),
                title=version.title or item.title,
                category=item.category,
                reason=(
                    "Exact assistant test fixture: matching test jurisdiction/source, canonical "
                    "fixture title, and fixture body text."
                ),
            )
        )

    complaint_rows = (
        await db.execute(
            select(ComplaintGuide, ComplaintGuideVersion, Jurisdiction)
            .join(ComplaintGuideVersion, ComplaintGuideVersion.guide_id == ComplaintGuide.id)
            .join(Jurisdiction, Jurisdiction.id == ComplaintGuideVersion.jurisdiction_id)
            .where(ComplaintGuide.status == KnowledgeStatus.ACTIVE)
            .options(selectinload(ComplaintGuide.versions))
        )
    ).all()
    complaint_groups: dict[
        str, tuple[ComplaintGuide, list[tuple[ComplaintGuideVersion, Jurisdiction]]]
    ] = {}
    for guide, version, jurisdiction in complaint_rows:
        key = str(guide.id)
        if key not in complaint_groups:
            complaint_groups[key] = (guide, [])
        complaint_groups[key][1].append((version, jurisdiction))
    for guide, version_rows in complaint_groups.values():
        reason = _complaint_guide_fixture_reason(version_rows)
        if reason is None:
            continue
        versions = [version for version, _jurisdiction in version_rows]
        candidates.append(
            Candidate(
                kind="complaint_guide",
                record_id=str(guide.id),
                parent_id=None,
                title=versions[0].title,
                category=versions[0].category,
                reason=reason,
                version_count=len(versions),
            )
        )

    help_rows = (
        await db.execute(
            select(HelpResource, Jurisdiction, Source)
            .join(Jurisdiction, Jurisdiction.id == HelpResource.jurisdiction_id)
            .join(Source, Source.id == HelpResource.source_id)
            .where(HelpResource.status == ResourceStatus.ACTIVE)
        )
    ).all()
    for resource, jurisdiction, source in help_rows:
        reason = _help_fixture_reason(resource, jurisdiction, source)
        if reason is None:
            continue
        candidates.append(
            Candidate(
                kind="help_resource",
                record_id=str(resource.id),
                parent_id=None,
                title=resource.name,
                category=resource.category,
                reason=reason,
            )
        )

    return CleanupPlan(tuple(candidates))


async def _admin_actor(db: AsyncSession, email: str) -> User:
    result = await db.execute(
        select(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.name == "admin", User.status == UserStatus.ACTIVE)
        .options(selectinload(User.roles).selectinload(UserRole.role))
    )
    admins = list(result.scalars().unique())
    for admin in admins:
        credential = await db.scalar(
            select(UserCredential).where(UserCredential.user_id == admin.id)
        )
        if credential is not None and credential.email.casefold() == email.strip().casefold():
            return admin
    raise ValueError("The configured cleanup actor must be an active administrator account.")


def _print_plan(plan: CleanupPlan) -> None:
    groups: tuple[tuple[CandidateKind, str], ...] = (
        ("knowledge_version", "knowledge versions"),
        ("complaint_guide", "complaint guides"),
        ("help_resource", "help resources"),
    )
    for kind, label in groups:
        rows = plan.for_kind(kind)
        version_count = (
            sum(row.version_count for row in rows) if kind == "complaint_guide" else len(rows)
        )
        print(f"{label}: {len(rows)} record(s), {version_count} version(s)")
        for row in rows:
            print(
                f"  id={row.record_id} title={row.title!r} category={row.category!r} "
                f"versions={row.version_count} reason={row.reason}"
            )


async def _apply_plan(db: AsyncSession, actor: User, plan: CleanupPlan) -> None:
    completed: list[Candidate] = []
    failures: list[tuple[Candidate, str]] = []
    audit_events_created = 0
    provenance_revokes_queued = 0

    async def apply_one(candidate: Candidate) -> None:
        nonlocal audit_events_created, provenance_revokes_queued
        before_audit = await db.scalar(select(func.count(AuditEvent.id))) or 0
        before_revokes = (
            await db.scalar(
                select(func.count(AuditEvent.id)).where(
                    AuditEvent.action == "provenance.revoke_requested"
                )
            )
            or 0
        )
        try:
            if candidate.kind == "knowledge_version":
                await unpublish_version(
                    db,
                    publisher_id=actor.id,
                    version_id=uuid.UUID(candidate.record_id),
                    reason=(
                        "Local demo fixture cleanup: positively identified integration test data."
                    ),
                )
            elif candidate.kind == "complaint_guide":
                await archive_complaint_guide(
                    db, actor_id=actor.id, guide_id=uuid.UUID(candidate.record_id)
                )
            else:
                await retire_help_resource(
                    db, actor_id=actor.id, resource_id=uuid.UUID(candidate.record_id)
                )
        except Exception as exc:
            await db.rollback()
            failures.append((candidate, type(exc).__name__))
            return

        after_audit = await db.scalar(select(func.count(AuditEvent.id))) or 0
        after_revokes = (
            await db.scalar(
                select(func.count(AuditEvent.id)).where(
                    AuditEvent.action == "provenance.revoke_requested"
                )
            )
            or 0
        )
        audit_events_created += after_audit - before_audit
        provenance_revokes_queued += after_revokes - before_revokes
        completed.append(candidate)

    for candidate in plan.for_kind("knowledge_version"):
        await apply_one(candidate)
    for candidate in plan.for_kind("complaint_guide"):
        await apply_one(candidate)
    for candidate in plan.for_kind("help_resource"):
        await apply_one(candidate)

    for candidate in completed:
        print(f"APPLIED {candidate.kind} id={candidate.record_id} title={candidate.title!r}")
    print(f"Successfully processed {len(completed)} candidate record(s).")
    print(f"Audit events created: {audit_events_created}")
    print(f"Provenance revoke operations queued: {provenance_revokes_queued}")
    print(f"Failures: {len(failures)}")
    for candidate, error_type in failures:
        print(f"FAILED {candidate.kind} id={candidate.record_id} error={error_type}")
    print("Failed document jobs, provider errors, reports, and feedback were not modified.")


async def run_cleanup(*, apply: bool, environ: Mapping[str, str] | None = None) -> CleanupPlan:
    environment = os.environ if environ is None else environ
    settings = get_settings()
    validate_cleanup_environment(settings, environment, apply=apply)
    async with AsyncSessionLocal() as db:
        plan = await collect_cleanup_plan(db)
        _print_plan(plan)
        if apply:
            actor = await _admin_actor(db, environment[_ACTOR_ENV])
            print("Applying through existing governance services.")
            await _apply_plan(db, actor, plan)
        else:
            print("DRY RUN ONLY: no records or audit events were changed. Use --apply to mutate.")
        return plan


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Inspect only (the default).")
    mode.add_argument("--apply", action="store_true", help="Apply governed fixture retirement.")
    args = parser.parse_args(argv)

    async def execute() -> None:
        try:
            await run_cleanup(apply=args.apply)
        finally:
            await engine.dispose()

    try:
        asyncio.run(execute())
    except (ValueError, SQLAlchemyError) as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
