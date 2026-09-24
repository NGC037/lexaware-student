# ADR 0008: Governed Hybrid Knowledge Retrieval

- Status: Accepted
- Date: 2026-09-24

## Context

The assistant needs relevant passages from current, reviewed, published knowledge while preserving the existing PostgreSQL full-text search and student visibility guarantees. Lexical search handles exact legal terms and editor supplied keywords; vector similarity can find related wording. Neither signal is sufficient alone, and indexed passages can become stale after governance changes.

## Decision

Phase 4.2 stores deterministic, section-aware chunks from `KnowledgeVersion` in `knowledge_chunks`. Chunks retain their version foreign key, stable UUID, section, ordinal, hash, chunker version, embedding model and dimension, and the indexed version timestamp. Source, jurisdiction, publication, effective dates, source status, and review freshness are resolved through canonical live knowledge rows on every query. The shared `student_knowledge_eligibility` SQL boundary is used by public FTS reads and both hybrid candidate paths. Vector retrieval also requires an exact indexed-version timestamp match, so changed content is invisible until reindexed. Student/user documents and incident narratives are never indexed.

Migration `d4c2a9420f31` adds a 384-dimensional `vector` column, a version/model metadata index, and an HNSW cosine index. At this bounded scale the HNSW index gives a straightforward approximate nearest-neighbor path without introducing another service; governance predicates are still applied in SQL before candidates are returned. Downgrade removes only the chunk table/indexes and leaves the preexisting PostgreSQL extension intact.

Chunking is deterministic and section-aware (`section-window-v1`), with repeated section context, configurable character window/overlap, and UUID5 identifiers derived from version, chunker version, section, ordinal, and content hash. Embeddings use a vendor-neutral async batch protocol. A stable feature-hash fake is provided for tests only; the API defaults to a disabled adapter and calls no external embedding service. The embedding provider and immutable retrieval config are separate injectable dependencies so a future adapter/config can be selected without vendor dependencies in domain logic.

The internal hybrid service runs English `plainto_tsquery` FTS and cosine vector retrieval for one explicit jurisdiction. It merges duplicate knowledge versions, retains the strongest matching passage, normalizes lexical score as `r/(1+r)`, maps cosine distance to similarity as `clamp(1-distance, 0, 1)`, and combines them with equal weights. Vector-only matches below 0.35 similarity are discarded. Ties sort by combined score, lexical score, vector score, jurisdiction code, slug, version number, then chunk ID. Top-k is bounded to 1–20; per-path candidates are capped at 20. Configuration identifier `hybrid-fts-vector-v1` records the FTS language, embedding model/dimension, chunk settings, limits, threshold, metric, weights, merge/rank strategy, and filter policy.

Retrieval is only reachable inside assistant orchestration; no public vector endpoint is added. Missing or invalid jurisdiction requires clarification; jurisdictions are never combined. Empty governed results produce a safe clarification, and retrieval errors produce a distinct fail-closed response without invoking generation. High-risk safety routing still bypasses retrieval and providers. Retrieved text is explicitly untrusted context in the versioned prompt.

## Consequences

FTS remains the exact-term baseline and the student knowledge browse/search API remains backward compatible. Candidate citations retain source and effective/review metadata for grounding validation, while chunk IDs and internal scores are not exposed in student response schemas or audit metadata. Reindexing is explicit and transactionally replaces rows only after all embeddings validate. Existing vectors need not be physically deleted when content becomes ineligible because live filters hide them.

There is no production embedding adapter, real Gemini generation, learned reranker, multilingual model, private-document processing, or large-scale vector tuning in this phase. The deterministic hash fake is only a predictable integration-test adapter and does not establish semantic quality. Retrieval quality has not been evaluated against a representative evaluation set, so this establishes the retrieval engine and contract rather than production relevance. Production model selection and adapter configuration require a later change to the fixed vector dimension and retrieval configuration.
