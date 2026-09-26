# ADR 0011: Permissioned blockchain provenance

- Status: accepted for local academic MVP
- Date: 2026-09-26

## Context

F9 / Increment 6 needs tamper-evident proofs for selected governed events without moving operational state or sensitive user data to a chain. Existing F8 report manifests already have deterministic SHA-256 canonical JSON hashing. Article publication, help-resource verification, and report creation are transactionally persisted in PostgreSQL.

## Decision

Use the official Hyperledger Fabric test network for local development, a small JavaScript chaincode contract, and the Fabric Gateway Node SDK behind an isolated loopback HTTP adapter. PostgreSQL remains the source of truth and holds a transactional provenance outbox/status row. A background worker submits and verifies chaincode transactions; domain workflows only enqueue metadata.

The ledger stores only object type, random internal UUID, version, SHA-256 digest, timestamp, transaction IDs, status, and superseding version. It receives no student identity, contact fields, private document bytes/text, report manifest, report findings, prompts, or secrets. Knowledge hashes use a versioned canonical projection. Report hashes use the F8 manifest hash implementation. Help-resource hashes intentionally exclude potentially identifying contact/name/description values.

Fabric chaincode verifies both Org1 MSP membership and `provenance.writer=true` certificate attributes. It validates UUID object IDs, supported types, positive monotonic versions, and lowercase SHA-256 digests. Duplicate matching anchors are idempotent; conflicting versions fail. Revocation/supersession is authorized, state-checked, idempotent for the same state, and preserves the original digest and anchor transaction.

The authenticated verification route scopes documents to their owner and requires article/help records to remain eligible for student display. Governance-role users may inspect non-current governed records. The route returns safe metadata and a distinct unavailable state rather than raw Fabric errors.

## Consequences

- Fabric outages leave durable, retryable pending outbox rows and do not block publication, resource verification, report generation, browsing, or deletion.
- Before an anchor retry after an ambiguous timeout, the worker queries the ledger; an already committed matching digest is reconciled without creating another anchor.
- The local two-organization network is a developer/academic MVP, not a production multi-party governance deployment. Writer certificate rotation, enterprise identity lifecycle, high availability, backups, and independent legal review are deployment work.
- An anchor establishes only that the digest was recorded at a time under the configured network. It does not establish legal correctness, applicability, enforceability, or factual accuracy.
