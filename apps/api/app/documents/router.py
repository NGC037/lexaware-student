from __future__ import annotations

import asyncio
import hmac
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import require_authenticated_user, verify_csrf_protection
from app.auth.service import record_audit_event
from app.core.config import get_settings
from app.db.models import (
    Document,
    DocumentProcessingJob,
    DocumentStatus,
    User,
)
from app.db.session import get_db_session
from app.documents.analysis import hash_report_manifest
from app.documents.queue import retry_document_job
from app.documents.schemas import AnalysisReport, DocumentSummary, UploadAccepted
from app.documents.storage import ObjectStorage, S3ObjectStorage
from app.documents.validation import UploadValidationError, validate_pdf_upload

document_router = APIRouter(
    prefix="/documents",
    tags=["private document analyzer"],
    dependencies=[Depends(verify_csrf_protection)],
)


def get_object_storage() -> ObjectStorage:
    return S3ObjectStorage()


def _summary(
    document: Document, job_override: DocumentProcessingJob | None = None
) -> DocumentSummary:
    job = job_override or document.__dict__.get("processing_job")
    return DocumentSummary(
        id=document.id,
        original_filename=document.original_filename,
        media_type=document.media_type,
        size_bytes=document.size_bytes,
        status=document.status.value,
        malware_scan_state=document.malware_scan_state,
        page_count=document.page_count,
        document_type=document.document_type,
        classification_confidence=document.classification_confidence,
        needs_ocr=document.needs_ocr,
        job_status=job.status if job else None,
        attempts=job.attempts if job else 0,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


async def _owned_document(
    session: AsyncSession, document_id: uuid.UUID, owner_id: uuid.UUID
) -> Document:
    result = await session.execute(
        select(Document)
        .options(selectinload(Document.processing_job), selectinload(Document.analysis_report))
        .where(
            Document.id == document_id,
            Document.owner_id == owner_id,
            Document.deleted_at.is_(None),
        )
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return document


async def _read_limited(file: UploadFile, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(min(64 * 1024, limit + 1 - total)):
        total += len(chunk)
        if total > limit:
            raise UploadValidationError("file_too_large", "The PDF exceeds the upload size limit.")
        chunks.append(chunk)
    return b"".join(chunks)


@document_router.post(
    "",
    response_model=UploadAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Privately upload a PDF for asynchronous review",
)
async def upload_document(
    response: Response,
    file: UploadFile = File(...),
    current_user: User = Depends(require_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
    storage: ObjectStorage = Depends(get_object_storage),
) -> UploadAccepted:
    settings = get_settings()
    try:
        data = await _read_limited(file, settings.document_max_upload_bytes)
        validated = await asyncio.to_thread(
            validate_pdf_upload,
            data,
            file.filename or "",
            file.content_type,
            settings.document_max_upload_bytes,
        )
    except UploadValidationError as exc:
        await record_audit_event(
            session,
            action="document.validation_failed",
            resource_type="document_upload",
            actor_id=current_user.id,
            details={"failure_code": exc.code},
        )
        await session.commit()
        raise HTTPException(
            status_code=422, detail={"code": exc.code, "message": str(exc)}
        ) from exc
    existing = await session.scalar(
        select(Document)
        .options(selectinload(Document.processing_job))
        .where(
            Document.owner_id == current_user.id,
            Document.content_hash == validated.sha256,
            Document.deleted_at.is_(None),
        )
    )
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return UploadAccepted(
            document=_summary(existing),
            duplicate=True,
            detail="This file was already uploaded to your account; the existing job was retained.",
        )

    document_id = uuid.uuid4()
    object_key = f"{current_user.id}/{document_id}/{secrets.token_hex(16)}.pdf"
    document = Document(
        id=document_id,
        owner_id=current_user.id,
        storage_key=object_key,
        original_filename=validated.safe_filename,
        media_type="application/pdf",
        size_bytes=validated.size_bytes,
        content_hash=validated.sha256,
        status=DocumentStatus.VALIDATED,
        page_count=validated.page_count,
        malware_scan_state="not_configured",
    )
    job = DocumentProcessingJob(
        id=uuid.uuid4(),
        document_id=document_id,
        status="queued",
        attempts=0,
        available_at=datetime.now(UTC),
    )
    document.processing_job = job
    session.add(document)
    stored_object = False
    try:
        await session.flush()
        await run_in_threadpool(storage.put, object_key, data, "application/pdf")
        stored_object = True
        await record_audit_event(
            session,
            action="document.uploaded",
            resource_type="document",
            resource_id=document_id,
            actor_id=current_user.id,
            details={"size_bytes": validated.size_bytes, "page_count": validated.page_count},
        )
        await record_audit_event(
            session,
            action="document.validated",
            resource_type="document",
            resource_id=document_id,
            actor_id=current_user.id,
            details={"validation": "pdf_structure", "page_count": validated.page_count},
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if stored_object:
            try:
                await run_in_threadpool(storage.delete, object_key)
            except Exception:
                pass
        duplicate = await session.scalar(
            select(Document)
            .options(selectinload(Document.processing_job))
            .where(
                Document.owner_id == current_user.id,
                Document.content_hash == validated.sha256,
                Document.deleted_at.is_(None),
            )
        )
        if duplicate is not None:
            response.status_code = status.HTTP_200_OK
            return UploadAccepted(
                document=_summary(duplicate),
                duplicate=True,
                detail=(
                    "This file was already uploaded to your account; the existing job was retained."
                ),
            )
        raise HTTPException(
            status_code=503, detail="Private document storage is unavailable."
        ) from exc
    except Exception as exc:
        await session.rollback()
        if stored_object:
            try:
                await run_in_threadpool(storage.delete, object_key)
            except Exception:
                pass
        raise HTTPException(
            status_code=503, detail="Private document storage is unavailable."
        ) from exc
    await session.refresh(document)
    await session.refresh(job)
    return UploadAccepted(
        document=_summary(document, job),
        duplicate=False,
        detail=("Upload accepted. Malware scanning and processing will continue asynchronously."),
    )


@document_router.get(
    "", response_model=list[DocumentSummary], summary="List your private documents"
)
async def list_documents(
    current_user: User = Depends(require_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[DocumentSummary]:
    result = await session.execute(
        select(Document)
        .options(selectinload(Document.processing_job))
        .where(Document.owner_id == current_user.id, Document.deleted_at.is_(None))
        .order_by(Document.created_at.desc(), Document.id)
    )
    return [_summary(document) for document in result.scalars().all()]


@document_router.get(
    "/{document_id}", response_model=DocumentSummary, summary="View your document status"
)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(require_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentSummary:
    return _summary(await _owned_document(session, document_id, current_user.id))


@document_router.get(
    "/{document_id}/report", response_model=AnalysisReport, summary="View your analysis report"
)
async def get_document_report(
    document_id: uuid.UUID,
    current_user: User = Depends(require_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisReport:
    document = await _owned_document(session, document_id, current_user.id)
    report = document.analysis_report
    if report is None:
        raise HTTPException(status_code=409, detail="The report is not available yet.")
    manifest = cast(dict[str, Any], report.manifest)
    if not hmac.compare_digest(hash_report_manifest(manifest), report.manifest_sha256):
        raise HTTPException(status_code=500, detail="Report integrity validation failed.")
    extraction = cast(dict[str, Any], manifest["extraction"])
    return AnalysisReport.model_validate(
        {
            **manifest,
            "id": report.id,
            "document_id": report.document_id,
            "report_version": report.report_version,
            "extraction_quality": extraction["quality"],
            "page_count": extraction["page_count"],
            "needs_ocr": extraction["needs_ocr"],
            "manifest_sha256": report.manifest_sha256,
        }
    )


@document_router.get("/{document_id}/download", summary="Download your private original PDF")
async def download_document(
    document_id: uuid.UUID,
    current_user: User = Depends(require_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
    storage: ObjectStorage = Depends(get_object_storage),
) -> Response:
    document = await _owned_document(session, document_id, current_user.id)
    if document.status in {DocumentStatus.DELETED, DocumentStatus.FAILED}:
        raise HTTPException(status_code=409, detail="This document is not available for download.")
    try:
        data = await run_in_threadpool(storage.get, document.storage_key)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="Private document storage is unavailable."
        ) from exc
    await record_audit_event(
        session,
        action="document.downloaded",
        resource_type="document",
        resource_id=document.id,
        actor_id=current_user.id,
        details={"size_bytes": document.size_bytes},
    )
    await session.commit()
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{document.original_filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@document_router.post(
    "/{document_id}/retry", response_model=DocumentSummary, summary="Retry a blocked document job"
)
async def retry_processing(
    document_id: uuid.UUID,
    current_user: User = Depends(require_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentSummary:
    document = await _owned_document(session, document_id, current_user.id)
    if not await retry_document_job(session, document):
        raise HTTPException(status_code=409, detail="This processing job cannot be retried now.")
    await record_audit_event(
        session,
        action="document.processing_retried",
        resource_type="document",
        resource_id=document.id,
        actor_id=current_user.id,
        details={"attempt": document.processing_job.attempts if document.processing_job else 0},
    )
    await session.commit()
    return _summary(document)


@document_router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete your document and report",
)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(require_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
    storage: ObjectStorage = Depends(get_object_storage),
) -> Response:
    document = await _owned_document(session, document_id, current_user.id)
    try:
        await run_in_threadpool(storage.delete, document.storage_key)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="Private document storage is unavailable."
        ) from exc
    await record_audit_event(
        session,
        action="document.deleted",
        resource_type="document",
        resource_id=document.id,
        actor_id=current_user.id,
        details={"size_bytes": document.size_bytes},
    )
    await session.delete(document)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
