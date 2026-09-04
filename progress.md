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
- [ ] First commit

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

- [ ] Repository baseline
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
