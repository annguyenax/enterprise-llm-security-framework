# Phase 12C Multidisciplinary Audit Resolution

## Audit inputs

- **Gemini academic audit — REVISE.** Gemini explicitly reported that it
  could not inspect the actual repository diff or execute tests. Its findings
  are therefore conditional academic requirements, verified against the local
  repository before adjudication.
- **Grok red-team audit — REVISE.** Grok inspected the diff but executed no
  tests and identified no concrete file/function vulnerability. Its
  recommendations are used for adversarial variants, benign counterexamples,
  and limitation wording.
- **Code X engineering/security audit — REVISE.** Code X inspected the actual
  Phase 12C diff, ran the 79 focused tests and the then-current 267-test full
  suite, and reproduced security failures with executable probes. Its two
  Critical and five blocking Major findings are treated as blocking evidence.

## Decision methodology

Decisions follow this order: reproducible code/test evidence; repository
rules, ADRs, architecture and phase boundaries; reviewer findings naming exact
files/functions; then general recommendations. Each finding is classified as
Accepted, Partially accepted, Rejected, Deferred to Phase 12D, or Deferred to
Phase 12E. No benchmark label or expected decision was changed.

## Code X Critical findings

### A. DLP uninspected output tail

- **Finding:** `scan_and_redact` appended content after its inspection budget
  verbatim, allowing DLP-only credentials to reach the API.
- **Decision:** Accepted.
- **Evidence verified:** A bearer token after character 20,000 was returned
  with decision `allow` before the fix.
- **Files/functions changed:** `app/guards/dlp_guard.py::scan_and_redact`;
  `app/services/rag_query.py::run_rag_query`.
- **Fix:** Safe model B was selected. DLP returns only the completely inspected
  prefix; any suffix is dropped and `truncated=True` is recorded. Non-positive
  limits are rejected. No uninspected provider-output character reaches Output
  Guard, the API answer, or audit metadata.
- **Regression tests:** after-boundary bearer/password/API-key/private-key;
  boundary-crossing secret; long benign output; helper and HTTP pipeline
  truncation behavior.
- **Residual risk:** Truncation can reduce answer completeness. This is an
  explicit availability/usability tradeoff, not silent leakage.
- **Resolution status:** Resolved.

### B. Audit logger omitted centralized detectors

- **Finding:** Audit redaction listed five patterns locally and omitted bearer
  and secret-assignment detectors.
- **Decision:** Accepted.
- **Evidence verified:** Endpoint metadata containing bearer and password
  values was persisted verbatim before the fix.
- **Files/functions changed:** `app/guards/dlp_guard.py::redact_sensitive_text`;
  `app/services/audit_logger.py::_redact_secrets`, `log_event`.
- **Fix:** The logger calls one stable complete redaction API rather than
  importing detector internals. Nested/repeated values and private-key blocks
  use the same detector set. Findings never contain raw matches.
- **Regression tests:** A real guard endpoint writes nested bearer,
  `password=`, `api_key=`, repeated credentials, and a private key; no raw
  value appears, while a benign identifier remains visible.
- **Residual risk:** Regex DLP does not detect encoded or semantic secrets.
- **Resolution status:** Resolved.

## Code X Major findings

### A. Raw prompt remained provider-visible

- **Finding:** The provider request carried both raw and sanitized query text.
- **Decision:** Accepted.
- **Evidence verified:** A capture provider observed text removed by Input
  Guard in `request.prompt`.
- **Files/functions changed:** `app/services/rag_query.py::run_rag_query`.
- **Fix:** Both provider-facing prompt fields contain only `effective_query`.
  The raw query remains outside provider request objects and audit stores only
  its hash prefix and length. `/v1/gateway/chat` retains its old contract.
- **Regression tests:** Capture provider asserts removed attack text is absent
  from every provider-visible prompt field.
- **Residual risk:** Input Guard sanitization remains rule-based.
- **Resolution status:** Resolved.

### B. Aggregate inspection differed from provider context

- **Finding:** Prefix excerpts were inspected while full chunks were sent;
  separators were outside the budget and aggregate SANITIZE was ignored.
- **Decision:** Accepted.
- **Evidence verified:** Padded and SANITIZE-only split attacks reached the
  provider in executable probes.
- **Files/functions changed:**
  `app/services/rag_query.py::_bound_chunks_for_aggregate`, `run_rag_query`.
- **Fix:** Deterministic model C was selected. Chunks are bounded/truncated or
  excluded first, separators consume the same global budget, the exact joined
  representation is inspected, and only those exact bounded chunks reach the
  provider. Aggregate SANITIZE fails closed because no safe deterministic
  mapping exists from a sanitized joined blob back to source chunks.
- **Regression tests:** SANITIZE-only split, content after character 400,
  global-budget exclusion, exact separator accounting, provider/inspector
  equality, Vietnamese wrapper plus zero-width split, and high-trust malicious
  content.
- **Residual risk:** Semantic, paraphrased, homoglyph, and novel multilingual
  coordination can evade the existing lexical rules.
- **Resolution status:** Resolved for the stated deterministic invariant.

### C. Missing audit coverage on failure paths

- **Finding:** Retrieval and provider-factory failures could occur before
  finalization; provenance exceptions were mislabeled; audit-sink and response
  failures lacked explicit safe handling.
- **Decision:** Accepted.
- **Evidence verified:** A retrieval failure produced no audit event.
- **Files/functions changed:** `app/services/rag_query.py::_audit_failure`,
  `run_rag_query`; `app/services/audit_logger.py::log_event`;
  `app/api/routes.py::rag_query`.
- **Fix:** Retrieval errors emit a safe terminal event before propagation;
  provider factory/generation failures have distinct codes and called-state;
  provenance/context/aggregate/DLP/output exceptions fail closed; response
  construction maps to a generic request-ID 500. Sink failure performs no
  recursive retry and emits one standard-logger fallback signal containing
  only endpoint, request ID, and final decision.
- **Regression tests:** Retrieval, provider factory, provider, provenance,
  context, aggregate, DLP, Output Guard, sink, and response-construction paths.
- **Residual risk:** If both the JSONL sink and process logger are unavailable,
  durable audit persistence is physically impossible; the request still does
  not expose secrets or internal paths.
- **Resolution status:** Resolved within local PoC infrastructure.

### D. Phase 12C settings were not validated

- **Finding:** Zero, negative, contradictory, malformed, and excessive values
  were accepted.
- **Decision:** Accepted.
- **Evidence verified:** Negative aggregate and DLP limits constructed
  successfully before the fix.
- **Files/functions changed:** `app/core/config.py::Settings.__post_init__`,
  `_str_to_bool`, `load_settings`.
- **Fix:** Positive integers, default/max/retrieval top-k relationships, hard
  ceilings, and strict booleans are validated at construction/startup. Defaults
  preserve old direct `Settings(...)` calls.
- **Regression tests:** Zero, negative, contradictory, non-integer, excessive,
  malformed boolean, valid boundaries, and backward-compatible construction.
- **Residual risk:** Hard ceilings are project policy constants, not
  production capacity measurements.
- **Resolution status:** Resolved.

### E. DLP redaction was reported as ALLOW

- **Finding:** DLP findings did not participate in final severity.
- **Decision:** Accepted.
- **Evidence verified:** Redacted responses previously retained final decision
  `allow`.
- **Files/functions changed:** `app/core/pipeline.py::RagPipelineResult`;
  `app/services/rag_query.py::run_rag_query`, `_finalize`.
- **Fix:** Findings produce `Decision.SANITIZE`; DLP severity participates in
  final decision; typed category/count telemetry is retained and audited;
  Output Guard BLOCK remains more severe.
- **Regression tests:** Single/multiple DLP findings, no finding, Output Guard
  override, response/audit redaction, and category counts.
- **Residual risk:** Category counts represent deterministic pattern matches,
  not semantic leakage events.
- **Resolution status:** Resolved.

### Minor findings

- **Overlapping detector counts — Accepted.** Matches are collected from the
  original inspected text and overlapping source spans are resolved
  deterministically before one redaction pass. Regression covers
  `api_key=sk-...` as one source span.
- **Stale application metadata — Accepted.** `app/main.py` and
  `app/__init__.py` now state that SQLite lexical retrieval and
  `/v1/rag/query` exist, while retaining mock-provider and non-production
  limitations.

## Gemini academic findings

### A. Ablation toggles

- **Decision:** Deferred to Phase 12E.
- **Actual repository evidence:** Phase 12E explicitly owns `GuardProfile` and
  the ablation runner. Phase 12C exposes no request field, header, or serving
  setting that can disable a guard. Retriever/provider dependency injection and
  the orchestration boundary permit Phase 12E to add an internal typed profile
  without changing guard implementations or public schemas.
- **Correction or deferral plan:** Phase 12E will inject immutable named
  profiles only from trusted evaluation code; public runtime always uses full.
- **Phase 12D/12E impact:** Phase 12D authors data only. Phase 12E implements
  and tests reproducible profile execution.

### B. Granular telemetry

- **Decision:** Partially accepted.
- **Actual repository evidence:** Stable stage IDs, decisions, reason codes,
  monotonic per-stage latency, provider-called state, DLP category/count,
  retrieval counts, and context counts now exist in typed per-request results
  and safe audit metadata.
- **Correction or deferral plan:** Phase 12E aggregates these records into
  p50/p95 and marginal-contribution metrics. Request handling does not compute
  population statistics.
- **Phase 12D/12E impact:** No benchmark metrics are invented in Phase 12C.

### C. DLP construct validity

- **Decision:** Accepted.
- **Actual repository evidence:** DLP is deterministic regex redaction and the
  only runtime provider is a fixed mock.
- **Correction or deferral plan:** Architecture/threat-model documentation now
  limits evidence to verbatim pattern mitigation and rejects semantic,
  stochastic-real-LLM, and real-world leakage-rate claims.
- **Phase 12D/12E impact:** Future reports must preserve this claim boundary.

### D. Trust does not equal safety

- **Decision:** Accepted and already structurally enforced.
- **Actual repository evidence:** Provenance acceptance is followed by the
  complete per-chunk and aggregate context guards. A high-trust malicious
  regression confirms provider non-invocation.
- **Correction or deferral plan:** Documentation explicitly defines trust as
  origin/policy classification, never content safety.
- **Phase 12D/12E impact:** High-trust malicious and benign cases remain
  separate evaluation categories.

## Grok red-team findings

- **Vietnamese/English and zero-width coordination — Accepted.** Added a
  Vietnamese wrapper with an English split directive and zero-width evasion.
- **High-trust malicious and mixed-trust benign retrieval — Accepted.** Added
  provider-stop and acceptance tests respectively.
- **Benign academic/authority counterexamples — Accepted.** Added ordinary
  academic prompt-injection discussion and legitimate final-policy language.
- **Homoglyph/semantic coordination — Deferred to Phase 12D.** Current guards
  do not claim homoglyph normalization or semantic understanding. Phase 12D may
  author such cases without changing Phase 12C rules; misses must be reported.
- **Aggregate-size documentation — Accepted.** Documentation states the exact
  enforcement model, separator accounting, configuration, and residual risk.

## Pipeline order after resolution

Input Guard -> Retrieval -> Provenance Guard -> per-chunk RAG Guard -> exact
bounded aggregate enforcement -> Mock Provider with sanitized query and
inspected context only -> DLP over all returned content -> Output Guard over
redacted content -> safe terminal audit -> safe API response. No earlier
blocking stage invokes the provider.

## DLP boundary and decision semantics

Only the inspected prefix can be returned. The uninspected suffix is dropped,
truncation is explicit, source-span overlaps are counted once, findings produce
SANITIZE, and raw findings are absent from result/audit objects.

## Aggregate-context enforcement model

Chunks are bounded before aggregate inspection. Separator cost is included;
excluded content never reaches the provider; truncated accepted content is
reported as SANITIZE; aggregate SANITIZE/BLOCK/HUMAN_REVIEW all stop before the
provider.

## Audit failure-path coverage

All controlled service paths attempt one terminal JSONL event with safe reason
codes. Propagating retrieval failures audit first. Sink failure emits one
metadata-only fallback logger signal, does not retry recursively, and never
exposes submitted values or internal exceptions.

## Configuration validation

All five Phase 12C settings have safe defaults. Numeric limits are positive,
ordered consistently, and capped; malformed environment integers/booleans fail
before service use. Existing direct settings construction remains compatible.

## Ablation-readiness decision

GuardProfile is intentionally Phase 12E evaluation-only work. The public API
cannot select a profile or disable a guard. Existing typed boundaries and
dependency injection are sufficient for Phase 12E to add profiles without
editing guard implementations between runs.

## Telemetry-readiness decision

Per-request telemetry is sufficient for later aggregation: stable stages,
decisions, reason codes, monotonic timings, DLP categories/counts,
provider-called state, and retrieval/context counts. p50/p95 and ablation
matrices remain Phase 12E outputs.

## Claim limitations

This is an offline academic PoC using SQLite BM25, rule/regex guards, synthetic
tests, and a deterministic Mock Provider. It is not production-ready and does
not establish semantic prompt-injection resistance, real-LLM leakage rates, or
real-world detection performance.

## Phase 12C acceptance gate (superseded by the final re-audit section below)

| Gate | Result |
|---|---|
| All Code X Critical findings resolved | PASS |
| All blocking Code X Major findings resolved | PASS |
| No uninspected provider output returned | PASS |
| Audit logger uses complete centralized redaction | PASS |
| Provider sees sanitized query only | PASS |
| Provider context equals inspected context | PASS |
| Controlled failure paths audited safely | PASS at the time — **corrected below: two paths were still unaudited** |
| Phase 12C settings validated | PASS |
| DLP redaction represented as SANITIZE | PASS |
| Public API cannot disable guards | PASS |
| Stage telemetry sufficient for later aggregation | PASS |
| Gateway/retrieval/ingestion compatibility preserved | PASS — full suite |
| Focused Phase 12C tests | PASS — 123 passed |
| Full tests | PASS — 311 passed |
| Live smoke test | PASS — isolated temporary database/log |
| No prohibited artifact changed | PASS |
| No dependency added | PASS |
| No runtime database tracked | PASS |

~~## Final recommendation~~

~~APPROVE PHASE 12C~~

**Superseded — see "Code X final re-audit" below.** A subsequent
independent Code X re-audit of this exact state found two remaining
terminal-audit-coverage gaps that this document's own acceptance gate
table above should not have marked fully PASS. The corrected final
recommendation is recorded at the end of this document.

## Code X final re-audit

- **Verdict:** REVISE.
- **Remaining Critical findings:** none.
- **Remaining blocking Major finding:** terminal audit coverage was still
  incomplete for two specific paths, both of which reach
  `app/api/routes.py::rag_query` but do not go through the pipeline's own
  internal audit commit:
  1. **Configured `top_k` policy rejection.** `top_k > settings.rag_max_top_k`
     was checked and rejected with HTTP 400 *before* `run_rag_query` (and
     therefore its internal `log_event` call) ever ran — a valid request
     that reached this service produced zero audit trail.
  2. **Response-construction failure.** `run_rag_query`'s `_finalize`
     committed the terminal audit event (e.g. `final_decision=allow`,
     `stop_reason=allowed`) *before* `app/api/routes.py` had even
     attempted to build `RagQueryResponse(...)` from the result. If that
     construction then failed, the caller received a safe HTTP 500, but
     the audit log already contained a contradictory "success" record for
     the same request — the terminal event no longer described the
     outcome the caller actually received.
- **Decision:** Both accepted.

### Selected terminal-audit architecture

Per the review's own preferred architecture ("separate building the
result, constructing the response, and emitting the audit"), the fix
splits audit commitment out of the pipeline function entirely:

- `app/services/rag_query.py::run_rag_query_uncommitted(...)` — new.
  Contains the full pipeline body (previously `run_rag_query`'s body),
  returns `(RagPipelineResult, RagQueryAuditContext)` **without** calling
  `log_event`. `RagQueryAuditContext` is a small internal (not
  HTTP-facing) frozen dataclass carrying exactly the guard-decision
  objects and raw query `_finalize` used to need for logging, kept out of
  the public `RagPipelineResult` on purpose.
- `app/services/rag_query.py::commit_rag_query_audit(result, audit_ctx)`
  — new. The extracted logging body (previously inline in `_finalize`).
  Callers are responsible for calling this **exactly once**, for
  whichever outcome is actually visible to the caller.
- `app/services/rag_query.py::run_rag_query(...)` — unchanged public
  behavior/signature. Now a two-line wrapper: calls
  `run_rag_query_uncommitted`, immediately calls
  `commit_rag_query_audit`, returns the result. Every existing direct/
  service caller (this project's own test suite included) is
  byte-for-byte unaffected.
- `app/services/rag_query.py::audit_top_k_rejected(...)` — new. Emits
  exactly one safe `block`/`top_k_rejected` event (query hash/length
  only, never the raw query) for the configured-policy-rejection path,
  called by the route immediately before it raises the (unchanged) HTTP
  400.
- `app/services/rag_query.py::mark_response_construction_failed(result)`
  — new. Returns a `dataclasses.replace`d copy of an already-computed
  `RagPipelineResult` with `final_decision=block`,
  `stop_reason=response_construction_failed`,
  `error_category=response_construction_failed`, and a fixed safe
  `answer` string — `provider_called` and every count/telemetry field are
  preserved from the real result, since they describe what actually
  executed, not what the API layer later did with it.
- `app/api/routes.py::rag_query` — now calls
  `run_rag_query_uncommitted` (not `run_rag_query`), builds
  `RagQueryResponse(...)` inside its own `try`/`except`, and only *then*
  calls `commit_rag_query_audit` — with the real result on success, or
  with `mark_response_construction_failed(pipeline_result)` on failure.
  There is now no code path where a "success" event can be committed
  before the response object is known to be valid.

This is a "clear explicit internal contract" (two named Python functions
plus a small internal dataclass), not a public flag — nothing about it is
reachable from the HTTP request schema, and `run_rag_query`'s existing
callers require zero changes.

### `top_k` rejection behavior (fixed)

`app/api/routes.py::rag_query` now calls
`audit_top_k_rejected(request_id=..., query=request.query,
configured_max_top_k=settings.rag_max_top_k)` immediately before raising
the unchanged `HTTPException(400, ...)`. The retriever and provider are
never touched (verified by mocking `_retriever.search` and asserting zero
calls). The resulting audit event: `final_decision=block`,
`metadata.stop_reason=top_k_rejected`, `metadata.provider_called=false`,
`metadata.query_hash`/`query_length` present, raw query absent,
`metadata.configured_max_top_k` present (the same number the HTTP 400
body itself already discloses — not a new information disclosure).
`log_event`'s existing sink-failure handling (catches `OSError` and
similar, never raises, never exposes the exception) already covers this
call with no further wrapping needed — verified live by pointing
`log_path` at a directory and confirming the 400 response is unaffected.

### Response-construction failure behavior (fixed)

`app/api/routes.py::rag_query` builds `RagQueryResponse(...)` inside a
`try` block. On success, `commit_rag_query_audit(pipeline_result,
audit_ctx)` runs with the real, accurate outcome. On failure, exactly one
corrected event is committed instead —
`commit_rag_query_audit(mark_response_construction_failed(pipeline_result),
audit_ctx)` — with `final_decision=block`,
`stop_reason=response_construction_failed`, and `provider_called`
reflecting whatever the pipeline actually did (e.g. `true` if the
provider had genuinely already run before the later, unrelated
serialization failure). No earlier "success" event exists to contradict
it, because `run_rag_query_uncommitted` never audits on its own.

### Empty sanitized-query regression (added)

`tests/test_rag_pipeline.py::test_exact_empty_sanitized_query_is_rejected_and_audited_once`
monkeypatches `evaluate_input` directly to return
`GuardDecisionResponse(decision=Decision.SANITIZE, sanitized_text="")` —
not relying on punctuation-only raw text later tokenizing to nothing
during retrieval. `effective_query` becomes `""`, the real
`SqliteBM25Retriever` raises `EmptySearchQueryError` (mapped to HTTP 400
at the route), the provider is never invoked
(`provider.received_context_chunks is None`), exactly one
`stop_reason=retrieval_failed` audit event is committed before the
exception propagates, and the raw distinctive query text never appears
in the log.

### Regression tests added (8)

- `tests/test_rag_pipeline.py::test_audit_top_k_rejected_emits_exactly_one_safe_block_event`
- `tests/test_rag_pipeline.py::test_run_rag_query_uncommitted_does_not_audit_until_committed`
- `tests/test_rag_pipeline.py::test_mark_response_construction_failed_produces_corrected_block_event`
- `tests/test_rag_pipeline.py::test_exact_empty_sanitized_query_is_rejected_and_audited_once`
- `tests/test_rag_query_routes.py::test_top_k_rejection_returns_400_without_calling_retriever_or_provider`
- `tests/test_rag_query_routes.py::test_top_k_rejection_returns_safe_response_even_if_audit_sink_fails`
- `tests/test_rag_query_routes.py::test_response_construction_failure_emits_exactly_one_corrected_audit_event`
- `tests/test_rag_query_routes.py::test_response_construction_failure_audit_sink_failure_still_returns_safe_500`

### Test evidence

- Focused Phase 12C tests (`test_rag_pipeline.py` + `test_rag_query_routes.py`
  + `test_provenance_guard.py` + `test_dlp_guard.py` + `test_phase12c_config.py`):
  **131 passed** (up from 123).
- Full suite: **319 passed** (up from 311), run with an explicit writable
  `--basetemp`.
- `python -m py_compile` clean on every changed file.
- Live smoke test (`scripts/smoke_test_rag_pipeline.ps1`) against a real
  `uvicorn` server on a scratch database/log path: **PASSED**. Manually
  re-verified live that a `top_k=30` request produces exactly one
  `stop_reason=top_k_rejected` audit event with no raw query.
- `git diff --check`, prohibited-path diff, `requirements.txt` diff, and
  `git ls-files "*.db" "*.sqlite" "*.sqlite3"` all clean/empty.
- No `is_poisoned`/`expected_decision` usage in any Phase 12C runtime
  path (only in documentation/comments stating they are never read, or
  in the pre-existing, out-of-scope v1 benchmark loader/evaluation
  runner). No network-call pattern found in the changed files.

### Residual risk

If both the JSONL sink and the process-logger fallback are unavailable
simultaneously, durable audit persistence is physically impossible in
this local PoC infrastructure — the request itself still never exposes
secrets or internal paths either way. `mark_response_construction_failed`
assumes `RagPipelineResult` is a well-formed, already-validated object at
the point of failure (true by construction, since it comes from
`run_rag_query_uncommitted`); it does not attempt to recover from a
`RagPipelineResult` that is itself somehow malformed.

### Recommendation (superseded — see the next section)

~~**READY FOR ONE FINAL CODE X RE-AUDIT.** Not APPROVE, not DONE.~~ A
further independent Code X re-audit of this exact diff found one more
blocking gap in the same terminal-audit-coverage area, described below.
The claim above ("every response-construction path was already
protected") was **inaccurate** — nested response-model construction
(`ProvenanceItemResponse`) was not.

## Code X final terminal-audit re-audit (nested response construction)

- **Verdict:** REVISE.
- **Remaining Critical findings:** none.
- **Remaining blocking Major finding:** "Nested `ProvenanceItemResponse`
  construction occurs outside the protected response-construction and
  terminal-audit block." The previous pass's fix wrapped
  `RagQueryResponse(...)` itself (and, incidentally, the inline
  `StageResultResponse` list comprehension already nested inside that
  same call) in a `try`/`except`, but the separate `provenance = [...]`
  list comprehension — which constructs one `ProvenanceItemResponse` per
  accepted/rejected hit — was built **before** that `try` block, right
  after `run_rag_query_uncommitted` returned. A failure there (reachable
  only after the full pipeline, including the provider, had already run)
  propagated as a raw, unprotected exception: no safe
  `request_id`-bearing HTTP 500 (FastAPI's own default error handler
  would have produced a generic one instead), and — critically — **zero
  terminal audit events**, since it happened before both the
  success-commit and the `except` block's corrected commit.
- **Decision:** Accepted.

### Protected response-construction architecture (corrected)

`app/api/routes.py::rag_query` now builds **every** nested and outer
response object inside one single `try` block:

```text
try:
    provenance = [ProvenanceItemResponse(...) for ...]   # was outside; now inside
    stage_items = [StageResultResponse(...) for ...]      # already effectively inside; now explicit
    response = RagQueryResponse(..., provenance=provenance, stage_results=stage_items, ...)
except Exception as exc:
    commit_rag_query_audit(mark_response_construction_failed(pipeline_result), audit_ctx)
    raise HTTPException(500, f"Unexpected server error (request_id={request_id}).") from exc

commit_rag_query_audit(pipeline_result, audit_ctx)
return response
```

No nested Pydantic response item (`ProvenanceItemResponse`,
`StageResultResponse`, or any future addition placed inside this same
block) can be constructed before this protected block, and the
success/`SANITIZE` terminal audit event is committed only after the
**entire** response tree — every nested item plus the outer
`RagQueryResponse` — has been confirmed to build successfully. This
reuses the exact same `mark_response_construction_failed`/
`commit_rag_query_audit` contract as the previous pass's outer-model
fix; no change to `app/services/rag_query.py` was needed, since that
module's audit-deferral contract already supported this — only the
route's own code needed to move the list comprehension inside the
existing `try`.

### Nested provenance failure behavior

A failure constructing any `ProvenanceItemResponse` (or
`StageResultResponse`) now behaves identically to an outer
`RagQueryResponse` construction failure: HTTP 500 with the existing
`request_id` in the detail message; exactly one terminal audit event,
`final_decision=block`, `stop_reason=response_construction_failed`,
`provider_called` preserved from the real pipeline execution (e.g.
`true` if the provider had already run); no raw query, provider output,
retrieved chunk text, secret value, Pydantic validation text, exception
class/message, or stack trace anywhere in the response or the audit
event. No earlier "success" event exists to contradict it, for the same
reason as the outer-model case: `run_rag_query_uncommitted` never audits
on its own.

### Audit-sink failure behavior (nested case)

Combining a nested-construction failure with a simultaneously broken
audit sink still returns the same safe HTTP 500 with `request_id`
present, no internal details exposed, and exactly one safe
fallback-logger signal (`audit_sink_failure`) — no recursive retry
against the same failed sink. This reuses `log_event`'s existing,
unmodified sink-failure handling.

### Schema-level 422 boundary (now explicitly documented)

FastAPI/Pydantic request-schema validation failures (e.g. an
`extra="forbid"` violation, a missing required field, `top_k` outside
its static `ge=1, le=50` bound) happen **before** `rag_query`'s own
function body ever executes, and therefore before any pipeline call,
before `request_id` is even generated, and before any audit call is
possible. These 422 responses are explicitly **outside** the one-
terminal-audit-event contract described below — there is no service-level
request to audit yet at that point. This is unchanged behavior; it is
now stated explicitly here rather than left implicit.

### One-terminal-event contract (reconfirmed)

For every request that reaches `rag_query`'s function body (i.e. passed
schema validation):

- at most one terminal audit event is ever committed;
- a full pipeline success/`SANITIZE`/`BLOCK` outcome commits only after
  the entire response tree (every nested item plus the outer
  `RagQueryResponse`) is confirmed valid;
- a nested response-construction failure commits one corrected
  `block`/`response_construction_failed` event;
- an outer `RagQueryResponse` construction failure commits the same
  corrected event;
- the configured `top_k` policy rejection commits one
  `block`/`top_k_rejected` event before the pipeline ever runs;
- a retrieval failure (including the exact empty-sanitized-query case)
  commits one `block`/`retrieval_failed` event before propagating;
- schema-level 422 failures remain outside this contract, per the
  boundary stated above.

### Regression tests added (4)

- `tests/test_rag_query_routes.py::test_nested_provenance_item_response_failure_maps_to_safe_500_with_audit`
  (Regression A — forces `ProvenanceItemResponse` itself to raise after
  the provider has run; asserts safe 500 with `request_id`, exactly one
  `block`/`response_construction_failed` event with
  `provider_called=true`, and no raw query/provider text/exception text
  anywhere).
- `tests/test_rag_query_routes.py::test_nested_provenance_item_response_failure_with_audit_sink_failure_still_returns_safe_500`
  (Regression B — combines the same nested failure with a broken audit
  sink; asserts the safe 500 is unaffected and exactly one
  `audit_sink_failure` fallback signal is produced, no recursive retry).
- `tests/test_rag_query_routes.py::test_successful_nested_response_construction_emits_exactly_one_normal_event`
  (Regression C — the ordinary success path still returns provenance
  summaries and commits exactly one normal `allowed` event; proves the
  fix does not change existing success/`SANITIZE` semantics).
- `tests/test_rag_query_routes.py::test_nested_stage_result_response_failure_maps_to_safe_500_with_audit`
  (Regression D — a different nested model, `StageResultResponse`
  (always constructed at least once per request), forced to fail;
  confirms it follows the identical `response_construction_failed` path,
  not a special case unique to `ProvenanceItemResponse`).

### Test evidence

- Focused Phase 12C suite (`test_rag_pipeline.py` + `test_rag_query_routes.py`
  + `test_provenance_guard.py` + `test_dlp_guard.py` + `test_phase12c_config.py`):
  **135 passed** (up from 131).
- Full suite: **323 passed** (up from 319), run with an explicit writable
  `--basetemp`.
- `python -m py_compile` clean on `app/api/routes.py` and
  `tests/test_rag_query_routes.py`.
- Live smoke test (`scripts/smoke_test_rag_pipeline.ps1`) against a real
  `uvicorn` server on a scratch database/log path: **PASSED**.
- `git diff --check`, prohibited-path diff, `requirements.txt` diff, and
  `git ls-files "*.db" "*.sqlite" "*.sqlite3"` all clean/empty. No
  dependency added.

### Residual risk (nested-construction fix)

Same residual risk as the outer-model fix: simultaneous JSONL-sink and
process-logger-fallback failure makes durable audit persistence
physically impossible in this local PoC infrastructure, without ever
exposing secrets or internal paths. No further nested response model
exists in this endpoint's schema today beyond `ProvenanceItemResponse`
and `StageResultResponse`; if a future change adds another nested model
to `RagQueryResponse`, it must be constructed inside this same protected
block, not appended afterward.

### Final recommendation (superseded — the re-audit has since run; see below)

**READY FOR ONE FINAL CODE X RE-AUDIT.** Not APPROVE, not DONE. Per this
task's explicit instruction, Phase 12C remains **In Review** and is not
marked `Done` until this specific diff receives an independent Code X
re-audit returning PASS.

---

# Phase 12C Final Code X Re-Audit — PASS, Phase 12C CLOSED

Report: `docs/modernization-ai-reviews/codex-phase-12c-final-reaudit.md`

## Reviewed state

| Item | Value |
|---|---|
| Branch | `phase-12-rag-v2` |
| Reviewed HEAD | `9fed074481f46ce5e3ae2bfa20abcec3e36661fb` |
| Phase 12C implementation baseline | `ad555c95f01601b8eeeba92106b132ad88d7be00` |
| Final implementation commit | `56b749a47501ab9686503ca007c5197d8a6b47b0` |
| Actual code inspected | **Yes** — routes, schemas, pipeline contracts, RAG service, provenance/context/DLP/output guards, provider, audit logger, config, tests, audit history, README, task board |
| Tests independently executed | **Yes** — focused, targeted security probes, full unignored suite, compile checks, manifest verification |
| `app/` drift after baseline | **None** (post-baseline executable additions belong only to Phase 12D scripts/tests) |

## Verdict

- **Final Verdict: PASS**
- Critical Issues: **None**
- Major Issues: **None**
- Required Actions Before Phase 12C Can Be Marked DONE: **None**

## Previous blocking finding — RESOLVED

The nested `ProvenanceItemResponse` construction that previously occurred
outside the protected response/audit boundary (allowing an unaudited HTTP 500
*after* the provider had already executed) is confirmed fixed:
`ProvenanceItemResponse`, `StageResultResponse`, and `RagQueryResponse` are all
constructed inside one `try` block in `app/api/routes.py::rag_query`. The
success audit is committed only after the complete typed tree exists. Code X
independently confirmed: no false success audit is possible through either the
outer or nested construction paths; no partial response can be returned; failure
disclosure is a fixed request-ID-bearing HTTP 500 with no exception text,
context, query, secret, or path leakage.

## Security and pipeline invariants — all VERIFIED

Sanitized-prompt-only · bounded-approved-context-only · aggregate inspection
(exact provider context inspected, separator costs counted) · server-side
provenance · trusted content still inspected · DLP complete-output coverage
(uninspected suffixes dropped) · Output Guard `BLOCK` priority over DLP
`SANITIZE` · audit redaction across nested values · no public guard-disable
surface · no external network/provider drift (only the local Mock Provider).

## Executed test evidence (Code X, independently run)

| Check | Result |
|---|---|
| Focused Phase 12C suite | **172 passed, 1 warning** |
| Targeted Critical/Major probes | **24 passed, 1 warning** |
| Full repository suite (no `--ignore`) | **578 passed, 0 failed, 0 skipped, 1 warning** |
| Compile (`python -m compileall -q app tests`) | **PASS** |
| Repository modified by tests | No |
| Tracked database files | None |

The single warning is the pre-existing Starlette `TestClient`/`httpx`
deprecation notice. No dependency was installed; `httpx2` is a typosquat and is
never installed.

## Minor findings — adjudicated, all non-blocking

1. **Regression-test count wording.** The collaboration handoff
   (`docs/ai-collaboration/handoffs/phase-12c-final-reaudit.md`) said "5
   regression tests"; the authoritative resolution above correctly says **4
   newly added** nested-response tests. Both are defensible: five is the total
   only when the *earlier* outer-response atomicity regression
   (`test_response_construction_failure_emits_exactly_one_corrected_audit_event`)
   is counted alongside the four new nested-response tests. **Accepted:** the
   handoff wording was imprecise, not the resolution. Recorded here rather than
   silently corrected. Non-blocking.

2. **Non-finite `retrieval_score` serializes as JSON `null`.** A defensive probe
   showed a non-finite score would serialize to `null` rather than fail
   validation. The current SQLite BM25 implementation emits only finite scores,
   so this is **optional future schema hardening** (an explicit finite-float
   constraint on the response model), not a live defect. **Accepted as
   future work.** Does not block Phase 12C.

3. **Pre-existing ignored `__pycache__` directories.** Present in the tree, not
   created by the audit, not tracked by git, timestamps predate the audit.
   **Accepted:** not a Phase 12C blocker, no action taken.

## Deferrable recommendations (carried forward, not lost)

Semantic/homoglyph resistance and trusted-internal ablation profiles remain
inside the already-documented future evaluation scope. They do not block Phase
12C closure and are candidates for the Phase 12E ablation design.

## Final status

- **Phase 12C: DONE**
- Final Code X technical re-audit: **PASS**
- Remaining Critical issues: **None**
- Remaining blocking Major issues: **None**
- Phase 12D: **DONE** (9-artifact manifest FINAL, all three audit gates PASS)
- **Phase 12E: NOT STARTED** — requires a separate, explicit go-ahead per
  `AGENT_RULES.md` rule 12.
