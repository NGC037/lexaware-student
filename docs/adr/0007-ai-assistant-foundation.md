# ADR 0007: Bounded AI Assistant Foundation

- Status: Accepted
- Date: 2026-09-24

## Context

The student legal-awareness assistant needs explicit safety routing, current governed-source grounding, stable response contracts, and traceability before an external language model or augmented retrieval is connected. User incident narratives may contain sensitive details and must not be copied into persistent audit metadata.

## Decision

Phase 4.1 adds an authenticated `/api/v1/assistant/messages` endpoint, deterministic first-pass risk classification and a fail-closed gate, versioned prompt metadata, typed provider protocol and deterministic test adapter, current knowledge retrieval, citation/currentness checks, structured responses, correlation IDs, and metadata-only use of the existing audit log. High-risk requests bypass providers and may include only resources already returned by the verified-current help-resource query. The disabled provider is the default.

Student-facing knowledge retrieval also excludes explicitly overdue review versions and inactive or temporally invalid sources. A missing review due date retains the existing published-content behavior. Internal eligibility metadata is excluded from public response serialization. Emergency help resources are restricted to the supplied, recognized jurisdiction; without one, the assistant directs users to local emergency services without listing resources from unknown jurisdictions.

## Consequences

No model vendor, credentials, database schema, user-message persistence, real RAG/pgvector, or complaint intake is introduced. The deterministic classifier is a routing safeguard, not a complete risk assessment. Phase 4.2 can add a governed retrieval adapter and separately reviewed provider implementation behind the existing protocol. Audit metadata follows the existing audit-event retention and access policy.
