"""Transactional outbox, canonical domain hashing, and ledger verification."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import record_audit_event
from app.core.config import get_settings
from app.db.models import ProvenanceAnchor

_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def canonical_sha256(value: dict[str, Any]) -> str:
    """Hash canonical UTF-8 JSON with sorted keys and compact separators."""
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


async def queue_anchor(
    db: AsyncSession,
    *,
    object_type: str,
    object_id: uuid.UUID,
    version: int,
    content_hash: str,
    actor_id: uuid.UUID | None,
) -> ProvenanceAnchor:
    if object_type not in {"knowledge_version", "help_resource", "document_report"}:
        raise ValueError("Unsupported provenance object type.")
    if version < 1 or not _HASH_PATTERN.fullmatch(content_hash):
        raise ValueError("Invalid provenance version or SHA-256 hash.")
    existing = await db.scalar(
        select(ProvenanceAnchor).where(
            ProvenanceAnchor.object_type == object_type,
            ProvenanceAnchor.object_id == object_id,
            ProvenanceAnchor.version == version,
        )
    )
    if existing:
        if existing.content_hash != content_hash:
            raise ValueError("An immutable provenance version cannot change its hash.")
        return existing
    anchor = ProvenanceAnchor(
        object_type=object_type,
        object_id=object_id,
        version=version,
        content_hash=content_hash,
        network=get_settings().fabric_network,
        anchor_status="pending",
        action="anchor",
        next_attempt_at=datetime.now(UTC),
        requested_by_id=actor_id,
    )
    db.add(anchor)
    await db.flush()
    await record_audit_event(
        db,
        action="provenance.anchor_requested",
        resource_type="provenance_anchor",
        resource_id=anchor.id,
        actor_id=actor_id,
        details={"object_type": object_type, "version": version},
    )
    return anchor


async def queue_transition(
    db: AsyncSession,
    *,
    object_type: str,
    object_id: uuid.UUID,
    version: int,
    action: str,
    actor_id: uuid.UUID | None,
    superseded_by_version: int | None = None,
) -> ProvenanceAnchor | None:
    if action not in {"revoke", "supersede"}:
        raise ValueError("Invalid provenance transition.")
    anchor = await db.scalar(
        select(ProvenanceAnchor)
        .where(
            ProvenanceAnchor.object_type == object_type,
            ProvenanceAnchor.object_id == object_id,
            ProvenanceAnchor.version == version,
        )
        .with_for_update()
    )
    if anchor is None or anchor.anchor_status in {"revoked", "superseded"}:
        return anchor
    anchor.action = action
    anchor.anchor_status = "pending"
    anchor.superseded_by_version = superseded_by_version
    anchor.next_attempt_at = datetime.now(UTC)
    await record_audit_event(
        db,
        action=f"provenance.{action}_requested",
        resource_type="provenance_anchor",
        resource_id=anchor.id,
        actor_id=actor_id,
        details={"version": version},
    )
    return anchor


async def claim_anchor(db: AsyncSession) -> uuid.UUID | None:
    now = datetime.now(UTC)
    row = await db.scalar(
        select(ProvenanceAnchor)
        .where(ProvenanceAnchor.anchor_status == "pending", ProvenanceAnchor.next_attempt_at <= now)
        .order_by(ProvenanceAnchor.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if row is None:
        return None
    row.next_attempt_at = now + timedelta(minutes=10)
    await db.commit()
    return row.id


async def process_anchor(db: AsyncSession, anchor_id: uuid.UUID) -> str:
    from app.provenance import gateway

    anchor = await db.get(ProvenanceAnchor, anchor_id)
    if anchor is None:
        return "missing"
    try:
        if anchor.action == "anchor":
            result = await asyncio.to_thread(
                gateway.verify_record, anchor.object_type, str(anchor.object_id), anchor.version
            )
            if result.get("exists"):
                if result.get("content_hash") != anchor.content_hash:
                    anchor.last_failure_code = "ledger_hash_conflict"
                    anchor.next_attempt_at = datetime.now(UTC) + timedelta(hours=1)
                    await db.commit()
                    return "pending"
            else:
                result = await asyncio.to_thread(
                    gateway.anchor_record,
                    anchor.object_type,
                    str(anchor.object_id),
                    anchor.version,
                    anchor.content_hash,
                )
            anchor.transaction_id = str(result["transaction_id"])
            anchor.anchor_status = "anchored"
            anchor.anchored_at = datetime.now(UTC)
        else:
            current = await asyncio.to_thread(
                gateway.verify_record, anchor.object_type, str(anchor.object_id), anchor.version
            )
            if not current.get("exists"):
                created = await asyncio.to_thread(
                    gateway.anchor_record,
                    anchor.object_type,
                    str(anchor.object_id),
                    anchor.version,
                    anchor.content_hash,
                )
                anchor.transaction_id = str(created["transaction_id"])
            elif current.get("content_hash") != anchor.content_hash:
                anchor.last_failure_code = "ledger_hash_conflict"
                anchor.next_attempt_at = datetime.now(UTC) + timedelta(hours=1)
                await db.commit()
                return "pending"
            result = await asyncio.to_thread(
                gateway.transition_record,
                anchor.object_type,
                str(anchor.object_id),
                anchor.version,
                anchor.action,
                anchor.superseded_by_version,
            )
            anchor.transaction_id = str(result.get("last_transaction_id", result["transaction_id"]))
            anchor.anchor_status = "revoked" if anchor.action == "revoke" else "superseded"
            anchor.revoked_at = datetime.now(UTC)
        anchor.last_failure_code = None
        await record_audit_event(
            db,
            action=f"provenance.{anchor.anchor_status}",
            resource_type="provenance_anchor",
            resource_id=anchor.id,
            details={"object_type": anchor.object_type, "version": anchor.version},
        )
        await db.commit()
        return anchor.anchor_status
    except Exception as exc:
        # Only safe category codes are persisted; never persist gateway responses.
        code = getattr(exc, "code", "gateway_unavailable")
        anchor.attempts += 1
        anchor.last_failure_code = str(code)[:64]
        anchor.next_attempt_at = datetime.now(UTC) + timedelta(
            seconds=min(3600, 5 * (2 ** min(anchor.attempts, 9)))
        )
        await db.commit()
        return "pending"


async def verify_anchor(anchor: ProvenanceAnchor) -> dict[str, object]:
    from app.provenance.gateway import verify_record

    try:
        record = await asyncio.to_thread(
            verify_record, anchor.object_type, str(anchor.object_id), anchor.version
        )
    except Exception:
        return {"available": False, "verified": False}
    exists = record.get("exists") is True
    matches = exists and record.get("content_hash") == anchor.content_hash
    return {
        "available": True,
        "verified": bool(matches),
        "ledger_status": record.get("status") if exists else None,
        "transaction_id": record.get("transaction_id") if exists else None,
        "anchored_at": record.get("anchored_at") if exists else None,
        "superseded_by_version": record.get("superseded_by_version") if exists else None,
    }
