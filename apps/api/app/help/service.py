import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import record_audit_event
from app.db.models import HelpResource, Jurisdiction, ResourceStatus, Source
from app.help.schemas import (
    HelpJurisdictionRead,
    HelpResourceCreate,
    HelpResourceUpdate,
    StudentHelpResourceRead,
    VerifyHelpResource,
)
from app.provenance.service import canonical_sha256, queue_anchor, queue_transition


def _source_is_current(source: Source, now: datetime) -> bool:
    return (
        source.is_active
        and (source.effective_from is None or source.effective_from <= now)
        and (source.effective_until is None or source.effective_until >= now)
    )


def _validate_contact_bundle(
    contact_method: str, phone: str | None, contact_url: str | None, email: str | None
) -> None:
    if contact_method == "phone" and not phone:
        raise HTTPException(status_code=400, detail="A phone contact is required.")
    if contact_method == "website" and not contact_url:
        raise HTTPException(status_code=400, detail="A website URL is required.")
    if contact_method == "email" and not email:
        raise HTTPException(status_code=400, detail="An email contact is required.")
    if (
        contact_method == "multiple"
        and sum(bool(value) for value in (phone, contact_url, email)) < 2
    ):
        raise HTTPException(status_code=400, detail="Multiple contact methods require two details.")
    if not all(
        value and value.strip() for value in (phone, contact_url, email) if value is not None
    ):
        raise HTTPException(status_code=400, detail="Contact details cannot be blank.")


async def _validate_resource_scope(
    db: AsyncSession, jurisdiction_id: uuid.UUID, source_id: uuid.UUID
) -> tuple[Jurisdiction, Source]:
    jurisdiction = await db.get(Jurisdiction, jurisdiction_id)
    if not jurisdiction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jurisdiction not found.")
    source = await db.get(Source, source_id)
    if not source or source.jurisdiction_id != jurisdiction_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A source configured for the resource jurisdiction is required.",
        )
    if not source.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Active source required."
        )
    return jurisdiction, source


async def create_help_resource(
    db: AsyncSession, actor_id: uuid.UUID, req: HelpResourceCreate
) -> HelpResource:
    await _validate_resource_scope(db, req.jurisdiction_id, req.source_id)
    _validate_contact_bundle(
        req.contact_method,
        req.phone,
        req.contact_url,
        str(req.contact_email) if req.contact_email else None,
    )
    now = datetime.now(UTC)
    if req.expires_at is not None and req.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resource expiry must be in the future.",
        )

    resource = HelpResource(
        jurisdiction_id=req.jurisdiction_id,
        source_id=req.source_id,
        name=req.name.strip(),
        category=req.category.strip().lower(),
        resource_type=req.resource_type.strip().lower(),
        assistance_type=req.assistance_type.strip().lower(),
        contact_method=req.contact_method,
        description=req.description.strip() if req.description else None,
        contact_url=req.contact_url.strip() if req.contact_url else None,
        phone=req.phone.strip() if req.phone else None,
        contact_email=str(req.contact_email) if req.contact_email else None,
        expires_at=req.expires_at,
        status=ResourceStatus.RETIRED,
    )
    db.add(resource)
    await db.flush()
    await record_audit_event(
        db,
        action="help.resource.created",
        resource_type="help_resource",
        resource_id=resource.id,
        actor_id=actor_id,
        details={"jurisdiction_id": str(resource.jurisdiction_id), "status": "retired"},
    )
    await db.commit()
    await db.refresh(resource)
    return resource


async def update_help_resource(
    db: AsyncSession, actor_id: uuid.UUID, resource_id: uuid.UUID, req: HelpResourceUpdate
) -> HelpResource:
    resource = await db.get(HelpResource, resource_id)
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Help resource not found."
        )
    if resource.status != ResourceStatus.RETIRED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Retire the resource before editing it.",
        )

    changes = req.model_dump(exclude_unset=True)
    jurisdiction_id = changes.get("jurisdiction_id", resource.jurisdiction_id)
    source_id = changes.get("source_id", resource.source_id)
    if source_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A source is required before updating a resource.",
        )
    await _validate_resource_scope(db, jurisdiction_id, source_id)

    previous_version = resource.version_number
    for key, value in changes.items():
        if (
            key
            in {
                "jurisdiction_id",
                "source_id",
                "name",
                "category",
                "resource_type",
                "assistance_type",
                "contact_method",
            }
            and value is None
        ):
            raise HTTPException(status_code=400, detail=f"{key} cannot be null.")
        if key in {"category", "resource_type", "assistance_type"} and value is not None:
            value = value.strip().lower()
        elif key in {"name", "description", "contact_url", "phone"} and isinstance(value, str):
            value = value.strip() or None
        elif key == "contact_email" and value is not None:
            value = str(value)
        setattr(resource, key, value)

    resource.version_number += 1
    await queue_transition(
        db,
        object_type="help_resource",
        object_id=resource.id,
        version=previous_version,
        action="revoke",
        actor_id=actor_id,
    )

    _validate_contact_bundle(
        resource.contact_method, resource.phone, resource.contact_url, resource.contact_email
    )
    if resource.expires_at is not None and resource.expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=400, detail="Resource expiry must be in the future.")

    resource.verified_at = None
    resource.verified_by_id = None
    resource.verification_due_at = None
    resource.status = ResourceStatus.RETIRED
    await record_audit_event(
        db,
        action="help.resource.updated",
        resource_type="help_resource",
        resource_id=resource.id,
        actor_id=actor_id,
        details={"status": "retired"},
    )
    await db.commit()
    await db.refresh(resource)
    return resource


async def verify_help_resource(
    db: AsyncSession,
    actor_id: uuid.UUID,
    resource_id: uuid.UUID,
    req: VerifyHelpResource,
) -> HelpResource:
    resource = await db.get(HelpResource, resource_id)
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Help resource not found."
        )
    if resource.status != ResourceStatus.RETIRED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only retired resources can be verified and activated.",
        )
    if resource.source_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A source is required.")

    _, source = await _validate_resource_scope(db, resource.jurisdiction_id, resource.source_id)
    now = datetime.now(UTC)
    if not _source_is_current(source, now):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Current source required."
        )
    if req.verification_due_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification due date must be in the future.",
        )
    if resource.expires_at is not None and resource.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expired resources cannot be activated.",
        )

    resource.verified_at = now
    resource.verified_by_id = actor_id
    resource.verification_due_at = req.verification_due_at
    resource.status = ResourceStatus.ACTIVE
    await record_audit_event(
        db,
        action="help.resource.verified",
        resource_type="help_resource",
        resource_id=resource.id,
        actor_id=actor_id,
        details={"verification_due_at": req.verification_due_at.isoformat(), "status": "active"},
    )
    await queue_anchor(
        db,
        object_type="help_resource",
        object_id=resource.id,
        version=resource.version_number,
        content_hash=canonical_sha256(
            {
                "schema": "verified-help-resource-v1",
                "resource_id": str(resource.id),
                "version_number": resource.version_number,
                "jurisdiction_id": str(resource.jurisdiction_id),
                "source_id": str(resource.source_id),
                "category": resource.category,
                "resource_type": resource.resource_type,
                "assistance_type": resource.assistance_type,
                "contact_method": resource.contact_method,
                "verified_at": resource.verified_at.isoformat(),
                "verification_due_at": resource.verification_due_at.isoformat(),
                "expires_at": resource.expires_at.isoformat() if resource.expires_at else None,
            }
        ),
        actor_id=actor_id,
    )
    await db.commit()
    await db.refresh(resource)
    return resource


async def retire_help_resource(
    db: AsyncSession, actor_id: uuid.UUID, resource_id: uuid.UUID
) -> HelpResource:
    resource = await db.get(HelpResource, resource_id)
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Help resource not found."
        )
    resource.status = ResourceStatus.RETIRED
    await queue_transition(
        db,
        object_type="help_resource",
        object_id=resource.id,
        version=resource.version_number,
        action="revoke",
        actor_id=actor_id,
    )
    resource.verified_at = None
    resource.verified_by_id = None
    resource.verification_due_at = None
    await record_audit_event(
        db,
        action="help.resource.retired",
        resource_type="help_resource",
        resource_id=resource.id,
        actor_id=actor_id,
        details={"status": "retired"},
    )
    await db.commit()
    await db.refresh(resource)
    return resource


async def list_student_help_resources(
    db: AsyncSession,
    category: str | None = None,
    jurisdiction_code: str | None = None,
    assistance_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[StudentHelpResourceRead]:
    now = datetime.now(UTC)
    stmt = (
        select(HelpResource, Jurisdiction, Source)
        .join(Jurisdiction, HelpResource.jurisdiction_id == Jurisdiction.id)
        .join(Source, HelpResource.source_id == Source.id)
        .where(
            HelpResource.status == ResourceStatus.ACTIVE,
            HelpResource.verified_at.is_not(None),
            HelpResource.verified_by_id.is_not(None),
            HelpResource.verification_due_at > now,
            or_(HelpResource.expires_at.is_(None), HelpResource.expires_at > now),
            Source.is_active.is_(True),
            or_(Source.effective_from.is_(None), Source.effective_from <= now),
            or_(Source.effective_until.is_(None), Source.effective_until > now),
        )
    )
    if category:
        stmt = stmt.where(HelpResource.category == category.strip().lower())
    if jurisdiction_code:
        stmt = stmt.where(func.lower(Jurisdiction.code) == jurisdiction_code.strip().lower())
    if assistance_type:
        stmt = stmt.where(HelpResource.assistance_type == assistance_type.strip().lower())

    stmt = (
        stmt.order_by(func.lower(HelpResource.name), Jurisdiction.code, HelpResource.id)
        .limit(min(max(limit, 1), 100))
        .offset(max(offset, 0))
    )
    rows = (await db.execute(stmt)).all()
    return [
        StudentHelpResourceRead(
            id=resource.id,
            name=resource.name,
            category=resource.category,
            resource_type=resource.resource_type,
            assistance_type=resource.assistance_type,
            contact_method=resource.contact_method,
            description=resource.description,
            contact_url=resource.contact_url,
            phone=resource.phone,
            contact_email=resource.contact_email,
            jurisdiction=HelpJurisdictionRead(code=jurisdiction.code, name=jurisdiction.name),
            source_title=source.title,
            source_publisher=source.publisher,
            source_url=source.source_url,
            source_citation=source.citation,
            source_retrieved_at=source.retrieved_at,
            verified_at=resource.verified_at,
        )
        for resource, jurisdiction, source in rows
    ]
