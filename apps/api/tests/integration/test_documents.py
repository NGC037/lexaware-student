from __future__ import annotations

import socketserver
import struct
import threading
from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import UUID, uuid4

import httpx
import pytest
from pypdf import PdfWriter
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.auth.service import hash_password
from app.auth.tokens import create_session
from app.core.config import get_settings
from app.db.models import (
    AuditEvent,
    Document,
    DocumentAnalysisReport,
    DocumentProcessingJob,
    DocumentStatus,
    Role,
    User,
    UserCredential,
    UserRole,
)
from app.db.session import AsyncSessionLocal
from app.documents.analysis import hash_report_manifest
from app.documents.queue import claim_next_document_job, run_document_job
from app.documents.router import get_object_storage
from app.documents.scanner import ClamAVScanner
from app.documents.storage import S3ObjectStorage
from app.main import app


class MemoryStorage:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, data: bytes, content_type: str) -> None:
        assert content_type == "application/pdf"
        self.objects[key] = data

    def get(self, key: str) -> bytes:
        return self.objects[key]

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


class CleanTestScanner:
    def scan(self, data: bytes) -> str:
        assert data.startswith(b"%PDF-")
        return "clean"


class ErrorTestScanner:
    def scan(self, data: bytes) -> str:
        return "error"


class InfectedTestScanner:
    def scan(self, data: bytes) -> str:
        return "infected"


def blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


def synthetic_internship_pdf() -> bytes:
    """Build a fixed, harmless one-page PDF fixture with extractable contract text."""
    content = (
        b"BT /F1 12 Tf 72 720 Td (INTERNSHIP AGREEMENT) Tj "
        b"0 -24 Td (This internship agreement describes stipend and training period.) Tj "
        b"0 -24 Td (A service bond applies during the training period.) Tj "
        b"0 -24 Td (The monthly stipend may be withheld under stated conditions.) Tj ET"
    )
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n%fixed-fixture\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(
        (
            f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
        ).encode()
    )
    return bytes(pdf)


def scanner_server(verdict: bytes):
    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            command = bytearray()
            while not command.endswith(b"\0"):
                command.extend(self.request.recv(1))
            assert command == b"zINSTREAM\0"
            while True:
                length = struct.unpack(">I", self._read_exact(4))[0]
                if length == 0:
                    break
                self._read_exact(length)
            self.request.sendall(verdict + b"\0")

        def _read_exact(self, count: int) -> bytes:
            result = bytearray()
            while len(result) < count:
                result.extend(self.request.recv(count - len(result)))
            return bytes(result)

    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    server.verdict = verdict
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


async def make_user(role_name: str = "student") -> tuple[UUID, str]:
    suffix = uuid4().hex
    async with AsyncSessionLocal() as session:
        role = await session.scalar(select(Role).where(Role.name == role_name))
        if role is None:
            role = Role(name=role_name, description=role_name.title())
            session.add(role)
            await session.flush()
        user = User(display_name="Document test")
        session.add(user)
        await session.flush()
        session.add(
            UserCredential(
                user_id=user.id,
                email=f"document-{suffix}@example.test",
                password_hash=hash_password("SecurePassword123!"),
            )
        )
        session.add(UserRole(user_id=user.id, role_id=role.id))
        await session.commit()
        user_id = user.id
    token, _ = await create_session(str(user_id))
    return user_id, token


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def memory_storage():
    storage = MemoryStorage()
    app.dependency_overrides[get_object_storage] = lambda: storage
    yield storage
    app.dependency_overrides.pop(get_object_storage, None)


@pytest.mark.asyncio
async def test_upload_duplicate_owner_report_download_and_delete_are_private(
    async_client: httpx.AsyncClient, memory_storage: MemoryStorage
):
    owner_id, owner_token = await make_user()
    _other_id, other_token = await make_user("admin")
    content = blank_pdf()
    unauthenticated = await async_client.get(f"/api/v1/documents/{uuid4()}")
    assert unauthenticated.status_code == 401
    cookie_only = await async_client.post(
        "/api/v1/documents",
        cookies={"lexaware_session": owner_token},
        files={"file": ("offer.pdf", content, "application/pdf")},
    )
    assert cookie_only.status_code == 403

    uploaded = await async_client.post(
        "/api/v1/documents",
        headers=bearer(owner_token),
        files={"file": ("../../offer.pdf", content, "application/pdf")},
    )
    assert uploaded.status_code == 202
    body = uploaded.json()
    document_id = body["document"]["id"]
    assert body["document"]["original_filename"] == "offer.pdf"
    assert "storage_key" not in str(body)
    assert len(memory_storage.objects) == 1
    object_key = next(iter(memory_storage.objects))
    assert object_key.startswith(f"{owner_id}/{document_id}/")
    assert "offer" not in object_key

    async with AsyncSessionLocal() as session:
        source = await session.get(Document, UUID(document_id))
        assert source is not None
        session.add(
            Document(
                id=uuid4(),
                owner_id=owner_id,
                storage_key=f"{owner_id}/duplicate-race/{uuid4().hex}.pdf",
                original_filename="copy.pdf",
                media_type="application/pdf",
                size_bytes=source.size_bytes,
                content_hash=source.content_hash,
                status=DocumentStatus.VALIDATED,
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()

    replay = await async_client.post(
        "/api/v1/documents",
        headers=bearer(owner_token),
        files={"file": ("different.pdf", content, "application/pdf")},
    )
    assert replay.status_code == 200
    assert replay.json()["duplicate"] is True
    assert replay.json()["document"]["id"] == document_id
    assert len(memory_storage.objects) == 1

    async with AsyncSessionLocal() as session:
        job_id = await session.scalar(
            select(DocumentProcessingJob.id).where(
                DocumentProcessingJob.document_id == UUID(document_id)
            )
        )
        assert job_id is not None
        assert await claim_next_document_job(session, job_id) == job_id
        state = await run_document_job(
            session, job_id, storage=memory_storage, scanner=CleanTestScanner()
        )
        assert state == "completed"
        assert (
            await run_document_job(
                session, job_id, storage=memory_storage, scanner=CleanTestScanner()
            )
            == "completed"
        )
        reports = await session.scalars(
            select(DocumentAnalysisReport).where(
                DocumentAnalysisReport.document_id == UUID(document_id)
            )
        )
        assert len(list(reports.all())) == 1

    other_headers = bearer(other_token)
    for path, method in (
        (f"/api/v1/documents/{document_id}", "get"),
        (f"/api/v1/documents/{document_id}/report", "get"),
        (f"/api/v1/documents/{document_id}/download", "get"),
        (f"/api/v1/documents/{document_id}", "delete"),
    ):
        response = await getattr(async_client, method)(path, headers=other_headers)
        assert response.status_code == 404
    assert len(memory_storage.objects) == 1

    owner_report = await async_client.get(
        f"/api/v1/documents/{document_id}/report", headers=bearer(owner_token)
    )
    assert owner_report.status_code == 200
    assert owner_report.json()["needs_ocr"] is True
    assert "OCR is not implemented" in " ".join(owner_report.json()["limitations"])
    assert owner_report.json()["manifest_sha256"]
    async with AsyncSessionLocal() as session:
        report = await session.scalar(
            select(DocumentAnalysisReport).where(
                DocumentAnalysisReport.document_id == UUID(document_id)
            )
        )
        assert report is not None
        changed = dict(report.manifest)
        changed["integrity_test"] = "tampered"
        await session.execute(
            update(DocumentAnalysisReport)
            .where(DocumentAnalysisReport.id == report.id)
            .values(manifest=changed)
        )
        await session.commit()
    tampered_report = await async_client.get(
        f"/api/v1/documents/{document_id}/report", headers=bearer(owner_token)
    )
    assert tampered_report.status_code == 500

    downloaded = await async_client.get(
        f"/api/v1/documents/{document_id}/download", headers=bearer(owner_token)
    )
    assert downloaded.status_code == 200
    assert downloaded.content == content
    assert downloaded.headers["x-content-type-options"] == "nosniff"

    deleted = await async_client.delete(
        f"/api/v1/documents/{document_id}", headers=bearer(owner_token)
    )
    assert deleted.status_code == 204
    assert not memory_storage.objects
    assert (
        await async_client.get(f"/api/v1/documents/{document_id}", headers=bearer(owner_token))
    ).status_code == 404
    async with AsyncSessionLocal() as session:
        assert (
            await session.scalar(select(Document.id).where(Document.id == UUID(document_id)))
            is None
        )
        actions = set(
            (
                await session.scalars(
                    select(AuditEvent.action).where(AuditEvent.resource_id == UUID(document_id))
                )
            ).all()
        )
        assert {
            "document.uploaded",
            "document.validated",
            "document.processing_started",
            "document.report_generated",
            "document.downloaded",
            "document.deleted",
        } <= actions
        events = (
            await session.scalars(
                select(AuditEvent).where(AuditEvent.resource_id == UUID(document_id))
            )
        ).all()
        assert all("offer" not in str(event.details).lower() for event in events)


@pytest.mark.asyncio
async def test_text_pdf_full_worker_flow_with_clamav_and_minio(
    async_client: httpx.AsyncClient, monkeypatch
):
    settings = get_settings()
    monkeypatch.setattr(settings, "clamav_host", "127.0.0.1")
    monkeypatch.setattr(settings, "clamav_port", 3310)
    storage = S3ObjectStorage()
    app.dependency_overrides[get_object_storage] = lambda: storage
    _owner_id, owner_token = await make_user()
    _other_id, other_token = await make_user()
    content = synthetic_internship_pdf()
    assert content == synthetic_internship_pdf()

    try:
        uploaded = await async_client.post(
            "/api/v1/documents",
            headers=bearer(owner_token),
            files={"file": ("synthetic-internship.pdf", content, "application/pdf")},
        )
        assert uploaded.status_code == 202
        document_id = UUID(uploaded.json()["document"]["id"])
        # Storage keys are intentionally not returned by the API; read them from the DB.
        async with AsyncSessionLocal() as session:
            document = await session.get(Document, document_id)
            assert document is not None
            object_key = document.storage_key
            job_id = await session.scalar(
                select(DocumentProcessingJob.id).where(
                    DocumentProcessingJob.document_id == document_id
                )
            )
            assert job_id is not None
            assert await claim_next_document_job(session, job_id) == job_id
            assert (
                await run_document_job(session, job_id, storage=storage, scanner=ClamAVScanner())
                == "completed"
            )
            await session.refresh(document)
            assert document.status == DocumentStatus.COMPLETED
            assert document.malware_scan_state == "clean"

        report_response = await async_client.get(
            f"/api/v1/documents/{document_id}/report", headers=bearer(owner_token)
        )
        assert report_response.status_code == 200
        report = report_response.json()
        assert report["document_type"] == "internship_agreement"
        assert report["extraction_quality"] in {"medium", "high"}
        assert report["findings"]
        assert report["findings"][0]["evidence"]["page_number"] == 1
        assert report["limitations"] and report["next_steps"]
        assert "not a binding legal opinion" in report["disclaimer"].lower()
        async with AsyncSessionLocal() as session:
            stored_report = await session.scalar(
                select(DocumentAnalysisReport).where(
                    DocumentAnalysisReport.document_id == document_id
                )
            )
            assert stored_report is not None
            assert stored_report.manifest_sha256 == hash_report_manifest(stored_report.manifest)
            assert report["manifest_sha256"] == stored_report.manifest_sha256

        owner_status = await async_client.get(
            f"/api/v1/documents/{document_id}", headers=bearer(owner_token)
        )
        assert owner_status.status_code == 200
        assert owner_status.json()["status"] == "completed"

        for suffix in ("", "/report", "/download", "/retry"):
            response = (
                await async_client.get(
                    f"/api/v1/documents/{document_id}{suffix}", headers=bearer(other_token)
                )
                if suffix != "/retry"
                else await async_client.post(
                    f"/api/v1/documents/{document_id}/retry", headers=bearer(other_token)
                )
            )
            assert response.status_code == 404
        denied_delete = await async_client.delete(
            f"/api/v1/documents/{document_id}", headers=bearer(other_token)
        )
        assert denied_delete.status_code == 404
        assert storage.get(object_key) == content

        deleted = await async_client.delete(
            f"/api/v1/documents/{document_id}", headers=bearer(owner_token)
        )
        assert deleted.status_code == 204
        from botocore.exceptions import ClientError

        with pytest.raises(ClientError):
            storage.get(object_key)
        assert (
            await async_client.get(
                f"/api/v1/documents/{document_id}/report", headers=bearer(owner_token)
            )
        ).status_code == 404
        async with AsyncSessionLocal() as session:
            assert await session.get(Document, document_id) is None
            assert (
                await session.scalar(
                    select(DocumentAnalysisReport.id).where(
                        DocumentAnalysisReport.document_id == document_id
                    )
                )
                is None
            )
            assert (
                await session.scalar(
                    select(DocumentProcessingJob.id).where(
                        DocumentProcessingJob.document_id == document_id
                    )
                )
                is None
            )
    finally:
        app.dependency_overrides.pop(get_object_storage, None)


def test_real_clamav_detects_harmless_eicar_signature_without_persisting_it(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "clamav_host", "127.0.0.1")
    monkeypatch.setattr(settings, "clamav_port", 3310)
    eicar_test_string = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    assert ClamAVScanner().scan(eicar_test_string) == "infected"


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        (b"stream: OK", "clean"),
        (b"unexpected: OK", "error"),
        (b"stream: Eicar-Test-Signature FOUND", "infected"),
        (b"stream: scanner failure ERROR", "error"),
    ],
)
def test_clamav_scanner_streams_content_and_maps_only_known_verdicts(
    reply: bytes, expected: str, monkeypatch
):
    server = scanner_server(reply)
    settings = get_settings()
    monkeypatch.setattr(settings, "clamav_host", "127.0.0.1")
    monkeypatch.setattr(settings, "clamav_port", server.server_address[1])
    try:
        assert ClamAVScanner().scan(b"synthetic safe fixture bytes") == expected
    finally:
        server.shutdown()
        server.server_close()


def test_clamav_scanner_unavailable_is_not_clean(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "clamav_host", "127.0.0.1")
    monkeypatch.setattr(settings, "clamav_port", 1)
    assert ClamAVScanner().scan(b"%PDF-1.4") == "unavailable"


@pytest.mark.asyncio
async def test_infected_file_is_deleted_and_never_analyzed(
    async_client: httpx.AsyncClient, memory_storage: MemoryStorage
):
    _owner_id, token = await make_user()
    uploaded = await async_client.post(
        "/api/v1/documents",
        headers=bearer(token),
        files={"file": ("synthetic.pdf", synthetic_internship_pdf(), "application/pdf")},
    )
    document_id = UUID(uploaded.json()["document"]["id"])
    async with AsyncSessionLocal() as session:
        job_id = await session.scalar(
            select(DocumentProcessingJob.id).where(DocumentProcessingJob.document_id == document_id)
        )
        assert job_id is not None
        assert await claim_next_document_job(session, job_id) == job_id
        assert (
            await run_document_job(
                session, job_id, storage=memory_storage, scanner=InfectedTestScanner()
            )
            == "failed"
        )
        document = await session.get(Document, document_id)
        assert document is not None
        assert document.malware_scan_state == "infected"
        assert document.status == DocumentStatus.FAILED
        assert not memory_storage.objects
        assert (
            await session.scalar(
                select(DocumentAnalysisReport.id).where(
                    DocumentAnalysisReport.document_id == document_id
                )
            )
            is None
        )


@pytest.mark.asyncio
async def test_scanner_error_retries_without_extraction(
    async_client: httpx.AsyncClient, memory_storage: MemoryStorage
):
    _owner_id, token = await make_user()
    uploaded = await async_client.post(
        "/api/v1/documents",
        headers=bearer(token),
        files={"file": ("synthetic.pdf", synthetic_internship_pdf(), "application/pdf")},
    )
    document_id = UUID(uploaded.json()["document"]["id"])
    async with AsyncSessionLocal() as session:
        job_id = await session.scalar(
            select(DocumentProcessingJob.id).where(DocumentProcessingJob.document_id == document_id)
        )
        assert job_id is not None
        assert await claim_next_document_job(session, job_id) == job_id
        assert (
            await run_document_job(
                session, job_id, storage=memory_storage, scanner=ErrorTestScanner()
            )
            == "queued"
        )
        document = await session.get(Document, document_id)
        assert document is not None
        assert document.malware_scan_state == "error"
        assert (
            await session.scalar(
                select(DocumentAnalysisReport.id).where(
                    DocumentAnalysisReport.document_id == document_id
                )
            )
            is None
        )


@pytest.mark.asyncio
async def test_scanner_unavailable_blocks_processing_and_owner_can_retry(
    async_client: httpx.AsyncClient, memory_storage: MemoryStorage
):
    _owner_id, token = await make_user()
    upload = await async_client.post(
        "/api/v1/documents",
        headers=bearer(token),
        files={"file": ("blank.pdf", blank_pdf(), "application/pdf")},
    )
    document_id = UUID(upload.json()["document"]["id"])
    async with AsyncSessionLocal() as session:
        job = await session.scalar(
            select(DocumentProcessingJob).where(DocumentProcessingJob.document_id == document_id)
        )
        assert job is not None
        job.status = "processing"
        job.attempts = 1
        job.claimed_at = datetime.now(UTC) - timedelta(minutes=11)
        document = await session.get(Document, document_id)
        assert document is not None
        document.status = DocumentStatus.PROCESSING
        await session.commit()
        job_id = job.id
        assert await claim_next_document_job(session, job_id) == job_id
        assert await run_document_job(session, job_id, storage=memory_storage) == "blocked"
        doc = await session.get(Document, document_id)
        assert doc is not None
        assert doc.malware_scan_state == "unavailable"
        assert doc.status.value == "validated"
        assert (
            await session.scalar(
                select(DocumentAnalysisReport.id).where(
                    DocumentAnalysisReport.document_id == document_id
                )
            )
            is None
        )

    retry = await async_client.post(f"/api/v1/documents/{document_id}/retry", headers=bearer(token))
    assert retry.status_code == 200
    async with AsyncSessionLocal() as session:
        job_id = await session.scalar(
            select(DocumentProcessingJob.id).where(DocumentProcessingJob.document_id == document_id)
        )
        assert job_id is not None
        assert await claim_next_document_job(session, job_id) == job_id
        assert (
            await run_document_job(
                session, job_id, storage=memory_storage, scanner=CleanTestScanner()
            )
            == "completed"
        )
        job = await session.scalar(
            select(DocumentProcessingJob).where(DocumentProcessingJob.document_id == document_id)
        )
        assert job is not None and job.attempts == 3 and job.status == "completed"


@pytest.mark.asyncio
async def test_invalid_uploads_are_rejected_and_audited_without_filename_or_content(
    async_client: httpx.AsyncClient, memory_storage: MemoryStorage, monkeypatch
):
    owner_id, token = await make_user()
    wrong_type = await async_client.post(
        "/api/v1/documents",
        headers=bearer(token),
        files={"file": ("unsafe.pdf", blank_pdf(), "text/plain")},
    )
    assert wrong_type.status_code == 422
    assert wrong_type.json()["detail"]["code"] == "unsupported_media_type"
    bad_magic = await async_client.post(
        "/api/v1/documents",
        headers=bearer(token),
        files={"file": ("unsafe.pdf", b"not pdf", "application/pdf")},
    )
    assert bad_magic.status_code == 422
    settings = get_settings()
    monkeypatch.setattr(settings, "document_max_upload_bytes", len(blank_pdf()) - 1)
    oversized = await async_client.post(
        "/api/v1/documents",
        headers=bearer(token),
        files={"file": ("oversized.pdf", blank_pdf(), "application/pdf")},
    )
    assert oversized.status_code == 422
    assert oversized.json()["detail"]["code"] == "file_too_large"
    assert not memory_storage.objects
    async with AsyncSessionLocal() as session:
        events = (
            await session.scalars(
                select(AuditEvent).where(
                    AuditEvent.actor_id == owner_id,
                    AuditEvent.action == "document.validation_failed",
                )
            )
        ).all()
        assert len(events) == 3
        assert all(set(event.details or {}) == {"failure_code"} for event in events)


@pytest.mark.asyncio
async def test_real_minio_private_object_round_trip_and_anonymous_denial():
    import asyncio
    from urllib.error import HTTPError
    from urllib.request import urlopen

    from app.documents.storage import S3ObjectStorage

    settings = get_settings()
    storage = S3ObjectStorage()
    key = f"integration-smoke/{uuid4().hex}.pdf"
    payload = b"%PDF-1.7\\nprivate storage integration"
    await asyncio.to_thread(storage.put, key, payload, "application/pdf")
    try:
        assert await asyncio.to_thread(storage.get, key) == payload
        try:
            response = await asyncio.to_thread(
                urlopen,
                f"{settings.s3_endpoint.rstrip('/')}/{settings.s3_bucket}/{key}",
                None,
                5,
            )
            status_code = response.status
            response.close()
        except HTTPError as error:
            status_code = error.code
        assert status_code in {401, 403}
    finally:
        await asyncio.to_thread(storage.delete, key)


@pytest.mark.asyncio
async def test_processing_storage_failure_retries_idempotently(
    async_client: httpx.AsyncClient, memory_storage: MemoryStorage
):
    class BrokenStorage:
        def get(self, key: str) -> bytes:
            raise RuntimeError("private storage diagnostic")

        def delete(self, key: str) -> None:
            return None

        def put(self, key: str, data: bytes, content_type: str) -> None:
            return None

    _owner_id, token = await make_user()
    upload = await async_client.post(
        "/api/v1/documents",
        headers=bearer(token),
        files={"file": ("retry.pdf", blank_pdf(), "application/pdf")},
    )
    document_id = UUID(upload.json()["document"]["id"])
    async with AsyncSessionLocal() as session:
        job_id = await session.scalar(
            select(DocumentProcessingJob.id).where(DocumentProcessingJob.document_id == document_id)
        )
        assert job_id is not None
        assert await claim_next_document_job(session, job_id) == job_id
        assert await run_document_job(session, job_id, storage=BrokenStorage()) == "queued"
        job = await session.get(DocumentProcessingJob, job_id)
        assert job is not None
        assert job.failure_code == "processing_failed"
        assert "private storage diagnostic" not in (job.failure_code or "")
        job.available_at = datetime.now(UTC)
        await session.commit()
        assert await claim_next_document_job(session, job_id) == job_id
        assert (
            await run_document_job(
                session, job_id, storage=memory_storage, scanner=CleanTestScanner()
            )
            == "completed"
        )
        report = await session.scalar(
            select(DocumentAnalysisReport.id).where(
                DocumentAnalysisReport.document_id == document_id
            )
        )
        assert report is not None
