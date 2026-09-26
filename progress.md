# LexAware Student — Project Progress

> Living project state and cross-chat handoff document.

---

## 1. Project Identity

**Project:** LexAware Student

**Product Promise:**

> Know your rights. Understand your documents. Take the right next step.

**Current Environment:** Local development

**Primary Jurisdiction:** India

**Current Phase:** Phase 0 — Discovery and Governance

**Current Increment:** Repository Foundation

**Status:** In progress

---

## 2. Product Boundary

LexAware Student is an AI-assisted legal-awareness and next-step
guidance platform for students.

It does not provide:

- Formal legal representation
- Binding legal opinions
- Automated legal filing
- Court case management
- Lawyer-client communication
- Guaranteed legal outcomes

---

## 3. Architecture

### Frontend

React + TypeScript + Vite

### Backend

Python + FastAPI

### Database

PostgreSQL + pgvector

### Background Processing

Redis + worker architecture

### Object Storage

S3-compatible private object storage

### AI

RAG-based architecture with:

- Approved knowledge
- Hybrid retrieval
- Embeddings
- LLM provider adapter
- Citation validation
- Safety routing

### Blockchain

Hyperledger Fabric for selective provenance anchoring.

Blockchain must never become the operational source of truth.

---

## 4. Repository

Repository root:

`C:\Users\Neha\Projects\lexaware-student`

Git branch:

`main`

Git initialized:

- [x] Git repository initialized
- [x] Main branch configured
- [x] First commit

---

## 5. Development Environment

- [x] Git
- [x] Node.js
- [x] npm
- [x] Python
- [x] Docker
- [x] Docker Compose
- [x] VS Code

---

## 6. Current Work

### Completed

- [x] Development environment inspected
- [x] Project location selected
- [x] Project directory created
- [x] Git repository initialized
- [x] Main branch created

### In Progress

| `7bd6d73 ` | Repository baseline | Complete |

- [ ] `.gitignore`
- [ ] `.env.example`
- [ ] `README.md`
- [ ] Repository structure
- [ ] Initial Git commit

### Next

- Frontend project initialization
- Backend project initialization
- Local infrastructure
- Database foundation
- CI foundation

---

## 7. Repository Structure

```text
lexaware-student/
├── apps/
│   ├── web/
│   └── api/
├── workers/
├── blockchain/
├── packages/
│   ├── contracts/
│   ├── prompts/
│   ├── rag/
│   └── evaluation/
├── content/
│   ├── sources/
│   └── seed/
├── migrations/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── security/
│   ├── e2e/
│   └── ai-evaluation/
├── docs/
│   ├── architecture/
│   ├── adr/
│   ├── runbooks/
│   └── product/
└── infra/
```

### Phase 1 — Technical Foundation

#### Local Infrastructure Checkpoint — Completed

The initial local development infrastructure has been established and verified.

Completed:

- Docker Compose local infrastructure configured.
- PostgreSQL 16 with pgvector configured.
- PostgreSQL connectivity verified with `pg_isready`.
- pgvector extension enabled and verified (`0.8.6`).
- Redis 7 configured and verified with `PONG`.
- MinIO configured with persistent local storage.
- MinIO health check verified.
- Automated MinIO initialization service added.
- Private document bucket `lexaware-documents-private` created automatically.
- Bucket access explicitly configured as private.
- Local `.env` created from `.env.example`.
- `.env` confirmed excluded from Git.
- Docker Compose configuration validated successfully.
- All infrastructure containers verified healthy.

Current local infrastructure:

| Service                 | Port | Status  |
| ----------------------- | ---: | ------- |
| PostgreSQL + pgvector   | 5434 | Healthy |
| Redis                   | 6379 | Healthy |
| MinIO API               | 9000 | Healthy |
| MinIO Console           | 9001 | Healthy |
| Private document bucket |    — | Created |

Verification performed:

- `pg_isready` → accepting connections
- Redis `PING` → `PONG`
- pgvector extension → `0.8.6`
- MinIO health check → healthy
- MinIO private bucket → verified

#### Backend Foundation - Completed

- Resolved local PostgreSQL authentication failure caused by the host PostgreSQL 18 service occupying port 5432; the project now uses local port 5434.
- Recreated only the PostgreSQL development volume and verified asyncpg authentication.
- SQLAlchemy async engine, pooled sessions, request-scoped session dependency, and shutdown disposal are configured.
- Redis async client, health check, and graceful shutdown are configured.
- Alembic is wired to async PostgreSQL and the application metadata.
- pgvector migration `19bffc3ace56` applied successfully; extension version `0.8.6` verified.
- Added `/api/v1/ready` with safe dependency status and HTTP 503 when unavailable.
- Added readiness, PostgreSQL, Redis, Alembic, and pgvector tests.
- Validation: 6 tests passed; Ruff check and formatting checks passed; health and readiness returned HTTP 200.

#### Domain Model Foundation - Completed

- Added UUID-based persistence models for users, roles, user-role assignments, jurisdictions, source metadata, knowledge items and versions, private documents, document access grants, audit events, help resources, and complaints.
- Added timezone-aware lifecycle timestamps, ownership foreign keys, object-level document access boundaries, publication/review states, soft lifecycle states, indexes, unique constraints, and database checks for document size and positive knowledge versions.
- Persisted enum values as stable lowercase strings for API and migration compatibility.
- Added migration `f2168b35f764_establish_core_domain_persistence_models`, reviewed and applied after the pgvector migration.
- Added ADR 0003 documenting the initial domain slice, privacy boundaries, and assumptions made because the detailed industrial product specification is not present in this checkout.
- Added integration tests for model creation, relationships, ownership, constraints, PostgreSQL, Redis, Alembic, and pgvector.
- Validation: 8 tests passed; mypy passed; Ruff check and formatting checks passed; `alembic check` reported no drift; Alembic current is `f2168b35f764`.

#### Authentication & Authorization Foundation - Hardened & Completed

- Established secure identity and authorization infrastructure for student accounts and multi-role operations (student, admin, reviewer, publisher).
- Added `user_credentials` table (1-to-1 with `users`) storing normalized email addresses and Argon2id password hashes (`argon2-cffi`).
- Relaxed `User.external_subject` constraint to allow `NULL` values for local password accounts while preserving OAuth/SSO compatibility (ADR 0004).
- Removed redundant ordinary index on `user_credentials.email` via migration `8cba291f6859`, maintaining clean PostgreSQL unique constraint indexing.
- Implemented opaque server-side session tokens in Redis (`auth:session:{token_hash}`), deriving security from cryptographic randomness with instant revocation support on logout and account suspension.
- Minimized Redis session payload to only `user_id`, `created_at`, and `expires_at`. Role evaluation is performed live from PostgreSQL on every request to prevent stale privileges.
- Removed all transient session fields from the `User` ORM entity, managing active request metadata strictly via `request.state`.
- Enforced NIST SP 800-63B compliant password policy: 12-character minimum, 128-character maximum, rejecting common/weak passwords without arbitrary composition rules.
- Implemented anti-enumeration defenses:
  - Registration returns uniform HTTP 201 acknowledgment without leaking whether an email is already registered.
  - Login failures for non-existent emails, invalid passwords, and inactive/suspended accounts return identical generic HTTP 401 `"Invalid email or password"` responses, backed by constant-time dummy Argon2id verification.
- Corrected rate-limiting semantics: failure quota is consumed only upon failed credential attempts, successful login resets failure quota, and Redis keys store SHA-256 hashed account identifiers to prevent PII leakage. Layered quotas protect shared campus Wi-Fi/hostel IPs.
- Implemented robust Double-Submit CSRF protection (`lexaware_csrf` cookie + `X-CSRF-Token` header) and Origin/Referer verification for cookie-authenticated mutations, while exempting Bearer token API clients.
- Configured browser session cookie (`lexaware_session`) with `HttpOnly`, `SameSite=Lax`, and `Secure` (production environment) flags.
- Enforced server-side role-based authorization via reusable FastAPI dependencies (`get_current_user`, `require_authenticated_user`, `require_role`).
- Added structured audit logging (`audit_events`) for registration, login success, login failure, and logout without leaking credentials or secrets.
- Migrations: `7927febec3bb` (user credentials) and `8cba291f6859` (redundant index cleanup).
- Validation: 23 tests passed (unit + integration); mypy passed in strict mode; Ruff check and formatting checks passed; `alembic check` reported zero drift; Alembic current is `8cba291f6859 (head)`.

### Phase 2 — Knowledge System

#### Chunk 2.1 — Governed Knowledge Domain - Completed

- Implemented industrial-grade governed knowledge domain foundation satisfying Product Specification v1.0 requirements FR-05, FR-06, FR-07, FR-08, FR-26, and FR-27.
- Expanded database models in `apps/api/app/db/models.py`:
  - `KnowledgeItem`: category (indexed), topic, audience, and composite index `(jurisdiction_id, category, status)`.
  - `KnowledgeVersion`: title, summary, applicability_notes, escalation_guidance, temporal windows (`effective_from`, `effective_until`), review tracking (`reviewed_by_id`, `reviewed_at`, `review_due_at`), publication tracking (`published_by_id`, `published_at`), and `change_summary`. Added composite indexes `(effective_from, effective_until)`, `(knowledge_item_id, publication_state)`, and `(review_due_at)`.
- Applied and verified Alembic migration `45bd284b1395` (`expand_knowledge_governance_schema`).
- Implemented robust Pydantic schemas in `apps/api/app/knowledge/schemas.py` for item creation/detail, version drafting, review decisions, review schedules, and student read models.
- Implemented core domain service in `apps/api/app/knowledge/service.py`:
  - `validate_publication_invariants`: Mandatory gatekeeper enforcing non-empty title, content >= 20 chars, plain-language summary, applicability notes, escalation guidance, active source, and completed formal review before publication.
  - Immutability enforcement: Direct content edits strictly restricted to versions in `DRAFT` state; revisions to published content enforce creating new sequential versions.
  - Automatic version superseding: Publishing a new approved version automatically transitions any existing published version to `SUPERSEDED`.
  - Content review queue (FR-27): `list_stale_reviews` finds published versions where `review_due_at < now()`.
  - Student read safety boundary: Hard database filters strictly enforcing `status == ACTIVE`, `state == PUBLISHED`, and `effective_from <= now <= effective_until`. Non-published content (drafts, in-review, approved, superseded, archived) is completely invisible.
  - Structured audit trail: Emits `AuditEvent` records for all lifecycle transitions without duplicating raw article bodies.
- Implemented API routers in `apps/api/app/knowledge/router.py` and mounted in `apps/api/app/api/router.py`:
  - Public Student Router (`/api/v1/knowledge`): `/articles`, `/articles/{slug}`, `/categories`, `/jurisdictions`.
  - Governance Admin Router (`/api/v1/admin/knowledge`): Role-protected endpoints for jurisdictions, sources, items, versions, review submissions, review decisions, publication, archiving/unpublishing, freshness review scheduling, and stale review queues.
- Added comprehensive integration test suite `apps/api/tests/integration/test_knowledge.py` covering all lifecycle states, invariant enforcement, unauthorized role attempts, search, category counting, automatic superseding, and stale review scheduling.
- Documented in ADR 0005 (`docs/adr/0005-governed-knowledge-domain.md`).
- Validation: 28 tests passed across full test suite; mypy passed in strict mode; Ruff check and formatting checks passed with 0 errors; `alembic check` reported zero drift; Alembic current is `45bd284b1395 (head)`.

#### Chunk 2.2 â€” Student Knowledge Search - Implemented

- Extended `GET /api/v1/knowledge/articles` with PostgreSQL full-text search and typed category, jurisdiction, audience, limit, and offset parameters. Empty or whitespace-only `q` follows browse behavior.
- Added `KnowledgeVersion.tags` and `keywords` JSONB arrays, nullable `synonyms`, and a maintained `search_vector`. Migration `a31c7e2f9d10` backfills existing rows, installs an update trigger, and creates a GIN index.
- Search covers title, summary, content, tags, keywords, and synonyms with `plainto_tsquery` and `ts_rank_cd`; structured item/category/topic matching remains separate. Results retain the student-safe active, published, effective-date SQL boundary and have stable secondary ordering.
- Student list output includes source citation metadata, review date, applicability notes, and escalation guidance, without internal governance IDs/state.
- Added integration cases for field matching, ranking, filters, hidden drafts, malformed input, empty queries, pagination, metadata, and private governance-field exclusion.
- Validation: PostgreSQL and Redis integration services were verified healthy. Migration `a31c7e2f9d10` upgraded successfully; Alembic current is `a31c7e2f9d10 (head)`, and `alembic check` passed with no schema drift. Pytest: 28 passed, 0 failed, 0 errors. Ruff check, Ruff format check, `mypy app`, compileall, and `git diff --check` passed. Authentication regression, knowledge governance, and FTS/search tests passed. No application, security, visibility, or pagination blocking issues were found.

### Phase 2.3 — Complaint Guidance + Help Directory

- Implemented FR-22 through FR-25 with governed, versioned complaint guides and a source-backed help directory. Complaint guide content uses typed, deterministically ordered safety/reporting/checklist steps and does not collect or persist incident narratives.
- Added migration `bc0d4f8a21e6_add_complaint_guides_and_verified_help.py` to add complaint guide/version tables and help-resource classification, source provenance, verification, and expiry fields. Existing help resources remain conservatively unverified and are hidden until verified against a current source in the same jurisdiction.
- Added public APIs `GET /api/v1/complaints/guides`, `GET /api/v1/complaints/guides/{slug}`, and `GET /api/v1/help`, with category/jurisdiction/audience or assistance-type filters and bounded pagination where applicable.
- Added role-protected administration APIs for guide draft/version, submit/review/publish/unpublish/archive lifecycle and help-resource create/update/verify/retire lifecycle. Student reads exclude drafts, review-only, unpublished, archived, future/expired, stale-review, unverified, inactive, or cross-jurisdiction-source content. Mutations emit structured audit events without guide prose or incident narratives.
- Safety behavior: guidance is static, editor-authored, available without AI, and places immediate safety first with escalation guidance last. The product does not provide legal representation, filing, guaranteed outcomes, binding opinions, or legal/illegal verdicts.
- Documented architecture, visibility rules, verification, role gates, auditing, APIs, and limitations in ADR 0006 (`docs/adr/0006-complaint-guidance-help-directory.md`).
- Validation: PostgreSQL and Redis Compose services healthy; migration `bc0d4f8a21e6` upgraded successfully; Alembic current `bc0d4f8a21e6 (head)`; Alembic check reported no drift. Pytest: 30 passed, 0 failed, 0 errors, including authentication, knowledge governance/search, and complaint/help integration tests. Ruff check passed with historical migration import-order `I001` ignored; Ruff format check passed; strict `mypy app`, compileall, and `git diff --check` passed. Ruff full check without that exception reports the pre-existing import-order warning in the unchanged Phase 2.2 migration `a31c7e2f9d10_add_knowledge_full_text_search.py`.
# Phase 4.1 — AI legal assistant foundation

Status: implementation and validation complete.

- Added authenticated `POST /api/v1/assistant/messages` with typed request, structured response, stable error envelope, and correlation ID.
- Added deterministic first-pass safety classification, provider gate, fail-closed default provider, versioned safety/grounding prompt, and a deterministic mock provider for tests.
- Added governed PostgreSQL full-text knowledge retrieval, citation/currentness validation, metadata-only audit traceability, and verified-current emergency resource lookup. No incident narrative is persisted.
- Tightened student knowledge queries to omit explicitly overdue reviews and inactive or temporally invalid sources; content without a scheduled review date retains existing publication behavior. Internal eligibility fields remain excluded from public JSON.
- No provider credentials/vendor, pgvector/RAG adapter, complaint intake, or schema migration was added.
- Validation against healthy PostgreSQL and Redis Compose services: Alembic current `bc0d4f8a21e6 (head)`, Alembic check reports no schema drift, and pytest reports 51 passed, 0 failed, 0 errors. Changed-file Ruff check and format check passed; `mypy app`, compileall, and `git diff --check` passed. Repository-wide Ruff check reports only I001 in the unchanged Phase 2.2 FTS migration.
- Next: Phase 4.2 — separately review and implement retrieval augmentation/provider integration.

# Phase 4.2 — Hybrid retrieval + RAG foundation

Status: implementation and validation complete.

- Added migration `d4c2a9420f31` with a 384-dimensional pgvector chunk table, governance/version metadata, metadata indexes, and an HNSW cosine index. PostgreSQL 16 uses the existing `pgvector/pgvector:pg16` Compose service and preexisting `vector` extension.
- Added deterministic section-aware chunking (`section-window-v1`), a vendor-neutral batch embedding protocol, a stable test-only hash fake, finite/count/dimension validation, and an explicit eligibility-gated, idempotent indexing service. Chunks link to governed versions; all visibility metadata comes from live canonical rows, and changed versions are excluded until reindexed.
- Added internal `hybrid-fts-vector-v1` retrieval using existing PostgreSQL FTS plus pgvector cosine search, the shared student knowledge eligibility boundary, explicit jurisdiction isolation, bounded candidate/top-k limits, deterministic weighted ranking, duplicate merging, and passage/provenance metadata. No public vector endpoint or external embedding/Gemini call was added.
- Updated assistant orchestration to use hybrid retrieval, retain emergency/high-risk bypasses, and distinguish no results, jurisdiction clarification, and retrieval failure. Retrieval failure is fail-closed; empty grounding does not invoke the generation provider. Audit/response traces include the retrieval config version/state without internal chunk IDs or user query text.
- Tests cover stable/overlapping chunks, provider determinism and dimension validation, real PostgreSQL vector-only retrieval and idempotent reindexing, stale governance exclusion, FTS retrieval, assistant provenance retention, instruction-like source text isolation, safety routing, and retrieval failures.
- Validation: PostgreSQL 16/pgvector and Redis Compose services verified healthy; migration upgrade passed; Alembic current is `d4c2a9420f31 (head)`; Alembic check reports no schema drift. Pytest: 58 passed, 0 failed, 0 errors, including authentication, knowledge governance/search, FTS/vector, assistant safety, prompt-injection boundary, and retrieval failure cases. Ruff passes for all Phase 4.2 changed files; repository-wide Ruff reports only the preexisting I001 in unchanged `a31c7e2f9d10_add_knowledge_full_text_search.py`. Ruff format check passed (71 files); `mypy app`, compileall, and `git diff --check` passed.
- Review: both retrieval paths use the shared live student eligibility boundary; stale, unpublished, inactive, overdue, future, expired, archived, and cross-jurisdiction content is excluded. Query handling uses bound parameters and escaped LIKE patterns; missing jurisdiction and retrieval failures fail closed. No student data is embedded or persisted, and retrieved passages remain untrusted prompt data. No implementation/security blocker found.
- Limitations/next step: the configured hash embedding is test-only and is not semantically useful in production. A production embedding model has not been selected, and retrieval quality has not been evaluated against a representative evaluation set. Phase 4.2 establishes the retrieval engine and contract, not production relevance. Select a production model/provider, coordinate its dimension and retrieval config, then evaluate retrieval before rollout. Real Gemini generation remains a separate phase.

### Phase 4.3 — Production Embeddings & AI Generation

Status: implementation and deterministic validation complete; production embeddings and live Gemini validation are deferred because Gemini returned HTTP 429.

- Selected Google's Gemini Embedding 001 (`gemini-embedding-001`) at 768 dimensions for governed-knowledge retrieval. Reduced-dimension vectors are normalized, query/document task types are distinct, and provider/model/dimension are configured through environment settings. Student-private documents are not embedded.
- Added migration `c195dd7e5955` to clear derived 384-dimensional test/index vectors, alter the pgvector column, dimension constraint and HNSW cosine index to 768. Eligible published knowledge requires re-indexing; full-text retrieval remains available during rebuild.
- Added Gemini embedding and structured generation adapters behind existing provider protocols. Providers default disabled, require `GEMINI_API_KEY` only when enabled, use timeouts and typed safe failure classes, and do not log prompts, secrets, or vendor error bodies.
- Added versioned prompt v2 with distinct application rules, schema, retrieved source context, and user question sections. Citation/currentness/jurisdiction validation and deterministic high-risk bypass remain application-controlled. Output checks reject common definitive, guaranteed, and evidence-concealment patterns; they do not claim semantic entailment.
- Added deterministic retrieval evaluation case definitions and Recall@k/Precision@k/source retrieval/stale rejection/jurisdiction rejection/empty-result metric helpers, plus deterministic generation route scenarios. No retrieval-quality percentages are claimed; run evaluations against an adjudicated governed corpus before launch.
- Added ADR 0009 documenting the model choice, migration/re-index requirement, provider architecture, trace metadata, evaluation approach, smoke test, and limitations.
- The previously pasted key is not in repository files or Git history. The replacement key is configured only in ignored local `.env`; `.env.example` contains an empty key setting. A repository scan found no provider-key patterns in the working tree, diff, or history.
- Re-indexing called the existing eligibility-gated, idempotent indexing service only. After the integration suite, 352 versions satisfy the student knowledge eligibility boundary; 59 have current `gemini-embedding-001` 768-dimensional indexes and 293 remain missing. No vector has a wrong dimension. Gemini returned HTTP 429 during embedding; indexing stopped without fabricating vectors or changing provider metadata. No further provider calls were made afterward. Live assistant generation and end-to-end Gemini retrieval smoke tests therefore remain incomplete.
- Validation: PostgreSQL/pgvector 16 and Redis Compose services are available. Migration `c195dd7e5955` is current at head; `alembic check` reports no schema drift. Pytest: 64 passed, 0 failed, 0 errors, including PostgreSQL/Redis integration, authentication/governance regressions, Gemini/embedding mocks, and retrieval/assistant tests. Repository-wide Ruff check and format check, strict `mypy app`, compileall, and `git diff --check` passed. The secret scan found no findings.
- Checkpoint: commit 2f65a21 (feat: establish production grounded ai assistant) was pushed to origin/main; the repository was clean and synchronized before Phase 5 began.
- PHASE 4.3 DEFERRED PROVIDER VALIDATION: resume idempotent indexing when Gemini quota permits; index the remaining 293 eligible versions; verify all vectors are 768-dimensional; run retrieval, live Gemini generation, and end-to-end grounded assistant smoke tests; complete provider validation. Do not fabricate retrieval-quality metrics.

### Phase 5 ? Document Analyzer Foundation

Status: backend foundation implemented; not a complete or release-ready analyzer.

- Extended the existing Document model with lifecycle, extraction quality, OCR need, classification, and malware scan state. Added a unique processing job per document and a private analysis report with a canonical SHA-256 manifest. Migrations e82fb314a6c1 and b71d2459c30a are applied.
- Added authenticated PDF upload/list/status/report/download/retry/delete endpoints under /api/v1/documents. Every query is owner-scoped; other users and administrators without ownership receive 404. Cookie-authenticated mutations require the existing CSRF protection. Storage keys are random identifiers, and responses never contain S3 internals or signed URLs.
- Upload validation checks bounded request and file sizes, PDF extension/MIME/signature, parser validity, page limits, encryption, active-content markers, and filenames. Duplicate uploads by the same owner and content hash reuse the existing job. Filenames are normalized and never used in object keys.
- Added a boto3 S3-compatible adapter using the existing private MinIO bucket. A live local put/get/delete smoke check passed; anonymous reads returned 403. .env.example now matches the Compose MinIO defaults. No public bucket policy or presigned URLs are used.
- Added a PostgreSQL job table with SKIP LOCKED claims, a ten-minute recovery lease, bounded attempts/backoff, idempotent report creation, and a standalone worker (python -m app.workers.document_worker). PostgreSQL is used because the repository had no existing task queue; Redis remains used for sessions and is not given a parallel job role.
- PDF text extraction uses pypdf, preserves page boundaries in memory, caps pages/text, and records page count, character count, low-text warnings, and OCR need. Extracted full text is not persisted. Image-only/low-text documents receive an unsupported/needs-OCR report; OCR is not claimed.
- Classification is deterministic for internship agreements, employment bonds, offer letters, hostel agreements, and rental agreements. Low-confidence, ambiguous, and unknown documents are not forced into a supported type. Keyword findings carry bounded page excerpts, uncertainty, limitations, and next steps; they are review signals and do not declare legality.
- Reports contain the informational-review disclaimer, type/classification confidence, extraction quality, evidence, limitations, next steps, and review recommendation. Canonical JSON uses sorted keys, compact separators, and UTF-8 before SHA-256; report reads verify the stored manifest hash. No blockchain integration or document-content provider calls were added.
- Deletion removes the private object before deleting document/job/report rows; metadata-only audit events remain. Audit records avoid filenames, excerpts, and document text. A malware scanner is not available in the repository: the worker defaults to scanner_not_configured, blocks extraction, and never marks a document clean. An actual malware scanner must be integrated before processing real student files.
- Tests cover owner/admin/cross-user IDOR boundaries, report/download/delete authorization, CSRF, MIME/signature/size/malformed/encrypted/active-content PDFs, filename normalization, OCR uncertainty, supported/unknown/ambiguous classification, bounded evidence, report-hash verification, safe scanner-blocked state, retry/lease recovery, duplicate processing, metadata-only audit, and real MinIO private access.
- Validation: pytest 84 passed, 0 failed, 0 errors; Ruff, format, strict mypy, compileall, Alembic check, and git diff --check passed. Alembic current is b71d2459c30a (head). PostgreSQL, Redis, and MinIO were exercised.
- Known limits / next increment: no malware-scanning implementation, OCR, text-bearing end-to-end PDF fixture, export, retention scheduler, or worker Compose service. The safe default prevents document analysis until a real malware scanner is configured. Phase 5 exit criteria are not yet complete.

### Phase 5.1 — ClamAV hardening + text-PDF end-to-end processing

Status: implementation and validation complete; Phase 5.1 remains uncommitted and unpushed.

- Integrated ClamAV 1.4.6 through clamd's `INSTREAM` protocol. The client sends the bounded uploaded bytes in fixed-size chunks, uses a configured finite socket timeout, caps scanner response handling, and discards raw daemon diagnostics. Only explicit clean/infected verdicts are accepted.
- Added ClamAV and a standalone document-worker service to the development Compose network. ClamAV is not published on public interfaces; the host integration-test port is bound to loopback. Its signature database uses a named volume. The worker waits for PostgreSQL, MinIO initialization, and ClamAV health.
- Worker behavior remains fail-closed: clean allows extraction; infected blocks the job, skips analysis, and removes the object; unavailable blocks for explicit retry; scanner error is recorded and retried under the existing bounded retry policy. No scanner result other than clean enters extraction.
- Added a deterministic, synthetic one-page internship-agreement PDF fixture with no personal data. End-to-end test covers authenticated upload to MinIO, real ClamAV scan, pypdf text extraction, classification, findings/page evidence, report/disclaimer/hash verification, cross-user denial, and object plus database deletion.
- Bounded extraction work with an explicit configured timeout in addition to upload/page/character limits. Parsing runs in a child process that is terminated if the timeout expires.
- Added clamd protocol verdict-mapping tests and worker tests for infected, unavailable, and error outcomes. Existing owner/IDOR, malformed/encrypted/oversized PDF, retry, audit privacy, and manifest tamper tests remain in the suite.
- Validation: real ClamAV 1.4.6 (signature database 28129) clean-scanned the synthetic PDF and detected the harmless EICAR test string. The worker image built, Compose configuration validated, and worker-container scanner connectivity returned clean. Full pytest: 94 passed, 0 failed, 0 errors, with PostgreSQL, Redis, MinIO, and ClamAV. Ruff check and format check passed; `mypy app` passed (64 source files); compileall passed; Alembic current is `b71d2459c30a (head)` and `alembic check` found no drift; `git diff --check` passed.
- Security validation: owner and cross-user status/report/download/retry/delete checks passed; infected and unavailable/error scanner states did not extract or create reports; malware and audit tests passed. No application changes were made to Phase 4.3 or Gemini. OCR, retention scheduling, frontend UI, and Gemini document analysis remain out of scope. Production scanner resource limits, monitoring, and signature-update operations still require deployment-specific hardening.

### Frontend foundation — Initial public experience

Status: initial public experience and backend-integrated registration/session/onboarding slice implemented.

- Added `apps/web`, a React 19 + TypeScript + Vite app with strict type checking, ESLint, Vitest/Testing Library, Playwright, and production build scripts.
- Added a responsive public landing page and shared shell, original shield/book brand mark and CSS illustration, accessible mobile navigation, skip link, not-found state, and system/light/dark theme preferences with persistence and pre-render theme bootstrap.
- Added semantic light and dark design tokens, responsive layouts, visible keyboard focus, reduced-motion and forced-color support, accessibility guidance, and third-party attribution documentation.
- Added `/register`, `/login`, `/onboarding`, and guarded `/app` routes using actual backend request/response contracts. Session state comes from `/api/v1/auth/me`; login establishes the cookie session and then re-fetches `/me`; logout obtains a CSRF token and posts the required header before clearing frontend state. Passwords and session tokens are not stored in browser storage.
- Backend onboarding persistence is not available. The intro collects no personal data; completion uses a user-keyed `sessionStorage` marker for this tab only and is explicitly described as non-authoritative. The `/app` shell shows only real `/me` identity and an empty state. No password recovery or email verification is claimed.
- Backend contract reviewed in `apps/api/app/auth`: `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/me`, `/auth/csrf`; opaque Redis session, HttpOnly `lexaware_session`, readable double-submit CSRF cookie/header, Argon2id password hashing, 12–128 character schema policy plus common-password rejection, credentialed exact-origin CORS, and role list in `/me`. Registration intentionally returns a generic duplicate-safe 201 acknowledgment. Backend implementation was not changed.
- Specs reviewed: `UI UX Specification.md` and `Industry-Specifications-Lexaware.md`. Frontend validation: typecheck, lint, production build passed; Vitest: 21 passed, 0 failed; `npm audit`: 0 vulnerabilities; `git diff --check` passed. Backend auth unit tests: 5 passed; integration tests: 10 passed against PostgreSQL and isolated temporary Redis. Real Edge + Vite + FastAPI browser flow passed registration, login, `/me`, onboarding, refresh, logout, protected-route denial, public landing, and login again; the generated test account was removed afterward. This does not constitute full product release validation.

### Authenticated student dashboard — Completed

- Replaced the placeholder `/app` welcome with a responsive student workspace and compact floating horizontal navigation; no permanent sidebar or fabricated activity is shown.
- Integrated `GET /api/v1/knowledge/articles` using the existing published/current visibility boundary and student audience filter, plus `GET /api/v1/help?limit=3` for current verified contact previews. Search text stays in memory only; external source links are restricted to HTTP(S), and support contacts are shown with their source.
- Recent activity, saved items, and announcements have no backend endpoints. They are presented as unavailable/empty, without frontend-only persistence or sample content. Assistant, document, and complaint destinations remain non-interactive “Coming soon” items because those frontend routes do not exist.
- The hero visual is a semantic layered SVG with CSS perspective and pointer-bounded rotation; there is no WebGL, canvas, third-party 3D dependency, or continuous render loop. Reduced motion disables entrance/rotation effects. The dashboard uses the existing semantic light/dark tokens, compact mobile header, and stacked mobile action/support layout.
- Added loading, success, empty, error, retry, cancellation, responsive, navigation, theme, and HTTP(S)-source handling to the dashboard, with mocked unit coverage for API states.
- Validation: Vitest 28 passed, 0 failed; ESLint passed; strict TypeScript typecheck passed; production build passed (308.62 kB JS, 96.38 kB gzip; 35.18 kB CSS, 7.66 kB gzip). Edge + Vite + FastAPI + PostgreSQL + Redis E2E passed (1 test): current-user dashboard, real help/search API responses, refresh/logout/protected redirect, 375px mobile no-overflow, light/dark preference, reduced-motion CSS, and simulated support API failure without backend-detail leakage. API readiness confirmed PostgreSQL and Redis available. Five synthetic browser-test accounts and their three outstanding Redis sessions were removed. No backend code or dependencies were changed.
- Limitations: Help Directory, assistant, document, and complaint screens remain future slices. A backend-specific emergency contact taxonomy/route was not found; the dashboard displays only governed verified contacts and does not invent emergency numbers. Activity, saved items, and announcements remain unavailable because no corresponding backend endpoints exist.

### F5 - Rights Explorer

Status: implementation and validation complete; no commit or push performed.

- Added the authenticated /app/rights knowledge library and /app/rights/:slug article detail route under the existing student session guard. The compact workspace navigation and dashboard action now link to the Explorer; prior dashboard behavior remains intact.
- Uses only existing governed endpoints: GET /api/v1/knowledge/articles for student browse/search/category/jurisdiction filters and offset pagination; GET /api/v1/knowledge/categories; GET /api/v1/knowledge/jurisdictions; and GET /api/v1/knowledge/articles/{slug} for currently available article details. No backend changes or new API routes.
- Search is submitted explicitly, trimmed, limited to the backend's 200-character maximum, held in component memory only, and not sent for each keystroke. Category and jurisdiction choices come from backend responses. Empty query browses current student-visible articles; no synthetic counts or article content are shown.
- Results and details render governed content without rewriting it. Source links allow only HTTP(S), include citations/publishers and available retrieved/effective/review dates, and detail content is escaped plain text. Unavailable article 404s and service errors have separate safe states. Loading, empty, error/retry, and load-more behavior are accessible; list pagination uses the backend's bounded 12-item pages.
- Added responsive editorial styling from existing light/dark design tokens, compact filter controls, visible keyboard focus, reduced-motion handling, and no permanent sidebar.
- Frontend validation: Vitest 37 passed across 8 files; ESLint passed; strict TypeScript typecheck passed; production build passed; git diff --check passed.
- Browser validation: real Edge + Vite + FastAPI + PostgreSQL + Redis E2E passed (1 test). Verified authenticated navigation, real article/category/jurisdiction responses, real search and filters, detail/source/retrieved metadata, empty search, simulated 503 handling without backend exception leakage, refresh, 375px no-overflow, dark theme with primary and secondary text contrast >= 4.5:1, reduced-motion CSS, and no unhandled page or console errors. PostgreSQL and Redis Compose services were healthy. Synthetic E2E accounts and related Redis sessions were cleaned up. No backend files or dependencies changed.
- Limitations: availability and status labels are limited to fields exposed by the student response schemas; publication/current visibility is enforced by the backend routes. The article API has no total-count field, so the UI does not show an aggregate total. Source/detail text is displayed as plain text because the response schema provides strings rather than structured rich text.

### F6 — Complaint Guidance + Help Directory

Status: implementation and validation complete; no commit or push performed.

- Added authenticated `/app/complaints`, `/app/complaints/:slug`, and `/app/help` routes using the existing session-protected workspace layout and compact navigation. Dashboard actions now link to complaint guidance and the full help directory; dashboard structure and F1–F5 pages remain intact.
- Complaint guidance uses `GET /api/v1/complaints/guides` with the backend-supported student audience, category, jurisdiction, limit, and offset fields, and `GET /api/v1/complaints/guides/{slug}` for details. It displays only returned published guide fields and structured steps. Current-unavailable 404, empty, loading, retry, and generic service-error states are handled.
- Help uses `GET /api/v1/help` with the supported category, jurisdiction, assistance-type, limit, and offset fields. The page displays only student schema fields for active verified resources, their contacts, jurisdiction, source, verification, and retrieval metadata. Contact and source website links are restricted to HTTP(S); phone and email actions use supplied backend values.
- No guide-to-resource relationship is exposed by the student schemas, so the experiences remain separate. No emergency classifications or resource associations are fabricated. Backend implementation was not changed.
- Frontend validation: Vitest 47 passed across 10 files; ESLint passed; strict TypeScript typecheck passed; production build passed; `git diff --check` passed.
- Real Edge + Vite + FastAPI + PostgreSQL + Redis validation passed using temporary student accounts that were deleted afterward; matching Redis sessions were revoked and no test accounts remain. Verified current help and complaint results (50 help resources and 7 guides in the first responses), supported category/jurisdiction/assistance-type filters, complaint detail and refresh, HTTP(S)-only external help links, simulated 503 states with generic messages and successful retries, real API no-match states, 375px layout without horizontal overflow, dark theme, reduced-motion preference, keyboard-visible focus, login/logout, and zero unhandled page errors.
- Known limitations / deferred work: category, jurisdiction, and assistance-type filters are exact-value text fields because the APIs do not provide discovery endpoints for these filter options. The student response does not expose help-resource expiry/review-due values or a guide-to-help relationship, so neither is inferred or shown. The app displays at most 50 results per request and loads further results only on user request; it has no total-count endpoint. No administrative authoring or complaint filing is included.
