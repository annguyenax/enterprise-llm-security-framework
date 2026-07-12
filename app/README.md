# app/

Application code for the LLM Security Gateway / Guardrail Proxy.

**Status: Phase 12C (In Review - ready for one final independent Code X
re-audit after the multidisciplinary audit resolution and a subsequent
terminal-audit-coverage fix) - end-to-end RAG security pipeline.**
Rule-based Input, Provenance/Trust, RAG Context, and Output guards,
centralized DLP, deterministic dataset loading, JSONL audit logging, a
mock chat pipeline, and a persistent local document ingestion/retrieval
foundation are implemented. No external LLM call exists. **Retrieval is
now wired into a guarded pipeline via `POST /v1/rag/query`** (Phase 12C);
`POST /v1/gateway/chat` remains completely unchanged and still uses only
caller-supplied `context_chunks` - it never calls the retriever or the
new pipeline. Not yet marked Done - see "Not Production-Ready" below and
`TASK_BOARD.md`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness check. |
| POST | `/v1/guard/input` | Evaluate a raw prompt. |
| POST | `/v1/guard/output` | Evaluate a candidate output. |
| POST | `/v1/guard/rag-context` | Evaluate caller-supplied context chunks. |
| POST | `/v1/gateway/chat` | Input -> RAG -> LLM Provider -> Output -> audit log (caller-supplied context only, unchanged since Phase 6). |
| POST | `/v1/documents/ingest` | **Phase 12B.** Persistent document ingestion with server-controlled provenance/trust. |
| POST | `/v1/retrieve` | **Phase 12B.** Lexical (SQLite FTS5/BM25) retrieval only - no guard pipeline runs. |
| POST | `/v1/rag/query` | **Phase 12C.** Full guarded end-to-end pipeline: Input Guard -> server-side retrieval -> Provenance/Trust Guard -> RAG Context Guard -> Mock Provider -> centralized DLP -> Output Guard. See "End-to-End RAG Pipeline" below. |

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

## End-to-End RAG Pipeline (Phase 12C)

`POST /v1/rag/query` (`app/services/rag_query.py`) is a new, additive
pipeline behind a strict request schema (`RagQueryRequest`,
`extra="forbid"`) that accepts only `query` and an optional `top_k` -
there is no field for `context_chunks`, `trust_level`, `classification`,
`source_type`, `is_poisoned`, `expected_decision`, a guard decision, or a
canonical document/chunk ID, so a caller cannot supply or override any of
them. Context is always retrieved server-side.

Stage order (guard failures fail closed; retrieval failures use safe audited
HTTP mappings rather than a `RagQueryResponse`):

1. **Input Guard** (existing, unchanged) - a blocked/human-review query
   never reaches retrieval or the provider.
2. **Retrieval** (Phase 12B `SqliteBM25Retriever`, server-side only,
   bounded `top_k`) - `EmptySearchQueryError`/`FTS5UnavailableError` map
   to the same HTTP 400/503 `POST /v1/retrieve` already uses for the
   identical exceptions. Zero hits is a safe `allow`/no-answer outcome,
   not an error.
3. **Provenance/Trust Guard** (`app/guards/provenance_guard.py`, new) -
   three fixed allow-lists (`trust_level`, `classification`,
   `source_type`), matching exactly the values
   `app/core/source_policy.py`'s real (non-fallback) policies produce
   today. Fails closed on anything else - including the
   `untrusted_unknown`/`unverified` fallback pair
   `UNKNOWN_SOURCE_POLICY` produces. A caller cannot influence this
   guard's decision at all, since it only ever reads a `RetrievalHit`'s
   server-assigned fields, never request input or chunk metadata.
   **Trust does not prove content safety** - an accepted, even
   `trusted_internal`, chunk still goes through the full content-based
   RAG Context Guard next; a compromised high-trust source remains a
   documented residual risk (`docs/modernization-v2-threat-model.md`
   §3).
4. **RAG Context Guard** (existing, unchanged), run once per
   provenance-accepted chunk, then a **bounded aggregate pass**: the
   accepted chunks are deterministically truncated/excluded first, with
   chunk separators included in `RAG_MAX_AGGREGATE_CONTEXT_CHARS`
   (default 4000 chars total). That exact bounded representation is
   joined and re-inspected as one synthetic chunk by the same,
   unmodified `evaluate_rag_context()` - a deterministic, best-effort
   mitigation for an instruction split across multiple chunks that no
   single chunk's inspection would catch alone (Phase 12A audit
   resolution, Grok Critical 2's required explicit decision - see
   `docs/modernization-v2-threat-model.md` §3, Tampering row). This does
   not eliminate semantic multi-chunk coordination risk. The provider
   receives only the bounded chunks inspected here. Aggregate `sanitize`
   fails closed because the sanitized joined text cannot be mapped safely
   back to individual source chunks.
5. **Mock LLM Provider** (existing, unchanged) - receives only the
   chunks that survived steps 3-4 and only the post-Input-Guard effective
   query; raw text removed by Input Guard sanitization is not included in
   any provider-visible request field.
6. **Centralized DLP** (`app/guards/dlp_guard.py`, new) - deterministic
   regex detectors (canary secret, OpenAI/AWS/GitHub key shapes,
   PEM private-key blocks, bearer tokens, `key: value`/`key=value`
   secret assignments) redact the provider's raw output before Output
   Guard or the API response ever see it. Content after the bounded
   inspection prefix (`DLP_MAX_INSPECT_CHARS`, default 20,000 chars) is
   dropped rather than appended uninspected; truncation is recorded in
   the stage result. Any finding produces `Decision.SANITIZE`. This module is also
   now the single source of the secret patterns previously duplicated in
   `app/guards/output_guard.py` and `app/services/audit_logger.py`.
   Audit logging calls the complete shared redaction API, so bearer and
   secret-assignment detectors cannot drift out of its safety net.
7. **Output Guard** (existing, unchanged) - evaluates the DLP-redacted
   text, never the raw provider output.
8. **Structured audit event** - one JSONL event attempt per call, safe fields
   only (see "Audit Logging" below); the raw query is never logged, only
   a SHA-256 hash prefix and length (stricter than other endpoints'
   redacted-preview convention, since a natural-language RAG query may
   embed sensitive enterprise content that pattern-based redaction alone
   would not catch). Retrieval errors are audited before their safe HTTP
   mapping. If the configured sink itself fails, a single metadata-only
   fallback logger signal is emitted without raw values or retry recursion.

Guard exceptions at any stage fail closed (mapped to a safe `block`
decision for that stage, not an unhandled 500); a bug in one guard
degrades the pipeline to a safe refusal rather than an open pass-through
or a crash. The response never includes full retrieved chunk text by
default - only a safe per-hit provenance summary (`document_id`,
`chunk_id`, `title`, `source_type`, `classification`, `trust_level`,
`rank`, `retrieval_score`, `status`, `reason_code`).

## Not Implemented

- No real external LLM provider call; only `MockLLMProvider` is implemented.
- No embeddings, similarity search, or vector database (lexical/BM25 only
  as of Phase 12B - see `docs/decisions/ADR-002-retrieval-engine.md`).
- No semantic classifier or LLM judge. Rule-based detection can miss semantic,
  deeply obfuscated, or encoded attacks and may still produce false positives.
- No `GuardProfile` ablation harness yet (`app/core/pipeline.py` holds
  only the Phase 12C typed pipeline result; the on/off layer-ablation
  configuration named in `docs/modernization-v2-architecture.md` §2 is a
  Phase 12E concern, deliberately not implemented in this pass). Public
  requests cannot disable guards through fields, headers, or serving-mode
  configuration; the full secure profile is mandatory.
- Multi-chunk coordination is only partially mitigated (see "End-to-End
  RAG Pipeline" above) - not fully solved.
- Not production-ready: no production claim, no real-world detection-rate
  claim.

## Audit Logging

Guard decisions are appended as UTF-8 JSON Lines to `logs/audit.jsonl` by
default. Secret-like content is redacted before logging. Raw context chunks are
not written to the decision summary. Phase 12B ingestion writes one audit
event per batch call recording only safe fields (document ID, source key,
assigned source type/classification/trust level, a content-hash prefix, and
the result status per item) - never full document text. Phase 12C's
`POST /v1/rag/query` commits exactly one terminal audit event per
request that reaches the service, recording only a query hash/length,
retrieval/accepted/rejected counts, per-stage reason codes, provenance
trust-level categories, DLP finding categories and count, per-stage
latency, and provider metadata - never the raw query, full retrieved
chunks, full provider output, or any detected secret value. This covers
every controlled outcome, including two paths fixed by a Code X final
re-audit that previously bypassed it: a configured `top_k` policy
rejection (audited via `audit_top_k_rejected` immediately before the
HTTP 400, before any pipeline stage runs) and a response-construction
failure (the pipeline's own computed outcome is deliberately not
committed until `app/api/routes.py` confirms the API response object was
built successfully; on failure, a corrected
`block`/`response_construction_failed` event is committed instead of the
pipeline's original, no-longer-accurate one - see
`app/services/rag_query.py::run_rag_query_uncommitted`/
`commit_rag_query_audit`/`mark_response_construction_failed`).

Phase 12C settings fail construction/startup when top-k relationships are
contradictory, integer limits are non-positive or exceed hard ceilings, or
boolean/integer environment values are malformed. Per-request telemetry uses
stable stage IDs, safe reason codes, monotonic stage timings, provider-called
state, DLP categories/counts, and retrieval/context counts. Phase 12E will
aggregate these into p50/p95 and ablation metrics; the request path does not
invent aggregate benchmark results.

## Not Production-Ready

This is a lab-scale university proof of concept. It does not claim complete
prompt-injection protection or provide a production security guarantee.
