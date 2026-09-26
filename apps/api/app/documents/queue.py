from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.service import record_audit_event
from app.core.config import get_settings
from app.db.models import (
    Document,
    DocumentAnalysisReport,
    DocumentProcessingJob,
    DocumentStatus,
)
from app.documents.analysis import (
    classify_document,
    create_report_manifest,
    extract_pdf_with_timeout,
)
from app.documents.lifecycle import transition_document
from app.documents.storage import ObjectStorage


class MalwareScanner(Protocol):
    def scan(self, data: bytes) -> str: ...


class MalwareScannerError(RuntimeError):
    """Scanner responded with an unknown/error verdict; processing must retry."""


class ScannerUnavailable:
    """Safe test/deployment fallback when no scanner integration is configured."""

    def scan(self, data: bytes) -> str:
        return "unavailable"


async def claim_next_document_job(session: AsyncSession, job_id: UUID | None = None) -> UUID | None:
    now = datetime.now(UTC)
    conditions = [
        or_(
            and_(
                DocumentProcessingJob.status == "queued",
                DocumentProcessingJob.available_at <= now,
            ),
            and_(
                DocumentProcessingJob.status == "processing",
                DocumentProcessingJob.claimed_at.is_not(None),
                DocumentProcessingJob.claimed_at <= now - timedelta(minutes=10),
            ),
        )
    ]
    if job_id is not None:
        conditions.append(DocumentProcessingJob.id == job_id)
    result = await session.execute(
        select(DocumentProcessingJob)
        .where(*conditions)
        .order_by(DocumentProcessingJob.available_at, DocumentProcessingJob.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return None
    job.status = "processing"
    job.claimed_at = datetime.now(UTC)
    job.attempts += 1
    document_result = await session.execute(
        select(Document).where(Document.id == job.document_id, Document.deleted_at.is_(None))
    )
    document = document_result.scalar_one_or_none()
    if document is None:
        job.status = "failed"
        job.failure_code = "document_missing"
        job.finished_at = datetime.now(UTC)
        await session.commit()
        return None
    transition_document(document, DocumentStatus.PROCESSING)
    await record_audit_event(
        session,
        action="document.processing_started",
        resource_type="document",
        resource_id=document.id,
        actor_id=document.owner_id,
        details={"attempt": job.attempts},
    )
    await session.commit()
    return job.id


async def run_document_job(
    session: AsyncSession,
    job_id: UUID,
    *,
    storage: ObjectStorage,
    scanner: MalwareScanner | None = None,
) -> str:
    settings = get_settings()
    result = await session.execute(
        select(DocumentProcessingJob)
        .options(selectinload(DocumentProcessingJob.document))
        .where(DocumentProcessingJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return "missing"
    document = job.document
    if job.status == "completed":
        return "completed"
    if job.status != "processing" or document.deleted_at is not None:
        return job.status
    existing = await session.scalar(
        select(DocumentAnalysisReport.id).where(DocumentAnalysisReport.document_id == document.id)
    )
    if existing is not None:
        job.status = "completed"
        job.finished_at = datetime.now(UTC)
        await session.commit()
        return "completed"
    try:
        payload = await asyncio.to_thread(storage.get, document.storage_key)
        scan_state = await asyncio.to_thread((scanner or ScannerUnavailable()).scan, payload)
        document.malware_scan_state = scan_state
        if scan_state == "error":
            raise MalwareScannerError
        if scan_state != "clean":
            if scan_state == "infected":
                try:
                    await asyncio.to_thread(storage.delete, document.storage_key)
                except Exception:
                    # Keep the object inaccessible via the failed document state; do not analyze it.
                    pass
                transition_document(document, DocumentStatus.FAILED)
                job.status = "failed"
                job.failure_code = "malware_detected"
                job.finished_at = datetime.now(UTC)
            else:
                transition_document(document, DocumentStatus.VALIDATED)
                job.status = "blocked"
                job.failure_code = "scanner_unavailable"
                job.finished_at = datetime.now(UTC)
            await record_audit_event(
                session,
                action="document.processing_blocked",
                resource_type="document",
                resource_id=document.id,
                actor_id=document.owner_id,
                details={"reason": job.failure_code, "scanner_state": scan_state},
            )
            await session.commit()
            return job.status

        extraction = await extract_pdf_with_timeout(
            payload, settings.document_extraction_timeout_seconds
        )
        classification = classify_document(extraction.pages)
        manifest, manifest_hash = create_report_manifest(document.id, extraction, classification)
        document.page_count = len(extraction.pages)
        document.extraction_metadata = {
            "quality": extraction.quality,
            "character_count": extraction.character_count,
            "needs_ocr": extraction.needs_ocr,
            "warnings": list(extraction.warnings),
        }
        document.document_type = classification.document_type
        document.classification_confidence = classification.confidence
        document.needs_ocr = extraction.needs_ocr
        transition_document(document, DocumentStatus.EXTRACTED)
        if extraction.needs_ocr or not classification.supported:
            transition_document(document, DocumentStatus.UNSUPPORTED)
        else:
            transition_document(document, DocumentStatus.ANALYZING)
            transition_document(document, DocumentStatus.COMPLETED)
        session.add(
            DocumentAnalysisReport(
                document_id=document.id,
                report_version=1,
                manifest=manifest,
                manifest_sha256=manifest_hash,
            )
        )
        job.status = "completed"
        job.finished_at = datetime.now(UTC)
        job.failure_code = None
        await record_audit_event(
            session,
            action="document.processing_completed",
            resource_type="document",
            resource_id=document.id,
            actor_id=document.owner_id,
            details={"status": document.status.value, "page_count": document.page_count},
        )
        await record_audit_event(
            session,
            action="document.report_generated",
            resource_type="document_report",
            resource_id=document.id,
            actor_id=document.owner_id,
            details={"manifest_sha256": manifest_hash, "finding_count": len(manifest["findings"])},
        )
        await session.commit()
        return job.status
    except Exception as exc:
        await session.rollback()
        result = await session.execute(
            select(DocumentProcessingJob)
            .options(selectinload(DocumentProcessingJob.document))
            .where(DocumentProcessingJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if job is None:
            return "missing"
        document = job.document
        if isinstance(exc, MalwareScannerError):
            document.malware_scan_state = "error"
        job.failure_code = _safe_failure_code(exc)
        if job.attempts < settings.document_worker_max_attempts:
            job.status = "queued"
            job.available_at = datetime.now(UTC) + timedelta(seconds=min(2**job.attempts * 5, 300))
            document.status = DocumentStatus.PROCESSING
        else:
            job.status = "failed"
            job.finished_at = datetime.now(UTC)
            transition_document(document, DocumentStatus.FAILED)
        await record_audit_event(
            session,
            action="document.processing_failed",
            resource_type="document",
            resource_id=document.id,
            actor_id=document.owner_id,
            details={"failure_code": job.failure_code, "attempt": job.attempts},
        )
        await session.commit()
        return job.status


def _safe_failure_code(error: Exception) -> str:
    code = str(error) if isinstance(error, ValueError) else "processing_failed"
    allowed = {
        "password_protected",
        "page_limit_exceeded",
        "extraction_limit_exceeded",
        "extraction_timeout",
    }
    return code if code in allowed else "processing_failed"


async def retry_document_job(session: AsyncSession, document: Document) -> bool:
    job = await session.scalar(
        select(DocumentProcessingJob).where(DocumentProcessingJob.document_id == document.id)
    )
    if job is None or job.status not in {"failed", "blocked"}:
        return False
    job.status = "queued"
    job.failure_code = None
    job.available_at = datetime.now(UTC)
    job.finished_at = None
    if document.status == DocumentStatus.FAILED:
        transition_document(document, DocumentStatus.VALIDATED)
    await session.commit()
    return True
