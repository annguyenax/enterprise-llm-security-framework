# Benchmark V2

**Status: DONE** (Phase 12D artifacts only; FINAL freeze, not yet used by any
evaluation). After three Code X fix rounds, Code X final technical
verification, Gemini final academic audit, and Grok final red-team coverage
audit all returned PASS against commit `4e10a2e`; no Critical or blocking
Major issue remains. The same nine audited artifacts were then finalized
without changing their bytes — see
`docs/modernization-ai-reviews/phase-12d-audit-resolution.md`.
See `docs/benchmark-v2-methodology.md` for the full design rationale,
taxonomy, contamination controls, and limitations, and
`docs/decisions/ADR-003-v2-benchmark.md` for the governing split/freeze
rules.

## What this is

An independently-governed, deterministic benchmark for a future Phase 12E
security evaluation of the RAG pipeline (`POST /v1/rag/query`). 120 cases
across 23 scenario families, split 30 development / 30 validation / 60
holdout, backed by a 172-document synthetic corpus. Class balance: 48
benign / 48 malicious / 16 mixed / 8 neutral. Produced by
`scripts/build_v2_benchmark.py` with a fixed seed — no network access, no
LLM calls, no wall-clock content. Every family's development, validation,
and holdout content is drawn from three independently authored content
banks, not a shared template — see the methodology doc §10 for why this
matters and how it is verified.

This benchmark does **not** contain any final evaluation result. Phase 12D
does not run the RAG pipeline, does not compute ASR/FPR/FNR, and does not
modify any guard.

## Structure

```
corpus/documents.jsonl            172 ingestible documents (no ground truth)
cases/{development,validation,holdout}.jsonl   120 execution-only inputs (incl. evaluation_scope)
labels/{development,validation,holdout}.jsonl  120 ground-truth + authoring-metadata records
design/authoring-provenance.jsonl              292 non-runtime provenance records (1 per query + 1 per document)
manifests/benchmark-v2-manifest.json           SHA-256 FINAL freeze manifest (9 files covered)
contamination-exemptions.json                  optional, rationale-required similarity exemptions (currently empty)
```

Case files and label files are **strictly separate** — a case file never
contains `expected_final_decision`/`is_poisoned`/`expected_document_
ingestion_status`/any other ground-truth or authoring-metadata field, and no
file under `app/` ever imports or reads `cases/`, `labels/`, or `design/`.
`design/authoring-provenance.jsonl` is independently cross-checked against
the real case/document text (hash-verified, not merely present) by
`scripts/validate_v2_benchmark.py::check_authoring_provenance`, and is
integrity-bound by the final manifest exactly like the generated
corpus/case/label files.

Every field on every corpus/case/label/provenance record is validated
**type-first**: a malformed value (a `list`, `dict`, `bool`, or number
where a string/enum/list/integer is expected) is always confirmed to have
the right Python type *before* any set/dict membership test, so it always
produces a clean, aggregated validation error and never an unhandled
`TypeError: unhashable type` (Code X Phase 12D round 3 re-audit).

## Commands

```powershell
python scripts/build_v2_benchmark.py                  # build (deterministic)
python scripts/build_v2_benchmark.py --verify-determinism  # build twice, compare, no files written
python scripts/validate_v2_benchmark.py                # schema/integrity/contamination checks (guard-independent)
python scripts/validate_v2_benchmark.py --diagnose-current-guards  # optional, NON-GATING guard-agreement report
python scripts/freeze_v2_benchmark.py freeze            # authoring-time CANDIDATE manifest
python scripts/freeze_v2_benchmark.py finalize          # explicit audit-gated FINAL manifest
python scripts/freeze_v2_benchmark.py verify             # check the tree against the frozen FINAL manifest
```

`validate_v2_benchmark.py`'s default (gating) path imports nothing from
`app/guards/*` — a structurally valid label may legitimately disagree with
the current guard implementation without failing validation. The
`--diagnose-current-guards` flag is a separate, opt-in, non-gating developer
sanity check; it never affects the exit code and, by default, never touches
`holdout/` (add `--include-holdout-diagnostic` to include it).

Tests: `python -m pytest tests/test_benchmark_v2_schema.py
tests/test_benchmark_v2_integrity.py tests/test_benchmark_v2_freeze.py -q`.

## Holdout discipline

The `holdout` split must never be inspected to debug a guard rule. If a
holdout case is ever looked at to explain a rule failure and a rule is
subsequently changed, the holdout split must be treated as contaminated and
regenerated (ADR-003's "Rule of Freezing"). Any edit to this benchmark after
its freeze is committed requires a new version (v3) and a new manifest — no
silent mutation.

## Known limitations (see the methodology doc for detail)

Synthetic corpus, rule-based guard target only, no real LLM (deterministic
mock provider), no semantic retrieval (SQLite FTS5/BM25 only), no
production-representativeness claim, residual semantic/encoded/homoglyph/
paraphrased bypasses (lexical-similarity contamination checks do not replace
a true semantic-similarity model), benchmark-author/guard-author overlap,
and a benchmark-specific ~40-entry EN/VI phrase lexicon for translation
detection that is not a translation model (see methodology doc §10a for the
exact, tested boundary of what it does and does not catch).
