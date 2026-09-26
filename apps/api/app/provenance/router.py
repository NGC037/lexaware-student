"""Authenticated, object-authorized provenance status and verification API."""

import uuid
from datetime import UTC, datetime
from typing import cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_authenticated_user
from app.auth.service import record_audit_event
from app.db.models import (
    Document,
    DocumentAnalysisReport,
    HelpResource,
    Jurisdiction,
    KnowledgeItem,
    KnowledgeVersion,
    ProvenanceAnchor,
    ResourceStatus,
    Source,
    User,
)
from app.db.session import get_db_session
from app.knowledge.eligibility import student_knowledge_eligibility
from app.provenance.service import verify_anchor

provenance_router = APIRouter(prefix="/provenance", tags=["provenance"])


class ProvenanceVerification(BaseModel):
    id: uuid.UUID
    object_type: str
    object_id: uuid.UUID
    version: int
    content_hash: str
    network: str
    anchor_status: str
    transaction_id: str | None
    anchored_at: datetime | None
    revoked_at: datetime | None
    superseded_by_version: int | None
    attempts: int
    last_failure_code: str | None
    verification_available: bool
    verified: bool
    ledger_status: str | None


async def _can_view_anchor(db: AsyncSession, anchor: ProvenanceAnchor, user: User) -> bool:
    now = datetime.now(UTC)
    governance_roles = {role.role.name for role in user.roles}
    is_governance = bool(governance_roles.intersection({"admin", "reviewer", "publisher"}))
    if anchor.object_type == "document_report":
        return bool(
            await db.scalar(
                select(DocumentAnalysisReport.id)
                .join(Document, DocumentAnalysisReport.document_id == Document.id)
                .where(
                    DocumentAnalysisReport.id == anchor.object_id,
                    Document.owner_id == user.id,
                    Document.deleted_at.is_(None),
                )
            )
        )
    if anchor.object_type == "knowledge_version":
        if is_governance:
            return bool(
                await db.scalar(
                    select(KnowledgeVersion.id).where(KnowledgeVersion.id == anchor.object_id)
                )
            )
        return bool(
            await db.scalar(
                select(KnowledgeVersion.id)
                .join(KnowledgeItem, KnowledgeVersion.knowledge_item_id == KnowledgeItem.id)
                .join(Source, KnowledgeVersion.source_id == Source.id)
                .where(
                    KnowledgeVersion.id == anchor.object_id,
                    *student_knowledge_eligibility(now),
                )
            )
        )
    if anchor.object_type == "help_resource":
        if is_governance:
            return bool(
                await db.scalar(select(HelpResource.id).where(HelpResource.id == anchor.object_id))
            )
        return bool(
            await db.scalar(
                select(HelpResource.id)
                .join(Jurisdiction, HelpResource.jurisdiction_id == Jurisdiction.id)
                .join(Source, HelpResource.source_id == Source.id)
                .where(
                    HelpResource.id == anchor.object_id,
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
        )
    return False


@provenance_router.get("/{anchor_id}", response_model=ProvenanceVerification)
async def verify_provenance(
    anchor_id: uuid.UUID,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
) -> ProvenanceVerification:
    anchor = await db.get(ProvenanceAnchor, anchor_id)
    if anchor is None or not await _can_view_anchor(db, anchor, current_user):
        raise HTTPException(status_code=404, detail="Provenance record not found.")
    result = await verify_anchor(anchor)
    await record_audit_event(
        db,
        action="provenance.verification_performed",
        resource_type="provenance_anchor",
        resource_id=anchor.id,
        actor_id=current_user.id,
        details={"verification_available": result["available"], "verified": result["verified"]},
    )
    await db.commit()
    return ProvenanceVerification(
        id=anchor.id,
        object_type=anchor.object_type,
        object_id=anchor.object_id,
        version=anchor.version,
        content_hash=anchor.content_hash,
        network=anchor.network,
        anchor_status=anchor.anchor_status,
        transaction_id=anchor.transaction_id,
        anchored_at=anchor.anchored_at,
        revoked_at=anchor.revoked_at,
        superseded_by_version=anchor.superseded_by_version,
        attempts=anchor.attempts,
        last_failure_code=anchor.last_failure_code,
        verification_available=bool(result["available"]),
        verified=bool(result["verified"]),
        ledger_status=cast(str | None, result.get("ledger_status")),
    )
