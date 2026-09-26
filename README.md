# LexAware Student

LexAware Student is an AI-assisted legal-awareness and next-step guidance
platform designed for college students.

## Product Promise

> Know your rights. Understand your documents. Take the right next step.

## Important Boundary

LexAware Student is a legal-awareness and guided-support platform.

It is not:

- A law firm
- A legal representative
- A provider of binding legal opinions
- A court-filing service
- A lawyer marketplace
- A guarantee of legal outcomes

The system is designed to make uncertainty, jurisdiction, source freshness,
and escalation requirements visible to users.

## Technology

### Frontend

- React
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui
- TanStack Query

### Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic

### Data

- PostgreSQL
- pgvector
- Redis
- S3-compatible object storage

### AI

- Retrieval-Augmented Generation
- Approved knowledge sources
- Embeddings
- Primary LLM provider through an adapter
- Citation and safety validation

### Background Processing

- Redis
- Worker infrastructure
- Asynchronous document analysis
- RAG indexing
- Cleanup
- Notifications
- Provenance anchoring

### Blockchain

- Hyperledger Fabric
- Provenance and integrity anchors only

### Quality

- Unit testing
- Integration testing
- Security testing
- End-to-end testing
- AI evaluation
- Accessibility testing
- CI/CD

## Repository Structure

```text
apps/
  web/                 React frontend
  api/                 FastAPI backend

workers/               Background processing

blockchain/            Hyperledger Fabric integration

packages/
  contracts/           Shared API contracts
  prompts/              Versioned AI prompts and schemas
  rag/                 Retrieval and citation logic
  evaluation/          AI evaluation tooling

content/
  sources/             Reviewed source inventory
  seed/                Non-production seed data

migrations/            Database migration resources

tests/
  unit/
  integration/
  security/
  e2e/
  ai-evaluation/

docs/
  architecture/
  adr/
  runbooks/
  product/

infra/                 Infrastructure and deployment configuration
```


## Private Document Analyzer foundation

PDF endpoints are mounted at /api/v1/documents. Uploads are owner-private in MinIO. Start the development scanner and worker with `docker compose -f infra/docker/docker-compose.yml up -d --build clamav document-worker` after PostgreSQL and MinIO are healthy. ClamAV downloads signatures on first start; the worker waits until the scanner health check passes. The scanner port is bound to loopback for host-run integration tests and is not exposed on public interfaces.

The worker streams each size-bounded PDF to ClamAV. Only an explicit clean verdict permits extraction; unavailable, infected, and error states fail closed. Image-only pages return a needs-OCR/unsupported report; OCR and Gemini document analysis are not implemented. See ADR 0010 for the lifecycle, privacy, retry, and report-manifest design.
