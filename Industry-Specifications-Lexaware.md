LexAware Student
Industrial-Grade Product Specification, Software Requirements, and Incremental Delivery Plan
Version: 1.0
Status: Build-ready baseline specification
Primary audience: Product owners, students, supervisors, software engineers, testers, content reviewers, and future maintainers

Product promise: Know your rights. Understand your documents. Take the right next step.

1. Executive Summary
   LexAware Student is a web-based legal-awareness and guided-support platform for college students. It explains common legal and institutional situations in plain language, helps users inspect potentially important clauses in documents, provides structured next-step guidance, and directs users to verified support resources.

The product is intentionally not a law firm, legal representative, court-filing service, or source of binding legal opinions. Its central design principle is to provide useful, source-backed awareness while making uncertainty, jurisdiction, urgency, and escalation visible to the user.

The first release will deliver eight connected capabilities: secure student accounts, a Rights Explorer, a grounded AI Legal Assistant, a Legal Document Analyzer, a Complaint Guidance Wizard, a verified Help Directory, a private Document Vault, and an administrator content-governance console.

The platform will be designed for an initial Indian higher-education context, with jurisdiction and effective-date fields built into the data model so that future expansion does not require a fundamental redesign. Content must identify its jurisdiction, source authority, effective date, review date, and reviewer status.

2. Product Vision and Outcomes
   2.1 Vision
   LexAware Student will become a trusted first-stop awareness layer between a student’s problem and an appropriate human or institutional support channel. It will reduce confusion without creating false confidence.

2.2 Intended outcomes
Outcome How the product contributes Evidence of success
Better awareness Plain-language, source-backed explanations Students can identify relevant rights and next steps in usability tests
Safer decisions Clause highlighting, uncertainty labels, and escalation Users understand that a flagged clause requires review rather than being automatically unlawful
Faster routing Guided workflows and verified help resources Users reach a plausible authority or support resource with fewer dead ends
Better governance Versioned content, review dates, audit logs, and feedback Administrators can trace what was published, by whom, and when
Responsible AI use Retrieval, citations, validation, refusal, and escalation controls Responses meet grounding, safety, and citation evaluation thresholds
2.3 Product principles
1 Awareness before advice. The platform explains information and options; it does not present itself as the user’s lawyer.
2 Source before generation. AI output must be grounded in approved knowledge wherever a source-backed answer is expected.
3 Uncertainty must be visible. The product must distinguish known information, likely interpretation, missing facts, and professional-review requirements.
4 Safety over completion. A safe refusal or escalation is preferable to a confident but unsupported answer.
5 Privacy by design. Sensitive documents are private by default, minimized, encrypted where supported, and removable by the user.
6 Human governance. Legal content, help resources, high-risk prompts, and AI quality metrics require review processes.
7 Accessible language. Content should be understandable to a student without legal training.

3. Scope and Boundaries
   3.1 In scope for the MVP
   The MVP will support student registration and authentication, topic browsing and search, grounded legal-awareness questions, analysis of selected document types, structured complaint guidance, verified help-resource discovery, document and report history, feedback, and administrator governance.

The initial content domain will cover internship and employment, hostel and rental matters, ragging, cybercrime and online fraud, consumer rights, and harassment and safety. The initial legal context should be explicitly configured for India, with a state or local-area field where the workflow or resource depends on location.

3.2 Out of scope for the MVP
The MVP will not provide formal legal representation, binding legal opinions, automated legal filing, court case management, lawyer-client communication, paid consultations, payments, guaranteed legality determinations, government-system integration, a lawyer marketplace, or a native mobile application. These are future product options, not implied MVP commitments.

3.3 Safety boundary
The platform must not claim that a contract clause is “illegal,” that a user will win a dispute, or that a particular outcome is guaranteed. The preferred vocabulary is “potentially important,” “may require review,” “possible concern,” and “seek appropriate professional or institutional help.”

The system must route urgent safety matters, threats, ongoing violence, self-harm risk, sexual violence, child-safety concerns, or imminent loss of money or evidence toward emergency or specialist resources. It must not delay urgent help with a long AI conversation.

4. Personas and Key Journeys
   4.1 Student
   A student wants to understand a document, explore a rights topic, determine what to do after an incident, or find a trustworthy support channel. The student may be distressed, unfamiliar with legal terminology, using a mobile browser, or unsure which facts matter.

4.2 Administrator and content editor
An authorized staff member maintains articles, workflows, contacts, announcements, taxonomies, and publication status. The administrator needs validation, preview, version history, scheduled review, and auditability rather than direct database editing.

4.3 Content or legal reviewer
A future reviewer verifies source quality, jurisdiction, effective dates, plain-language accuracy, escalation language, and resource validity. This role should be distinct from a general administrator where staffing permits.

4.4 Core student journey
A student arrives at the dashboard, chooses Know Your Rights, Ask the Assistant, Analyze a Document, Get a Complaint Guide, or Find Help, receives an understandable result with limitations and sources, and is shown an actionable next step. The experience must allow the student to save or revisit the result without requiring repeated disclosure of sensitive facts.

5. Functional Requirements
   Requirement identifiers are stable references for design, implementation, and testing.

5.1 Identity and access
ID Requirement Acceptance condition
FR-01 The system shall support student registration with verified email or an approved institutional identifier. Duplicate and malformed identities are rejected; successful registration creates an inactive or verified account according to configuration.
FR-02 The system shall support login, logout, password reset, session expiry, and account deactivation. Expired or revoked sessions cannot access protected resources.
FR-03 The system shall enforce server-side role-based authorization. A student cannot access administrator endpoints, records, or files by changing a client request.
FR-04 The system shall record security-relevant events without storing unnecessary sensitive content. Login, logout, failed access, role changes, and administrative actions are auditable.
5.2 Knowledge and Rights Explorer
ID Requirement Acceptance condition
FR-05 Students shall browse topics by category, jurisdiction, and audience. Published and currently applicable content is discoverable; drafts remain private.
FR-06 Students shall search approved articles and FAQs. Search supports title, tags, keywords, and relevant synonyms and returns no unpublished content.
FR-07 Each article shall display sources, jurisdiction, last reviewed date, applicability notes, and escalation guidance. A user can identify the basis and freshness of the information.
FR-08 Administrators shall create, edit, preview, version, publish, unpublish, archive, and schedule review of content. Publication requires required metadata and an authorized action.
5.3 AI Legal Assistant
ID Requirement Acceptance condition
FR-09 The assistant shall validate input and classify intent, topic, jurisdiction, urgency, and risk. Test prompts are routed to answer, clarify, refuse, or escalate paths.
FR-10 The assistant shall retrieve relevant approved content before generating a source-backed response. The response stores the retrieval references used to produce it.
FR-11 The assistant shall present a plain-language explanation, assumptions, missing facts, possible next steps, sources, and a limitation notice. Required response sections are present for supported questions.
FR-12 The assistant shall refuse or escalate unsupported, high-risk, emergency, or clearly individualized legal-advice requests. The user receives an actionable safe route rather than fabricated certainty.
FR-13 Users shall be able to rate and report an answer. Feedback is associated with the response version and retrieval context.
5.4 Document Analyzer and Vault
ID Requirement Acceptance condition
FR-14 The system shall accept only configured file types and size limits and shall scan or validate uploads before processing. Invalid, oversized, corrupted, or unsupported files are rejected with a clear message.
FR-15 The system shall extract text with page references when technically possible and identify extraction confidence. A report identifies unreadable or image-only pages and does not silently treat missing text as absent clauses.
FR-16 The system shall classify supported document types and show an “unsupported or uncertain” result when confidence is low. Low-confidence classification triggers a review warning.
FR-17 The system shall identify configured clause categories and associate each finding with page or section evidence. A user can locate the source passage for a finding.
FR-18 The system shall label findings as informational, attention required, or urgent review, and shall explain that labels are not legality determinations. No report uses an unqualified “legal/illegal” verdict.
FR-19 The system shall generate a structured report containing summary, document type, findings, evidence, limitations, and next steps. The report is viewable and exportable in the configured format.
FR-20 Users shall view, rename, download, and delete their own documents and reports. Object-level authorization prevents cross-user access.
FR-21 The system shall support configurable retention and deletion behavior. Deletion removes the user-visible object and queues underlying storage cleanup according to policy.
5.5 Complaint Guidance and Help Directory
ID Requirement Acceptance condition
FR-22 The wizard shall collect only information necessary to choose a guidance path. Sensitive free text is optional unless needed for the workflow.
FR-23 The wizard shall provide immediate safety steps, evidence-preservation guidance, reporting options, required information, and a checklist. Each published guide has a reviewed sequence and escalation path.
FR-24 Help resources shall include type, jurisdiction or location, contact method, source, verification date, and status. Expired or unverified resources are not displayed as verified.
FR-25 Users shall filter resources by category, location, and assistance type. Results reflect the configured scope and verification status.
5.6 Administration, feedback, and operations
ID Requirement Acceptance condition
FR-26 Administrators shall manage users, categories, articles, guides, resources, announcements, and feedback. Every change is authorized and auditable.
FR-27 The system shall support content review queues and stale-content alerts. Administrators can identify items past their review date.
FR-28 The system shall provide operational metrics without exposing unnecessary personal content. Metrics include usage, failures, latency, feedback, and escalation rates in aggregate.
FR-29 The system shall handle unavailable AI, storage, search, and parsing services gracefully. The user receives a clear fallback or retry action and no partial success is presented as complete.

6. AI Safety and Knowledge Architecture
   6.1 Controlled response pipeline
   The assistant and analyzer shall follow this sequence:

User input
-> Input validation and sensitive-content handling
-> Intent, jurisdiction, urgency, and risk classification
-> Retrieval from approved, versioned knowledge
-> Context and source selection
-> Model generation using a constrained response schema
-> Citation and grounding validation
-> Safety, refusal, and escalation checks
-> Response with limitations and next steps
-> Feedback and quality monitoring

The model must not be the source of truth. It is a language-generation component operating over approved context and configured rules.

6.2 Knowledge records
Each source-backed content record should contain: title, content, category, jurisdiction, source authority, source URL or document reference, effective date, review date, reviewer, version, status, tags, applicability notes, and escalation notes. The system should preserve retired versions for audit purposes while preventing them from appearing in ordinary search.

6.3 Retrieval and citations
Retrieved passages must be traceable to the content version used at response time. The interface should expose concise source references and a “last reviewed” indicator. If retrieval confidence is below the configured threshold, the assistant should ask a clarifying question or provide a bounded limitation rather than inventing an answer.

The recommended retrieval-augmented generation (RAG) implementation is a hybrid retrieval pipeline. PostgreSQL full-text search should handle exact legal terms, names, and phrases, while pgvector should handle semantic similarity over approved knowledge chunks. A reranking step may be added after evaluation demonstrates that it improves citation accuracy. Every chunk must retain its article ID, version, jurisdiction, effective date, page or section reference, and source metadata. The generator must receive only retrieved content that passes status, jurisdiction, and freshness filters.

RAG is a retrieval and explanation mechanism, not a legal verification mechanism. A retrieved source may still be outdated, incomplete, or inapplicable to the user’s facts. Therefore, the application must validate source status and jurisdiction before generation and must display the source metadata with the answer.

6.4 Response contract
A supported response should contain the following sections:

8 What this may mean. A plain-language explanation.
9 What depends on the facts. Missing information and assumptions.
10 What to check or do next. Practical, non-guaranteed steps.
11 When to seek help urgently. Escalation conditions.
12 Sources and freshness. The relevant approved content.
13 Limitations. A concise legal-awareness disclaimer.

6.5 High-risk handling
The system should detect signals such as immediate danger, threats, violence, sexual abuse, self-harm, child safety, extortion, active financial fraud, imminent deadlines, requests to conceal evidence, and requests for a definitive legal verdict. These cases should use a short safety-first response, show relevant verified resources, and avoid asking unnecessary follow-up questions.

6.6 Document analysis safety
The analyzer is a review assistant, not a contract adjudicator. Findings must include the source page or text span, the reason the clause may deserve attention, and the limitation that enforceability depends on applicable law and facts. OCR or extraction uncertainty must be surfaced because a missing clause may result from unreadable content rather than actual absence.

6.7 Evaluation and monitoring
Before release, the team must maintain a test set of representative, ambiguous, adversarial, and high-risk prompts. Evaluation should measure groundedness, citation correctness, completeness, unsafe certainty, refusal quality, escalation recall, and latency. Production monitoring must sample responses for review without retaining more personal content than policy permits.

RAG evaluation should separately measure retrieval recall, retrieval precision, citation entailment, answer faithfulness, and stale-source rejection. The system should store the retrieval configuration, embedding-model version, prompt version, and knowledge-base version for each response so that an answer can be reproduced or investigated.

7. Document Analysis Design
   7.1 Supported first-release formats and types
   The first release should support text-based PDF files and a deliberately small set of document types: internship agreements, employment bonds, offer letters, hostel agreements, and rental agreements. Scanned PDFs, photographs, handwritten documents, password-protected files, and unsupported formats should be explicitly marked as unsupported or routed through a later OCR capability.

7.2 Processing states
A document should move through explicit states: uploaded, validated, queued, extracting, classified, analyzing, report_ready, needs_review, failed, deleted. State transitions should be idempotent so retries do not create duplicate reports.

7.3 Report structure
Each report should include document metadata, extraction quality, document classification and confidence, short summary, detected clause categories, evidence excerpts with page numbers, attention labels, explanation, missing-information warnings, suggested next steps, sources where applicable, processing timestamp, model or ruleset version, and disclaimer.

7.4 Retention and privacy defaults
Documents should be private by default. The system should not use user documents for model training unless a separate, explicit, revocable consent process is designed and approved. Temporary processing files should have shorter retention than user-saved documents. The product should provide a clear deletion action and explain what deletion means for backups and audit records.

8. System Architecture
   React + TypeScript Web Client
   |
   | HTTPS / versioned REST API
   v
   FastAPI Application Layer
   |-- Identity and authorization
   |-- Knowledge and search
   |-- Assistant orchestration
   |-- Document workflow
   |-- Complaint guidance
   |-- Help directory
   |-- Administration and audit
   |
   +--> PostgreSQL: users, content, metadata, reports, feedback, audit
   +--> pgvector: embeddings for approved RAG knowledge chunks
   +--> Object storage: private documents and generated exports
   +--> Queue/worker: extraction, analysis, notifications, cleanup
   +--> RAG service: chunking, embedding, hybrid retrieval, reranking, citations
   +--> AI provider adapter: one primary LLM and embedding provider behind abstractions
   +--> Blockchain anchor service: hashes and provenance proofs only
   +--> Monitoring and error reporting

The application should isolate provider-specific AI code behind adapters so that model replacement does not affect domain logic. The database should store references and metadata rather than large document binaries. Long-running analysis should execute asynchronously through a queue or worker, with progress visible to the student. Blockchain writes should also be asynchronous and must never block a student’s core request.

8.1 Recommended technology baseline
Layer Recommended technology Design reason
Frontend React, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query Typed, accessible, maintainable component-based client with predictable server-state handling
Backend Python, FastAPI, Pydantic, SQLAlchemy, Alembic Clear API contracts, validation, migrations, and a strong document-processing ecosystem
Primary database PostgreSQL 16+ Relational integrity, filtering, transactions, and audit-friendly records
Vector retrieval pgvector with PostgreSQL full-text search Keeps structured data, keyword search, embeddings, and metadata filters in one governed store for the MVP
RAG orchestration LangChain or LlamaIndex behind an internal RAG service Supports loaders, chunking, retrieval, prompt composition, and tracing without coupling the domain layer to a framework
Embeddings One approved embedding model through an adapter Stable semantic retrieval with a documented model version and re-indexing process
LLM One primary Gemini model through an AI provider adapter Limits provider complexity while allowing later replacement and controlled fallback
Authentication Argon2id password hashing, secure HTTP-only cookies or short-lived JWT access tokens, refresh/session controls Limits credential and session risk
Object storage S3-compatible private storage such as MinIO for development and S3-compatible production storage Separates large files from the application database and supports lifecycle policies
Document processing PyMuPDF, optional OCR service later, ClamAV or equivalent upload scanning Reliable text-based PDF baseline with explicit malware and extraction-quality checks
Background work Redis plus Celery or RQ workers Supports asynchronous analysis, retries, cleanup, notifications, and blockchain anchoring
Blockchain network Hyperledger Fabric permissioned network for production-style governance; a local Fabric test network for the academic MVP Provides controlled organizational membership, private channels, and tamper-evident provenance without exposing student data on a public chain
Blockchain SDK Hyperledger Fabric Gateway SDK for Python or a small Node.js gateway service Encapsulates chaincode calls and keeps blockchain integration out of ordinary domain handlers
Smart-contract logic Fabric chaincode for content-version anchoring, report-hash anchoring, reviewer identity, and revocation status Makes provenance verifiable without storing documents or personal data on-chain
API Versioned REST with OpenAPI documentation Stable integration and testing contract
Observability OpenTelemetry, Prometheus, Grafana, and structured JSON logs Measures API, RAG, queue, provider, and blockchain behavior without logging sensitive content
Delivery GitHub, pull requests, GitHub Actions, Docker Compose locally, containerized staging/production Reproducible engineering workflow and automated quality gates
The technology choice is less important than the controls around it. LangChain or LlamaIndex should be used only behind an observable internal RAG service; it must not obscure prompts, sources, retrieval scores, or failure states. The blockchain network is a provenance and integrity layer, not a storage layer, identity provider, payment system, or legal-validity oracle.

8.2 RAG implementation flow
Approved article or reviewed source
-> Normalize and clean content
-> Split into traceable chunks
-> Generate embeddings
-> Store chunks, metadata, and embeddings in PostgreSQL + pgvector
-> Create optional blockchain anchor for the content-version manifest

User question
-> Validate and classify
-> Apply jurisdiction/status/freshness filters
-> Hybrid keyword + vector retrieval
-> Rerank and select context
-> Generate structured answer
-> Validate citations and safety
-> Return answer with source references

The system must re-index content when a published version changes. Old embeddings must remain associated with their historical content version for audit and reproducibility, but they must not be retrieved for current answers unless the user explicitly requests historical information.

8.3 Blockchain usage and boundaries
Blockchain will be used selectively to create tamper-evident proofs for governed events. The recommended events are publication of a knowledge-article version, approval or verification of a help resource, generation of an analysis-report manifest, and revocation or supersession of a previously anchored version. The chain should store a content or manifest hash, object type, internal version identifier, timestamp, network transaction ID, and status. It must not store names, email addresses, document text, legal facts, uploaded files, AI prompts, full reports, or personally identifiable information.

The application database remains the operational source of truth. A blockchain anchor proves that a specific version or manifest existed in a particular form at a particular time; it does not prove that the content is legally correct, current, applicable, or approved by a court. Each anchor must have a revocation or supersession mechanism because immutable records cannot be edited in place. If the blockchain is unavailable, the platform should queue the anchor request and continue operating while clearly marking provenance as pending.

9. Data Model
   The initial relational model should include the following entities.

Entity Purpose Important fields
User Identity and account state id, email, name, role, status, created_at, last_login_at
Session or RefreshToken Session control id, user_id, expiry, revoked_at, device metadata
Category Shared taxonomy id, name, slug, status
KnowledgeArticle Reviewed awareness content id, category_id, jurisdiction, title, body, source, effective_date, review_date, version, status
ComplaintGuide Structured workflow id, category_id, jurisdiction, steps, evidence checklist, authorities, review metadata, status
HelpResource Verified support destination id, type, name, location, contacts, source, verification_date, expiry_date, status
Document User-owned file metadata id, user_id, storage_key, filename, type, size, checksum, retention_date, status
AnalysisJob Asynchronous processing state id, document_id, status, progress, error_code, pipeline_version
AnalysisReport Result and provenance id, document_id, summary, findings, confidence, model_version, created_at
Query User question metadata id, user_id, intent, risk, jurisdiction, created_at
AssistantResponse Generated response and provenance id, query_id, content, citations, retrieval_version, safety_route, feedback_state
Feedback Quality signal id, user_id, target_type, target_id, rating, comment, triage_status
Announcement Dashboard communication id, title, body, audience, publish window, status
ContentEmbedding RAG retrieval representation id, source_type, source_id, content_version, chunk_text, embedding, page_or_section, jurisdiction, status
ProvenanceAnchor Blockchain transaction reference id, object_type, object_id, version, content_hash, network, transaction_id, anchor_status, anchored_at, revoked_at
AuditEvent Governance and security record id, actor_id, action, object_type, object_id, timestamp, metadata
Sensitive fields should be minimized, encrypted where appropriate, access-controlled, and excluded from ordinary application logs.

10. Security, Privacy, and Trust Requirements
    The MVP must implement secure password hashing, HTTPS, server-side authorization, object-level file authorization, input validation, upload size and type limits, malware or file safety checks where available, rate limiting, CSRF protection where applicable, secure cookies or carefully managed tokens, secret management, dependency updates, and audit logging.

Administrative access should support least privilege. Content publication and user-management actions should be auditable. The system should separate development, staging, and production data and credentials. Error responses must not expose stack traces, internal paths, tokens, prompts, or private document content.

The privacy notice should describe what is collected, why it is collected, how long it is retained, who can access it, how deletion works, and which external AI or storage providers process data. The user should be warned not to upload unnecessary personal identifiers or confidential information. If external AI processing is used, the deployment must document the provider’s data-handling configuration and contractual suitability before production use.

A minimum threat model should address credential theft, broken object-level authorization, malicious uploads, prompt injection inside documents, data leakage through logs or prompts, administrator misuse, stale or manipulated help resources, denial of service, model hallucination, embedding leakage, poisoned knowledge-base content, compromised blockchain credentials, chaincode authorization flaws, and replay or duplicate anchoring. Each risk should have an owner, mitigation, and test case.

Blockchain credentials and network certificates must be stored in a secrets manager or protected deployment configuration. Chaincode must enforce authorized writers, validate object types and version transitions, reject unauthorized revocations, and emit auditable events. No private document or personal information may be included in transaction payloads, logs, or public blockchain metadata.

11. Non-Functional Requirements and Quality Targets
    Quality area MVP target
    Performance Typical non-AI API requests should meet a defined p95 target agreed by the team; long analysis must be asynchronous.
    Availability Core browsing and content access should remain usable when the AI provider is unavailable.
    Reliability Jobs must be retryable and idempotent; failures must be visible and recoverable.
    Security No known critical vulnerability at release; authorization and upload tests must pass.
    Accessibility Keyboard navigation, visible focus, semantic labels, readable contrast, and responsive layouts are required.
    Usability A first-time student should complete a core journey without legal or technical training.
    Maintainability API contracts, migrations, prompts, rules, and content schemas must be version-controlled.
    Observability Logs, metrics, traces or correlation IDs, job states, and provider failures must be diagnosable.
    Scalability Stateless API instances and externalized storage should permit horizontal growth.
    Data integrity Foreign keys, validation, checksums, and safe deletion workflows must protect records.
    RAG quality Retrieval, citation, embedding, and prompt versions must be observable and reproducible.
    Blockchain resilience Blockchain unavailability must not make core browsing, guidance, or document deletion unavailable.
    Exact numerical service-level objectives should be selected after measuring the deployment environment rather than copied without evidence.

12. API and Integration Principles
    All APIs should be versioned, documented with OpenAPI, validated with typed schemas, and return consistent error objects containing a safe code, human-readable message, correlation identifier, and optional field details. The API should never return another user’s object merely because a client supplied a different identifier.

Long-running operations should return a job identifier and status endpoint. The frontend should poll or use a supported event mechanism without exposing internal worker details. AI-provider failures, timeouts, quota errors, and unsafe outputs should map to stable application-level error states.

External resources in the Help Directory should be treated as governed data. A resource must have an owner, source, verification date, review interval, status, and deactivation mechanism. Links should be checked periodically where permitted, but a successful HTTP response alone must not be treated as proof that a resource remains appropriate.

13. Incremental Development Plan with Exit Criteria
    Each increment must include design, implementation, tests, documentation, demo evidence, and a retrospective. The next increment should not begin by ignoring unresolved critical defects in the previous one.

Increment Scope Exit criteria 0. Discovery and governance Jurisdiction decision, risk register, personas, content schema, threat model, UX flows, initial source inventory Approved scope, data classification, architecture decision record, and prioritized backlog

1. Foundation Repository, CI, database migrations, authentication, roles, dashboard shell, logging, error contract Registration/login/role tests pass; unauthorized access is blocked; staging deployment works
2. Knowledge system Categories, article schema, search, Rights Explorer, admin draft/review/publish flow Only reviewed content is public; source and review metadata are visible; search acceptance tests pass
3. Complaint and Help system Guided workflows, checklists, resource directory, verification status, emergency routing Published guides have reviewed steps; expired resources are hidden or clearly marked; usability test completed
4. RAG and AI Assistant Knowledge chunking, embeddings, pgvector, hybrid retrieval, intent/risk routing, constrained generation, citations, refusal, escalation, feedback Retrieval and answer evaluation meet agreed thresholds; source/version traceability works; provider outage fallback works
5. Document Analyzer Private upload, validation, extraction, classification, clause findings, report, async jobs, deletion, report-manifest hashing Cross-user access tests pass; extraction uncertainty is shown; reports include evidence and limitations; no document content reaches the blockchain
6. Blockchain provenance Local permissioned Fabric network, chaincode, content/report hash anchoring, verification endpoint, revocation and pending-anchor handling Valid anchors can be verified; unauthorized writes are rejected; blockchain outage does not block core workflows
7. Product hardening Vault history, announcements, analytics, accessibility, security testing, backup/restore, monitoring, release documentation Critical test suites pass; operational runbook exists; release candidate is accepted
   The original ordering placed document analysis before complaint guidance. The revised order introduces the Help and Complaint system before the AI and document modules so that users have safe human and institutional routes available when AI cannot help.

   13.1 Definition of done for every feature
   A feature is complete only when acceptance criteria, unit tests, integration tests, security checks, accessibility review, error states, audit behavior, documentation, and deployment configuration are present. AI features additionally require prompt/version tracking, evaluation evidence, source traceability, refusal tests, and a rollback or disable switch.

8. Testing and Validation Strategy
   Testing should cover unit behavior, API contracts, database migrations, authorization, file handling, queue retries, provider failures, content publication, keyword and vector search relevance, blockchain anchor verification, chaincode authorization, and end-to-end student journeys. Security tests must include IDOR attempts, role bypass, malicious filenames, oversized files, malformed PDFs, injection strings, rate-limit behavior, embedding and metadata leakage, duplicate or replayed blockchain requests, and log inspection.

The AI evaluation set should include ordinary questions, ambiguous questions, jurisdiction mismatches, outdated-content scenarios, requests for definitive legal conclusions, prompt injection embedded in uploaded text, emergency situations, and questions outside the knowledge base. Each test should have an expected route: answer with sources, clarify, refuse, or escalate. RAG tests should also verify that filters exclude draft, expired, revoked, or wrong-jurisdiction content and that every displayed citation supports the generated claim.

User acceptance testing should involve students and at least one qualified content reviewer. Test tasks should measure completion, comprehension, confidence calibration, error recovery, and whether users understand the non-advisory nature of the output. Feedback must be converted into backlog items rather than collected only for presentation.

15. Operations and Governance
    The product requires an owner for content freshness, resource verification, AI evaluation, security response, and incident handling. A review calendar should track article and resource expiry. Administrators need a dashboard for stale content, failed analyses, provider errors, user reports, and unresolved feedback.

The team should maintain runbooks for deployment, rollback, secret rotation, database migration, storage recovery, AI-provider outage, harmful-response escalation, resource deactivation, and data-deletion requests. Backups should be tested through restoration exercises rather than assumed to work.

A release should be blocked when any of the following is true: critical authorization failure, exposed private document, missing emergency route for a supported high-risk workflow, unreviewed legal content presented as current, inability to delete user documents according to policy, or evaluation evidence showing unsafe confident answers above the accepted threshold.

16. Risks and Mitigations
    Risk Impact Mitigation
    Hallucinated or overconfident AI output Users may make harmful decisions Retrieval, citations, constrained schema, refusal, escalation, evaluation, and disable switch
    Outdated law or resource Incorrect or unavailable guidance Jurisdiction/effective-date metadata, review calendar, expiry status, source ownership
    Misread document User may overlook a relevant issue Extraction confidence, page evidence, supported-format limits, human-review recommendation
    Sensitive document exposure Privacy and safety harm Private storage, object authorization, encryption, retention, deletion, access logs
    Scope expansion Delayed or incomplete delivery Explicit MVP boundaries and increment exit criteria
    Provider outage or quota Broken AI workflow Provider adapter, graceful fallback to Rights Explorer and Help Directory, retry states
    Prompt injection in documents Unsafe or manipulated analysis Treat extracted text as untrusted data; isolate instructions from document content
    Poor student comprehension False confidence or inaction Plain language, comprehension testing, visible uncertainty, actionable next steps
    Administrative error Incorrect content reaches users Draft/review/publish lifecycle, versioning, reviewer role, audit trail
    Legal or institutional misrouting Delayed help Location-aware resources, verification dates, multiple reporting options, escalation review

17. Future Roadmap
    Version 2 may add Hindi and other carefully reviewed languages, improved multilingual search, college-specific portals, richer analytics, and a mobile application. Version 3 may add verified legal professionals, appointment booking, and advanced contract comparison only after governance, identity, consent, and professional-liability requirements are designed. Later versions may consider government-service integration, document generation, voice assistance, and personalized recommendations.

Future scope must not be treated as a promise that the MVP already supports these capabilities. Each future feature requires a separate privacy, safety, legal, operational, and feasibility review.

18. Recommended Repository and Delivery Structure
    lexaware-student/
    ├── apps/
    │ ├── web/ # React client
    │ └── api/ # FastAPI application
    ├── workers/ # Extraction, RAG indexing, analysis, and anchoring jobs
    ├── blockchain/ # Fabric network configuration, chaincode, and gateway
    ├── packages/
    │ ├── contracts/ # Shared API schemas and types
    │ ├── prompts/ # Versioned prompt, response, and retrieval schemas
    │ ├── rag/ # Chunking, embeddings, retrieval, reranking, citations
    │ └── evaluation/ # AI test sets and scoring tools
    ├── content/
    │ ├── sources/ # Reviewed source inventory
    │ └── seed/ # Non-production seed data
    ├── migrations/
    ├── tests/
    │ ├── unit/
    │ ├── integration/
    │ ├── security/
    │ ├── e2e/
    │ └── ai-evaluation/
    ├── docs/
    │ ├── architecture/
    │ ├── adr/
    │ ├── runbooks/
    │ └── product/
    ├── infra/
    ├── .env.example
    └── README.md

Pull requests should describe the requirement IDs addressed, migration impact, security impact, test evidence, RAG index impact, chaincode or network impact, and operational changes. Prompt, content, embedding, and chaincode changes should be reviewed like code because they can change user-visible behavior or provenance guarantees.

19. Final Product Definition
    LexAware Student is an AI-assisted legal-awareness and next-step guidance platform for students, not an automated legal decision-maker. Its industrial quality comes from the complete system around the model: governed content, jurisdiction-aware sources, RAG retrieval with traceable citations, safe document processing, private storage, blockchain-backed provenance proofs, traceable reports, escalation routes, verified resources, role-based administration, measurable quality targets, and an incremental delivery process.

The recommended build strategy is to deliver a dependable foundation and governed information system first, then add AI and document analysis only after safe human routes and content controls are operational. This sequencing produces a more credible academic project, a safer product, and a stronger basis for future scale.

References
Implementation note: References to Indian authorities and portals are starting points for content governance. Before publication, each resource must be verified for current applicability, contact details, jurisdiction, and review date.
