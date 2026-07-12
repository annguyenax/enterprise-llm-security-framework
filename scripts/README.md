# scripts/

Offline development, inspection, smoke-test, and evaluation helpers.

## Evaluation

- `run_evaluation.py` validates and evaluates `redteam/prompts.jsonl` directly
  against the guards, then writes JSON and Markdown artifacts under
  `reports/evaluation/`.
- `run_evaluation.ps1` is the PowerShell wrapper for the same offline run.

```powershell
python scripts/run_evaluation.py
.\scripts\run_evaluation.ps1
```

Baseline versus guarded comparison:

```powershell
python scripts/run_evaluation.py --comparison
.\scripts\run_evaluation.ps1 -Comparison
```

## Benchmark V2 (Phase 12D)

- `build_v2_benchmark.py` deterministically generates `datasets/v2/`
  (corpus, cases, labels, and a non-runtime `design/authoring-
  provenance.jsonl`) from a fixed seed. No network access, no LLM calls,
  no timestamp in generated content. Every scenario family draws its
  development/validation/holdout content from three disjoint, independently
  authored content banks (Code X Phase 12D audit fix — see
  `docs/benchmark-v2-methodology.md` §10), never a shared template.
  `normalize_for_fingerprint`/`normalized_text_hash` are the single
  canonical text-normalization implementation, imported directly by
  `validate_v2_benchmark.py` (same-directory script import) so a
  provenance hash can never silently drift between generation and
  validation. `--verify-determinism` builds twice in memory and fails if
  the two outputs (including provenance) differ, without writing any file.
- `validate_v2_benchmark.py` checks schemas, enums, complete field types
  (no unhandled crash on a malformed value — Code X Phase 12D re-audit,
  Major #1), exact counts, taxonomy-registry coverage, language coverage,
  exact class-distribution bounds, referential integrity, case-label
  mapping, duplicate IDs/`external_id`s, no orphan (unreferenced)
  documents, normalized-duplicate queries, cross-split secret reuse,
  cross-split content-fingerprint/similarity contamination, a
  benchmark-specific EN/VI bilingual-translation canonicalization check
  (`check_bilingual_contamination`, Code X Phase 12D re-audit, Critical
  #1.B), an authoring-provenance hash cross-check
  (`check_authoring_provenance`, Critical #1.A), v1-comparison
  contamination against both queries and every referenced corpus document
  (Critical #2 extension), source-key compatibility with
  `app/core/source_policy.py`, and manifest structural safety.
  Schema/type checks are a hard preflight before normalization, similarity,
  reference, or provenance processing, and are **type-first**: every
  enum/list/integer field is confirmed to have the right Python type
  (rejecting a list, dict, number, or bool) *before* any set/dict
  membership test or hash operation ever sees it (Code X Phase 12D
  malformed-value re-audit — previously `expected_stop_reason=[]` and
  authoring-provenance `split=[]` each raised an unhandled `TypeError:
  unhashable type`; both are now a clean, aggregated validation error).
  Reusable helpers (`validate_string_field`, `validate_string_enum`,
  `validate_optional_string_enum`, `validate_string_list`,
  `validate_integer_field`, `validate_json_safe_value`,
  `safe_record_identifier`) enforce this ordering consistently across
  every corpus/case/label/provenance/exemption field; `main()` keeps a
  final, last-resort defensive exception boundary, but the type-first
  helpers are the primary fix, not the boundary. **Guard-independent by
  default** —
  imports nothing from `app.guards.*`
  and its exit code never depends on the current guard implementation
  (Code X Phase 12D audit, Critical #1). An optional, explicitly opt-in,
  non-gating diagnostic reports agreement/disagreement with the real
  `app.guards.input_guard`/`app.guards.rag_guard` without affecting the
  result: `--diagnose-current-guards` (`--include-holdout-diagnostic` to
  also scope holdout).
- `freeze_v2_benchmark.py` writes/verifies a SHA-256 **candidate** manifest
  (`datasets/v2/manifests/benchmark-v2-manifest.json`, `"manifest_status":
  "candidate"`) covering all 9 policy-bearing files: `corpus/`, `cases/`,
  `labels/`, `design/` (the authoring-provenance artifact), and the
  top-level `contamination-exemptions.json` (Code X Phase 12D re-audit --
  every artifact that can change benchmark meaning or validation
  exemptions is now integrity-bound, not only the generated corpus/case/
  label files). Not a defensible final freeze until Code X, Gemini, and
  Grok all pass. A fresh freeze fails closed if either required policy-bearing
  file is missing.

```powershell
python scripts/build_v2_benchmark.py
python scripts/build_v2_benchmark.py --verify-determinism
python scripts/validate_v2_benchmark.py
python scripts/validate_v2_benchmark.py --diagnose-current-guards
python scripts/freeze_v2_benchmark.py freeze
python scripts/freeze_v2_benchmark.py verify
```

See `datasets/v2/README.md` and `docs/benchmark-v2-methodology.md` for the
full design. These three scripts are the only ones in this directory that
read or write `datasets/v2/` — they produce benchmark *artifacts only*, run
no evaluation, and modify no file under `app/`.

## Other Helpers

- `run_dev.ps1` starts the local FastAPI application.
- `smoke_test_gateway.ps1` exercises health, guards, and gateway responses.
- `inspect_dataset.py` / `inspect_dataset.ps1` inspect the synthetic corpus.
- `test_rag_guard.ps1` performs a manual RAG Guard smoke test.
- `smoke_test_retrieval.ps1` (**Phase 12B**) exercises `POST
  /v1/documents/ingest` and `POST /v1/retrieve` against a running server:
  ingests two synthetic documents, retrieves by keyword, updates one
  document, and verifies the stale (pre-update) content is no longer
  retrievable while the new content is. Recommended usage starts the
  server against a scratch database first, so the smoke test never
  touches your normal `data/retrieval.db`:

```powershell
$env:RETRIEVAL_DB_PATH = "$env:TEMP\smoke-retrieval.db"
uvicorn app.main:app --reload
# in a second shell:
powershell -ExecutionPolicy Bypass -File scripts/smoke_test_retrieval.ps1
```

- `smoke_test_rag_pipeline.ps1` (**Phase 12C**) exercises `POST
  /v1/rag/query` end to end against a running server: ingests one benign
  document and two documents containing indirect-prompt-injection text,
  runs a benign query (expects `allow`, provenance returned, the DLP
  stage present in `stage_results`), a mixed query (expects the poisoned
  document excluded from `accepted_context_count`), an all-poisoned
  query (expects `stop_reason=all_context_blocked` and
  `provider_called=false`), and a direct-injection query (expects
  `stop_reason=input_blocked` before retrieval), then reconfirms `POST
  /v1/gateway/chat` is unaffected. Documented, known limitation: it
  cannot demonstrate live secret redaction in a provider response,
  because the default Mock LLM Provider never echoes retrieved chunk
  text into its deterministic output — that exact scenario is covered
  instead by `tests/test_dlp_guard.py` and `tests/test_rag_pipeline.py`
  using a scripted offline provider double. Same scratch-database usage
  pattern as `smoke_test_retrieval.ps1`:

```powershell
$env:RETRIEVAL_DB_PATH = "$env:TEMP\smoke-rag-pipeline.db"
uvicorn app.main:app --reload
# in a second shell:
powershell -ExecutionPolicy Bypass -File scripts/smoke_test_rag_pipeline.ps1
```

The Phase 12C multidisciplinary audit-resolution run repeated this script
against a uniquely named temporary SQLite database and audit log, with the
server started hidden and stopped immediately afterward; it passed. Boundary
DLP and injected-provider scenarios remain deterministic pytest cases because
the live Mock Provider intentionally emits only its fixed short response.

No evaluation script calls an LLM API, vector database, or external service.
`smoke_test_retrieval.ps1` and `smoke_test_rag_pipeline.ps1` use only
Python's standard-library `sqlite3` and the offline Mock LLM Provider (via
the running server), and never touch `datasets/`/`redteam/`. Any future
paid API call still requires explicit approval under `AGENT_RULES.md`
rule 4.
