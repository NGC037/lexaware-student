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
- Documented in ADR 0004.
- Validation: 23 tests passed (unit + integration); mypy passed in strict mode; Ruff check and formatting checks passed; `alembic check` reported zero drift; Alembic current is `8cba291f6859 (head)`.
