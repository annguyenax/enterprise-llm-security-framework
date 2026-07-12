# Code X Phase 12C Independent Audit

## Reviewed State
- Base: `phase-12-rag-v2` at `6c733247d3049e097754abdb520af475349128ef`
- Commit: `10e3e979fda577d6f077e7ce00b412118d1f8b04`
- Files inspected: complete Phase 12C diff; requested pipeline, guards, provider, logger, routes, configuration, schemas, four Phase 12C test modules, smoke script, and Phase 12C documentation. `app/guards/rag_context_guard.py` does not exist; the actual implementation inspected was `app/guards/rag_guard.py`.
- Git status before: `?? docs/modernization-ai-reviews/grok-phase-12c-red-team-audit.md`
- Git status after: three untracked review files: `codex-phase-12c-code-audit.md`, `gemini-phase-12c-academic-audit.md`, and `grok-phase-12c-red-team-audit.md`. None was created or modified by this audit.
- Tests executed: focused Phase 12C pytest suite; full pytest suite; `py_compile` for all changed Python files; targeted executable security probes. Smoke test not run because no live server was started.
- Test results: Phase 12C `79 passed, 1 warning`; full suite `267 passed, 1 warning`; Python compile checks passed. Test artifacts were redirected outside the repository. `git diff --check` passed; prohibited paths and `requirements.txt` are unchanged; no database is tracked.

## Critical Issues

### 1. DLP returns the uninspected output tail verbatim
- File and function: `app/guards/dlp_guard.py::scan_and_redact`; `app/services/rag_query.py::run_rag_query`
- Code evidence: `scan_and_redact` scans only `text[:max_chars]`, stores the remainder in `tail`, then returns `redacted + tail`. The pipeline ignores `DLPResult.truncated` and returns that text. Reviewer probe placed a bearer token after character 20,000; the API result remained `allow` and contained the raw token.
- Failure/attack scenario: A provider emits a long response with credentials after the inspection boundary. Bearer tokens and secret assignments not recognized by Output Guard pass directly to the caller.
- Minimal fix: Never append an uninspected tail. Fail closed on truncation, truncate the returned response at the inspected boundary, or enforce a provider-output maximum before DLP and inspect the complete returned output.
- Required regression test: Put each DLP-only secret type immediately after and across the boundary; assert no raw value reaches `RagPipelineResult.answer` or the HTTP response.
- Blocking: yes

### 2. Audit logger persists credentials covered by new DLP detectors
- File and function: `app/services/audit_logger.py::_SECRET_PATTERNS`, `_redact_value`, `log_event`; `app/guards/dlp_guard.py::_DETECTORS`
- Code evidence: Audit redaction imports only canary, OpenAI, AWS, GitHub, and private-key patterns. It omits the new bearer-token and secret-assignment patterns. Reviewer probe persisted both `Bearer abcdef1234567890xyz` and `password=UltraSecret123` verbatim.
- Failure/attack scenario: Caller metadata supplied to existing guard endpoints can place credentials in `audit.jsonl`, contradicting the logger’s no-secret persistence contract.
- Minimal fix: Make audit redaction consume the complete centralized detector set through a safe shared API, without retaining or returning uninspected text.
- Required regression test: Exercise real endpoints with bearer tokens and password/API-key assignments in nested metadata and assert the raw values are absent from the JSONL file.
- Blocking: yes

## Major Issues

### 1. Sanitized input is accompanied by the raw attack prompt at the provider boundary
- File and function: `app/services/rag_query.py::run_rag_query`, provider request construction
- Code evidence: Retrieval uses `effective_query`, but `LLMProviderRequest` receives both `prompt=query` and `sanitized_prompt=effective_query`. Reviewer probe confirmed the provider received the original attack suffix after Input Guard returned `sanitize`.
- Failure/attack scenario: Any provider implementation using `request.prompt` instead of `sanitized_prompt` reintroduces content explicitly removed by Input Guard.
- Minimal fix: Provider-facing fields must contain only the effective sanitized prompt, or the raw prompt must be removed from the provider contract.
- Required regression test: Force Input Guard `sanitize`, capture the provider request, and assert the removed text is absent from every provider-visible field.
- Blocking: yes

### 2. Aggregate inspection does not govern all context sent to the provider
- File and function: `app/services/rag_query.py::_build_aggregate_text`, `run_rag_query`
- Code evidence: Only the first 400 characters per chunk are considered; separator lengths are excluded from the global budget. Full chunks still reach the provider. An aggregate `sanitize` result is not applied to `final_chunks`. Probes showed split `ignore previous instructions` fragments reached the provider unchanged after `aggregate_sanitize`, and padded fragments beyond character 400 produced `allow`.
- Failure/attack scenario: An attacker pads each chunk before coordinated fragments or triggers a SANITIZE-only aggregate rule. The aggregate check reports success/sanitization while the provider receives the uninspected malicious content.
- Minimal fix: Ensure provider context is exactly the content covered by aggregate inspection. Fail closed on aggregate SANITIZE unless a deterministic per-chunk transformation exists, include separators in the bound, and reject or exclude content outside the aggregate budget.
- Required regression test: Cover SANITIZE-only split attacks, fragments after the per-chunk excerpt, fragments beyond the global budget, token splits at boundaries, and an assertion that aggregate length never exceeds configuration.
- Blocking: yes

### 3. Audit coverage is absent on several failure paths
- File and function: `app/services/rag_query.py::run_rag_query`, `_finalize`; `app/api/routes.py::rag_query`
- Code evidence: Retrieval exceptions propagate before `_finalize`; provider factory resolution occurs outside the provider `try`; route top-k rejection and exception mappings do not audit; `log_event` failures propagate without a safe fallback. A reviewer retrieval-failure probe produced no audit file.
- Failure/attack scenario: Storage, configuration, provider-factory, or audit-sink failures return 400/503/500 without the required structured security event. Provenance exceptions are also summarized as `provenance_evaluated`, obscuring the actual failure reason in audit stage codes.
- Minimal fix: Centralize safe finalization for all post-validation paths, preserve explicit safe failure codes, and define fail-closed behavior for audit-sink failure without exposing internal exceptions.
- Required regression test: Retrieval 400/503/500, provider-factory failure, provenance failure, DLP failure, audit write failure, and response-construction failure must have safe HTTP behavior and expected audit status.
- Blocking: yes

### 4. New configuration values are not validated
- File and function: `app/core/config.py::Settings`, `load_settings`; `app/api/routes.py::rag_query`
- Code evidence: The five new values are parsed directly with no positivity, relationship, or upper-bound validation. Reviewer probe successfully constructed negative top-k, aggregate, and DLP limits. Negative DLP slicing and non-positive aggregate limits weaken controls rather than failing startup.
- Failure/attack scenario: A malformed environment configuration silently disables aggregate inspection, breaks top-k behavior, or creates an unsafe DLP boundary.
- Minimal fix: Validate positive bounds, `rag_default_top_k <= rag_max_top_k <= retrieval_max_top_k`, and reasonable hard ceilings during settings construction/startup.
- Required regression test: Environment-driven zero, negative, contradictory, non-integer, and excessive values must fail clearly before routes serve requests.
- Blocking: yes

### 5. DLP redaction is reported as an allow decision
- File and function: `app/services/rag_query.py::run_rag_query`, `_finalize`
- Code evidence: The DLP stage has `decision=None`; DLP findings are excluded from `most_severe`. A response containing an in-bound secret can be modified while final decision and audit decision remain `allow`.
- Failure/attack scenario: Clients and later evaluation treat a security-relevant redaction as an untouched allow, understating leakage attempts and per-layer contribution.
- Minimal fix: Represent findings as `Decision.SANITIZE` and include that decision in final severity and structured audit output.
- Required regression test: Any DLP redaction must produce `sanitize`, accurate finding categories/counts, and no raw value.
- Blocking: yes

## Minor Issues

### 1. Overlapping DLP detectors inflate redaction counts
- File and function: `app/guards/dlp_guard.py::scan_and_redact`
- Code evidence: Detectors run sequentially over already-redacted text. `api_key=sk-...` is counted once as an API key and again as `api_key=[REDACTED]`, producing count 2 for one source span.
- Failure/attack scenario: Leakage metrics and detector contribution counts are inaccurate.
- Minimal fix: Collect spans from the original inspected text, resolve overlaps deterministically, then redact once.
- Required regression test: Overlapping assignment/API-key and repeated-secret cases with exact expected source-span counts.
- Blocking: no

### 2. Current application metadata still says retrieval does not exist
- File and function: `app/main.py` FastAPI title/description; `app/__init__.py` module documentation
- Code evidence: Both state that no real RAG retrieval exists, while Phase 12B/12C now implement SQLite retrieval and `/v1/rag/query`. Phase 12C documentation also overstates that every failure path is audited/safely structured.
- Failure/attack scenario: Generated API documentation and report evidence misrepresent the implemented state.
- Minimal fix: Update wording while retaining the no-real-LLM and non-production limitations.
- Required regression test: A small metadata assertion for current title/description, or a documentation consistency scan.
- Blocking: no

## Pipeline Order Conclusion
The nominal happy-path order is correct: Input Guard, retrieval, provenance, per-chunk context inspection, aggregate inspection, provider, DLP, Output Guard, audit, response. Blocked input does not retrieve, rejected chunks do not reach the provider, and DLP precedes Output Guard. The security data flow is nevertheless unsafe because raw sanitized-away input remains provider-visible, aggregate-uninspected context reaches the provider, and DLP-uninspected output reaches the API.

## Provenance/Trust Conclusion
Provenance handling is fail-closed for unknown values, matches the actual source-policy labels, preserves retrieval ordering, and does not let metadata override canonical provenance. Trusted content still undergoes context inspection. The all-rejected path avoids provider invocation. Exception audit coding remains incomplete.

## Multi-Chunk Aggregate Conclusion
Partially implemented but unsafe as an enforcement boundary. It is deterministic and bounded approximately, but not exactly; it samples only prefixes, omits separator cost, ignores sanitized aggregate output, and sends full uninspected chunks onward. The current named split-attack test demonstrates one favorable pattern, not robust enforcement.

## Centralized DLP Conclusion
Unsafe. Normal in-bound matches, repetition, multiline private-key blocks, and benign examples are handled deterministically with bounded regex work. However, uninspected tails are returned verbatim, audit redaction omits two centralized detector types, overlapping counts are inaccurate, and redaction does not influence final decision severity.

## Audit-Log Safety Conclusion
Query hashing and omission of retrieved text/provider output are sound on normal finalized paths. Raw SQL exceptions and stack traces are not returned by the API. Audit safety fails overall because bearer/password values can be persisted and several failure paths generate no audit event.

## API Boundary Conclusion
`RagQueryRequest(extra="forbid")` correctly rejects all specified caller-controlled context, provenance, trust, benchmark-label, guard-result, and canonical-ID fields with 422 responses. The endpoint accepts only query and optional bounded `top_k`.

## Backward-Compatibility Conclusion
The full 267-test suite passed. `/health`, `/v1/gateway/chat`, `/v1/retrieve`, `/v1/documents/ingest`, historical Output Guard behavior, and historical audit fixtures remain operational. No network request, external LLM call, dependency change, benchmark mutation, or tracked database was found.

## Missing Regression Tests
- DLP secrets after/across the inspection boundary.
- Bearer and secret-assignment redaction in real audit events.
- Sanitized prompts absent from every provider-visible field.
- Aggregate SANITIZE propagation and padded/budget-excluded split attacks.
- Exact aggregate bound including separators.
- Provenance, DLP, provider-factory, retrieval, audit-writer, and response-serialization failures.
- Environment-driven validation for all five new settings.
- DLP action reflected in final decision.
- Exact non-overlapping DLP counts and additional Unicode/emoji cases.

## Residual Risks Acceptable for Phase 12C
Rule-based detection can miss semantic, obfuscated, multilingual, and novel attacks. SQLite retrieval remains lexical, the provider remains deterministic and offline, and bounded aggregate inspection cannot eliminate multi-chunk coordination. These are acceptable only after all content sent downstream is actually within the enforced inspection boundary.

## Required Fixes Before Phase 12C Can Be Done
Close the DLP tail leak; apply all centralized detectors to audit logging; remove raw sanitized-away input from the provider boundary; make aggregate inspection govern the exact context sent to the provider; audit every controlled failure path; validate all new settings; and represent DLP redaction in final decision semantics with regression coverage.

## Final Verdict
REVISE