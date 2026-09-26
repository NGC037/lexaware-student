# ADR 0009: Production embeddings and grounded Gemini generation

## Status

Accepted for Phase 4.3; live provider rollout remains deployment-configured.

## Decision

- Use Google's stable `gemini-embedding-001` text model with explicit 768-dimensional output and `RETRIEVAL_DOCUMENT` / `RETRIEVAL_QUERY` task types. Normalize reduced-dimension results as required by that model. It is used only for governed public knowledge; private user documents are not embedded.
- Move pgvector storage and its HNSW cosine index from 384 to 768 using migration `c195dd7e5955`. This derived vector store is cleared on migration and must be rebuilt by running the eligibility-gated indexing service for each current published knowledge version. Existing 384-dimensional fake/test vectors cannot be reused.
- Use Google's stable `gemini-3.8-flash` through a dedicated adapter implementing the existing `AIProvider` contract and Google's official `google-genai` SDK. `AI_PROVIDER` and `EMBEDDING_PROVIDER` default to `disabled`; credentials are `GEMINI_API_KEY` environment/secret configuration only.
- Require JSON structured output matching the existing bounded Pydantic provider schema. Versioned prompt v2 separates system/application rules, schema, retrieved source data, and user data. Model output remains untrusted and application-validated.
- Preserve deterministic safety routing, live student knowledge eligibility, jurisdiction checks, citation-key allowlisting, and current-source validation. Unsafe/malformed output and provider failures fail closed; no generated fallback is fabricated.
- Persist only metadata needed for traceability: correlation, route, provider/model, prompt/schema/retrieval versions, knowledge references, validation outcomes, safe failure class, and latency. No key, user question, raw context, or full conversation is audited.
- Retrieval and assistant evaluation fixtures are deterministic and record case expectations and metrics; no quality score is claimed without running over a representative governed corpus.

## Consequences and limitations

- Model, dimension, task type, chunking, prompt, and retrieval configuration are versioned for reproducibility. Re-indexing is required after an embedding model or dimension change.
- Rule-based output checks catch common definitive/guaranteed claims and evidence-concealment language, but do not prove semantic entailment. Citation allowlisting proves that a displayed citation was retrieved and eligible, not that every sentence is entailed by it. Add a separately validated claim-to-passage entailment evaluator before making stronger grounding claims.
- The real provider smoke check requires a deployment secret and billing/quota configuration. Automated tests use mocks and do not call the external service.
- During the vector rebuild, full-text retrieval remains available. Vector results use only matching current model/dimension metadata, and live governance filters remain authoritative.
