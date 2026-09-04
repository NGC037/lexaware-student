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
