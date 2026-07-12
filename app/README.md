# app/

Application code for the LLM Security Gateway / Guardrail Proxy.

**Status: Phase 12B (In Review) - SQLite FTS5/BM25 retrieval foundation.**
Rule-based Input, RAG Context, and Output guards, deterministic dataset
loading, JSONL audit logging, a mock chat pipeline, and a persistent local
document ingestion/retrieval foundation are implemented. No external LLM
call exists. **Retrieval is not yet wired into the guarded gateway** -
`POST /v1/rag/query` does not exist until Phase 12C; `POST /v1/gateway/chat`
is unchanged and still uses caller-supplied `context_chunks` only.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness check. |
| POST | `/v1/guard/input` | Evaluate a raw prompt. |
| POST | `/v1/guard/output` | Evaluate a candidate output. |
| POST | `/v1/guard/rag-context` | Evaluate caller-supplied context chunks. |
| POST | `/v1/gateway/chat` | Input -> RAG -> LLM Provider -> Output -> audit log (caller-supplied context only). |
| POST | `/v1/documents/ingest` | **Phase 12B.** Persistent document ingestion with server-controlled provenance/trust. |
| POST | `/v1/retrieve` | **Phase 12B.** Lexical (SQLite FTS5/BM25) retrieval only - no guard pipeline runs. |

## Guard Design

All three guards use small, explainable regex and keyword rules with the shared
decision order `block > human_review > sanitize > log_only > allow`.

- **Input Guard:** prompt injection, role and hierarchy attacks, jailbreaks,
  sensitive extraction, context manipulation, and tool misuse.
- **RAG Context Guard:** hidden instructions, system/developer overrides,
  transcript injection, fake-secret redaction, approval/policy bypass, and
  compound signals. Phase 5.1 adds detection-only normalization for whitespace,
  zero-width characters, and common light leetspeak.
- **Output Guard:** synthetic and realistic-looking secrets, email-like PII,
  system-instruction leakage, and classification markers.

RAG sanitization operates on original chunk text and preserves `doc_id` and
`metadata`. Hidden instruction blocks are removed selectively when possible.

## LLM Provider Adapter

`services/llm_provider.py` contains typed provider request/response models,
`BaseLLMProvider`, `MockLLMProvider`, and `get_llm_provider()`. The default
provider is deterministic, local, and offline. Gateway responses expose
`provider_name`, `model_name`, and `is_mock`; audit events store only those
provider fields, never provider prompts, context, or output.

Configuration defaults are `LLM_PROVIDER=mock`,
`LLM_MODEL_NAME=mock-rag-guard-v1`, and
`LLM_PROVIDER_TIMEOUT_SECONDS=30`.

## Retrieval Foundation (Phase 12B)

`retrieval/` and `services/ingestion.py`/`services/chunking.py` implement a
persistent, deterministic, offline lexical retrieval foundation using only
Python's standard-library `sqlite3` module (no new dependency):

- `retrieval/models.py` - typed, defensively-immutable records
  (`DocumentRecord`, `ChunkRecord`, `RetrievalHit`, etc.). Metadata is
  copied into a `MappingProxyType` at construction so callers cannot mutate
  a record after the fact.
- `retrieval/base.py` - the storage-agnostic `Retriever` protocol.
- `retrieval/sqlite_bm25.py` - the only implementation: a persistent SQLite
  file with an FTS5 virtual table, `bm25()`-ranked search, short-lived
  per-operation connections (never a shared global connection), and an
  explicit FTS5 capability check that fails loudly with **no fallback of
  any kind** (no `LIKE` search, no degraded scoring) if FTS5 is
  unavailable - see `docs/decisions/ADR-002-retrieval-engine.md`.
- `services/chunking.py` - deterministic, paragraph-aware chunking (v2),
  distinct from `services/dataset_loader.py`'s v1 fixed-window chunker,
  which is unchanged and still used only by the v1 benchmark loader.
- `services/ingestion.py` - validation, chunking orchestration, and atomic
  persistence via `Retriever.upsert_documents()`.
- `core/source_policy.py` - the **only** place `trust_level`/
  `classification`/`source_type` are assigned, always server-side from a
  `source_key` allowlist (only `api_upload` is reachable through the
  public `POST /v1/documents/ingest` endpoint; elevated-trust internal
  policies require `allow_internal=True`, which the public route never
  passes). A caller can never set these directly (the ingestion request
  schema has no such fields, `extra="forbid"` rejects any attempt to add
  them at the top level) and any attempt to smuggle them through the
  free-form `metadata` field is stripped before storage - recursively,
  through any combination of nested dicts and lists (a list-of-lists
  containing a reserved key is caught just like a plain nested dict is),
  matching case/whitespace/hyphen/underscore variants of the reserved key
  names, up to a bounded nesting depth beyond which the metadata is
  rejected outright. Before any of that recursive handling runs, an
  **iterative, non-recursive preflight** (an explicit stack, not Python
  function-call recursion) validates raw metadata structure, type, and
  nesting depth, and rejects direct Python object-identity cycles
  (reachable only via a direct service-level call - HTTP JSON can never
  contain a cycle) - this bounds traversal before `json.dumps` or the
  recursive sanitizer ever run, so a pathologically deep structure
  (verified to ~900 levels) is rejected in a bounded number of steps
  instead of raising an unhandled `RecursionError`. The configured
  metadata size limit is enforced against the raw, caller-submitted
  metadata *before* any stripping happens (so a large value cannot evade
  the limit merely by being placed under a key that sanitization would
  remove), and is measured as the actual **UTF-8 encoded byte length** of
  a deterministically-serialized form - not a Python character count,
  which under-counts multi-byte content such as Vietnamese text or emoji.
  Unknown `source_key` values are rejected, not silently downgraded to a
  low-trust policy - see `core/source_policy.py`'s module docstring for
  the documented rationale.

Query text is never concatenated raw into an FTS5 `MATCH` expression: user
queries are tokenized into plain lexical terms and each term is
individually double-quoted before being joined with an explicit,
server-generated `OR` into the final match expression, so FTS5 operators
(`NEAR`, `AND`/`OR`/`NOT`, column-filter syntax, wildcards) typed by a
caller are treated as literal search terms, never as operators. `OR` (not
implicit `AND`) means one extra, otherwise-irrelevant query term cannot
zero out an otherwise-matching result, while `bm25()` ranking still
rewards chunks matching more of the query's terms. SQL parameterization
alone does not protect against FTS5 query-syntax manipulation - FTS5
`MATCH` has its own query language.

The runtime retrieval/ingestion path never reads or stores the v1
benchmark's `is_poisoned` field - see `docs/modernization-v2-threat-model.md`
§3.

## Not Implemented

- No real external LLM provider call; only `MockLLMProvider` is implemented.
- No embeddings, similarity search, or vector database (lexical/BM25 only
  as of Phase 12B - see `docs/decisions/ADR-002-retrieval-engine.md`).
- No `POST /v1/rag/query` yet - retrieval is not wired into any guard or
  the LLM provider. That is Phase 12C.
- No semantic classifier or LLM judge. Rule-based detection can miss semantic,
  deeply obfuscated, or encoded attacks and may still produce false positives.
- Not production-ready: no production claim, no real-world detection-rate
  claim.

## Audit Logging

Guard decisions are appended as UTF-8 JSON Lines to `logs/audit.jsonl` by
default. Secret-like content is redacted before logging. Raw context chunks are
not written to the decision summary. Phase 12B ingestion writes one audit
event per batch call recording only safe fields (document ID, source key,
assigned source type/classification/trust level, a content-hash prefix, and
the result status per item) - never full document text.

## Not Production-Ready

This is a lab-scale university proof of concept. It does not claim complete
prompt-injection protection or provide a production security guarantee.
