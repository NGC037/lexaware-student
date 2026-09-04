# ADR 0003: Core Domain Persistence Model

## Status

Accepted

## Context

The detailed industrial product specification is not present in this repository. The first domain checkpoint still needs stable persistence boundaries for later API and workflow phases.

## Decision

Establish one migration-backed SQLAlchemy model slice for users and roles, jurisdictions, source-backed versioned knowledge, private documents and per-user access grants, audit events, help resources, and complaint records.

Use UUID identifiers, timezone-aware timestamps, explicit foreign keys, PostgreSQL enums for lifecycle states, and indexes on ownership, jurisdiction, publication, and audit lookup paths. Document ownership is represented by `documents.owner_id`; additional access is represented by `document_access` and never inferred from object-storage paths.

Store only the minimum application data needed for these foundations. Document contents remain in private object storage; audit details are structured metadata and must not contain document contents, credentials, or tokens. Blockchain provenance, authentication, and full complaint workflows remain outside this slice.

## Consequences

The schema supports object-level authorization checks, source provenance, review/publication state, jurisdiction-aware retrieval, and traceable security events without committing to future workflow details. Future migrations can add richer permissions, review assignments, document processing records, and complaint escalation entities without changing these ownership boundaries.
