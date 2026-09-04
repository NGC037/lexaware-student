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
