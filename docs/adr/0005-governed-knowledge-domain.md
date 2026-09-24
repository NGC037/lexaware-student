# ADR 0005: Governed Knowledge Domain, Immutability & Student-Safe Read Boundary

## Status

Accepted

## Context

LexAware Student provides college students in India with grounded, accessible legal awareness and guided next-step information across critical student life domains (ragging, tenancy and hostel security deposits, disciplinary actions, mental health rights, and consumer disputes).

The platform is explicitly **not** a law firm, does not provide legal representation or binding legal opinions, and relies on strict governance to ensure that all advice provided to students is accurate, currently applicable, verified against authoritative legal sources, and accompanied by plain-language summaries and escalation safety guidance.

To fulfill requirements **FR-05, FR-06, FR-07, FR-08, FR-26, and FR-27** of the *LexAware Student Industrial-Grade Product Specification v1.0*, we established the core Governed Knowledge Domain model and lifecycle management architecture.

## Decisions

### 1. Dual-Entity Content Modeling (`KnowledgeItem` and `KnowledgeVersion`)

We modeled knowledge as two distinct, strictly governed entities:
- **`KnowledgeItem` (Canonical Asset)**: Holds immutable classification metadata: `jurisdiction_id`, `category`, `topic`, `audience`, unique URL `slug`, `title`, and lifecycle `status` (`active`, `archived`).
- **`KnowledgeVersion` (Immutable Content Revision)**: Holds specific versioned textual data and governance metadata: `version_number`, `source_id`, `title`, `summary`, `content`, `applicability_notes`, `escalation_guidance`, `publication_state`, temporal windows (`effective_from`, `effective_until`), review tracking (`reviewed_at`, `reviewed_by_id`, `review_due_at`), publication tracking (`published_at`, `published_by_id`), and `change_summary`.

### 2. Explicit Publication State Machine & Edit Restrictions

A knowledge version transitions through explicit publication states:
`DRAFT` ➔ `IN_REVIEW` ➔ `APPROVED` ➔ `PUBLISHED` (and optionally `SUPERSEDED` or `ARCHIVED`).

**Invariants:**
- **Draft-Only Mutation**: Only versions in the `DRAFT` state can be edited directly. Any version in `IN_REVIEW`, `APPROVED`, `PUBLISHED`, `SUPERSEDED`, or `ARCHIVED` rejects mutation attempts with HTTP 400.
- **Sequential Versioning**: Updating published content requires creating a new sequential draft version (`v2`, `v3`, etc.) via `POST /admin/knowledge/items/{id}/versions`.
- **Single Active In-Flight Revision**: An item cannot have multiple unapproved drafts or concurrent in-review versions simultaneously.

### 3. Mandatory Publication Invariants (Gatekeeper Validation)

Before any version can transition to `PUBLISHED` via `POST /admin/knowledge/versions/{id}/publish`, the domain service executes strict invariant validation (`validate_publication_invariants`):
1. **Title**: Must be non-empty and substantive.
2. **Substantive Content**: Must contain at least 20 characters of verified text.
3. **Plain-Language Summary**: Mandatory for student discoverability and cognitive accessibility.
4. **Applicability Notes**: Mandatory to explicitly define legal and institutional scope (e.g. state or university applicability).
5. **Escalation Guidance**: Mandatory for student safety (hotlines, campus committees, emergency next steps).
6. **Active Authoritative Source**: Must link to an active, validated `Source` record with citation and retrieval metadata.
7. **Formal Review Completion**: Must have undergone formal review (`reviewed_at` and `reviewed_by_id` set by an authorized reviewer/admin).

### 4. Automatic Version Superseding Invariant

For any given `KnowledgeItem`, at most **one** version can be in the `PUBLISHED` state at any point in time.
When a new approved version is published, any existing `PUBLISHED` version for that knowledge item is automatically transitioned to `SUPERSEDED`, and an audit event (`knowledge.version.superseded`) is emitted.

### 5. Strict Student-Safe Read Boundary

Public student endpoints (`/api/v1/knowledge/*`) enforce hard safety query filters at the database level:
- Items must have `status == KnowledgeStatus.ACTIVE`.
- Versions must have `publication_state == PublicationState.PUBLISHED`.
- Temporal applicability: `(effective_from IS NULL OR effective_from <= now) AND (effective_until IS NULL OR effective_until >= now)`.
- Non-published content (drafts, in-review, approved but unpublished, superseded, and archived) is completely invisible to students. Slug lookups for unpublished or archived articles return HTTP 404.

### 6. Role-Based Governance Authorization (RBAC)

- **`student` / Public**: Can browse categories, search published articles, and inspect published article details with sources and escalation guidance.
- **`reviewer`**: Can create items, edit draft versions, submit for review, perform review decisions (approve/reject), schedule reviews, and view governance queues.
- **`publisher` / `admin`**: Holds exclusive authority to publish approved versions and unpublish/archive content.
- **`admin`**: Full administrative authority, including creating jurisdictions.

### 7. Content Freshness & Stale Review Queue (FR-27)

To prevent outdated legal advice from remaining published:
- Versions support a scheduled `review_due_at` timestamp.
- The governance queue endpoint `GET /admin/knowledge/stale-reviews` exposes all published versions where `review_due_at < now()`, enabling proactive legal compliance audits.

### 8. Structured Audit Trail

All governance lifecycle mutations emit structured `AuditEvent` records:
`knowledge.item.created`, `knowledge.version.created`, `knowledge.version.updated`, `knowledge.version.submitted_review`, `knowledge.version.approved`, `knowledge.version.rejected`, `knowledge.version.published`, `knowledge.version.superseded`, `knowledge.version.unpublished`, `knowledge.version.review_scheduled`.
Article bodies and full legal texts are never duplicated into audit payloads.

## Consequences

- Content integrity is strictly enforced; legal awareness materials cannot be published without plain-language summaries, applicability boundaries, active sources, and escalation guidance.
- Non-draft content is immutable, guaranteeing an unbroken revision history.
- Students are protected from accessing unverified drafts or outdated superseded guidance.
- Governance teams have real-time visibility into review schedules and stale legal articles.

## Student Search Extension (Chunk 2.2)

### PostgreSQL Full-Text Search

The existing `GET /api/v1/knowledge/articles` endpoint serves both browse and search. PostgreSQL stores a maintained `tsvector` on each `KnowledgeVersion`, built from its title, summary, content, JSONB `tags`, JSONB `keywords`, and nullable `synonyms` using the English text-search configuration. A database trigger refreshes the vector on insert and whenever one of those fields changes. Existing rows are backfilled by migration `a31c7e2f9d10`; a GIN index supports vector matches.

Search uses parameterized SQLAlchemy expressions with `plainto_tsquery` and `ts_rank_cd`. Category, jurisdiction, and audience remain normalized structured filters. For compatibility, item title/category/topic also have separately parameterized literal substring matching; these matches rank below full-text matches. Ties are ordered by version title, slug, item ID, and version number. No rank internals are exposed in student responses.

### Input, Results, and Pagination

Search terms are trimmed, control characters are removed, and query length is limited to 200 characters. PostgreSQL's plain-text query parser treats punctuation as input rather than query operators. Structured substring matching escapes wildcard characters. Empty or whitespace-only `q` uses the existing browse behavior. Browse and search default to 50 results, cap `limit` at 100, and accept offsets from 0 through 1,000,000.

Student list results include only student-facing article fields plus source title, publisher, URL, citation, review date, applicability notes, and escalation guidance. They omit publication state, reviewer/publisher IDs, audit data, and relevance scores. All search and filter predicates are applied in the same SQL statement after the active-item, published-version, and effective-date boundary.

### Limitations

English stemming is currently used for all indexed content. Search is lexical rather than semantic; synonyms must be entered by editors as searchable text. Searchable item classification remains structured and is not merged into the version vector. The trigram/fuzzy and multilingual search strategies are outside this increment.
