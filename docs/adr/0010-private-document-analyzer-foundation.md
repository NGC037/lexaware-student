# ADR 0010: Private document analyzer foundation

## Status

Accepted for the Phase 5 backend foundation and hardened in Phase 5.1. This is not a production release approval; deployment-specific scanner operations and security validation remain required.

## Context

The repository already had owner-linked Document metadata, a private MinIO bucket, PostgreSQL, Redis for authentication sessions, and metadata-only audit events. It had no document analyzer, PDF parser, malware scanner, or task queue. Student uploads are private and untrusted. The foundation must work without Gemini and must not send document content to external providers or blockchain.

## Decisions

- Extend the existing Document model and retain legacy status values. Add extraction/classification/scanner metadata, one idempotent processing job per document, and a private report manifest. Migration e82fb314a6c1 follows c195dd7e5955.
- Store original PDFs only in the existing private S3-compatible MinIO bucket. Object keys are generated from opaque identifiers, never filenames; server-side routes authorize by Document.owner_id. The adapter does not generate public or presigned URLs. Local Compose credentials and bucket defaults match the API example settings.
- Accept PDF only, with bounded request-body and file reads, MIME/extension/signature checks, strict pypdf structure validation, a page limit, and rejection of encrypted or detected active-content PDFs. Sanitize filenames as display metadata; do not use them in paths.
- Use a PostgreSQL job table because no existing worker queue was present. Claims use FOR UPDATE SKIP LOCKED, a ten-minute processing lease, retry backoff, and unique document/job/report constraints. A standalone worker runs with python -m app.workers.document_worker; it is not yet a Compose service. Redis remains reserved for existing session behavior.
- Provide a `MalwareScanner` interface and a ClamAV implementation using clamd's bounded `INSTREAM` protocol. It sends uploaded bytes over the private Compose network with finite socket timeouts, fixed-size chunks, and a bounded response. Only explicit `OK` or `FOUND` verdicts are accepted; daemon diagnostics are discarded. Unavailable results block processing, infected files are blocked and removed from storage, and scanner errors follow the bounded retry policy. No non-clean result can enter extraction.
- Extract per-page selectable text in memory with pypdf and bounded upload bytes, pages, characters, and an asynchronous timeout. Persist extraction metrics and warnings, not full extracted text. Pages with little or no text produce an explicit needs-OCR/unsupported report; OCR is not implemented.
- Classify deterministically using configured term sets for internship agreement, employment bond, offer letter, hostel agreement, and rental agreement. Ambiguous and unknown content remains unknown. Keyword findings use bounded excerpts and safe review language, with page and document-version references; they are not legal conclusions.
- Store a structured private report with extraction quality, supported type/confidence, evidence, uncertainty, limitations, next steps, and an informational-only disclaimer. Canonical manifest hashing uses UTF-8 JSON with lexicographically sorted keys and compact separators. Reads recompute and verify SHA-256 before returning the report.
- Hard-delete the MinIO object first, then cascade-delete document metadata, jobs, and reports; preserve only a metadata-only audit event. If object deletion fails, keep the database record and return an error. A database failure after object removal can leave an inaccessible metadata record, but cannot leave a downloadable object.
- Keep document content local: no Gemini calls, embeddings, or blockchain writes are part of this foundation. Prompt-like document text is never treated as application instructions because no model is invoked.

## Security and privacy boundaries

- All document, report, download, retry, and delete routes require an authenticated user and owner-scoped lookup. Administrators do not receive implicit access.
- Browser-cookie mutations use the existing CSRF dependency; bearer-token requests follow existing auth behavior.
- Audit details include lifecycle codes and bounded counts/hashes, not filenames, raw content, or excerpts.
- Original downloads are private attachments with Cache-Control: private, no-store and X-Content-Type-Options: nosniff.
- Active-content token checks are defense in depth, not malware detection. No document is described as malware-safe until an actual scanner reports clean.
- ClamAV's TCP protocol is unauthenticated; Compose keeps the daemon on the private application network and binds its test port only to host loopback. Do not publish that port in deployed environments. Signature updates occur on service startup, and health checks keep the worker from claiming jobs before the daemon is ready.

## Consequences and limitations

- Full text is transient during processing; report evidence excerpts are persisted because users need to trace findings.
- Heuristic extraction/classification/findings can be incomplete or overinclusive. Reports expose this uncertainty and recommend human review.
- OCR, exports, retention scheduling, and production scanner monitoring/update policy remain future work. Compose includes ClamAV and a document worker; production deployments still need operational health monitoring, resource limits, and a supported signature-update policy.
- PostgreSQL job polling is simple and transactionally integrated but needs production worker monitoring and operational limits before scale-up.
- Migration downgrade removes new tables/columns. PostgreSQL enum values added for lifecycle states remain because PostgreSQL cannot safely remove used enum labels.

## Validation

The integration suite covers owner isolation, administrator non-bypass, CSRF, upload validation, private MinIO access, scanner verdict mapping and fail-closed behavior, retries, idempotency, report integrity, audit metadata, deletion, and a text-bearing synthetic PDF scanned with ClamAV and processed end to end. Passing these tests does not satisfy Phase 5 release criteria without deployment-specific operational/security review.
