# Phase 12D Code X Audit Resolution

## Reviewed audit

`docs/modernization-ai-reviews/codex-phase-12d-benchmark-audit.md` —
independent technical audit of Phase 12D at commit
`94f7bdefe166087a4edb6723558b888d7d062a06`, branch
`phase-12d-v2-benchmark`. Final verdict: **REVISE** (2 Critical, 3 Major,
2 Minor). This document resolves the 2 Critical and 3 Major blocking
findings only, per the resolution task's explicit scope. Minor findings
(per-family holdout sample sizes of 2–8 supporting only descriptive, not
statistically meaningful, per-family rates; manifest/documentation should
consistently say "candidate" until all audits pass) are addressed as part
of the same fix pass (see "Statistical reporting limitations" and
"Candidate manifest" below) since they overlap directly with the Major #3
and freeze-labeling work.

## Evidence hierarchy

Findings are adjudicated by direct inspection of the current repository
state after the fix, in this priority order:

1. **Executed command output** in this session (build, `--verify-
   determinism`, validate, freeze, verify, pytest) — highest weight.
2. **Direct source reads** of the fixed `scripts/build_v2_benchmark.py`,
   `scripts/validate_v2_benchmark.py`, `scripts/freeze_v2_benchmark.py`,
   and the real `app/guards/input_guard.py`/`app/guards/rag_guard.py` rule
   tables, cross-checked against the exact regex each cited rule uses.
3. **Ad-hoc verification scripts** run directly against the real guard
   functions during this fix pass (not a test file, but executed and
   inspected) — used to catch and fix authoring bugs before finalizing.
4. **Code X's own audit text**, used only to state what was found, never
   as a substitute for re-verifying the current state independently.

No claim below is made without a corresponding executed command or direct
source read in this session.

## Critical 1 — Guard-dependent validation

- **Decision:** CONFIRMED and fixed.
- **Verified evidence:** `scripts/validate_v2_benchmark.py::
  check_guard_cross_reference` (pre-fix) imported
  `app.guards.input_guard.evaluate_input`/
  `app.guards.rag_guard.evaluate_rag_context` and appended any mismatch
  directly into `all_errors` inside `main()`, so `validate_v2_benchmark.py`'s
  exit code depended on today's guard behavior. Reproduced Code X's exact
  finding independently before fixing: flipping a `direct_injection`
  label's `expected_final_decision` to `"allow"` (a value that genuinely
  disagrees with the real Input Guard's BLOCK decision for that query) made
  the pre-fix validator return non-zero solely due to that disagreement.
- **Fix:** the default `main()` call chain in the rewritten
  `scripts/validate_v2_benchmark.py` no longer calls any guard-cross-check
  function and imports nothing from `app.guards.*`,
  `app.services.rag_query`, or any other Phase 12C runtime module at
  module scope. The guard cross-check survives only as
  `diagnose_against_current_guards()`, invoked exclusively via the
  explicitly opt-in `--diagnose-current-guards` CLI flag; it lazily adds
  the repository root to `sys.path` and imports guard modules only inside
  that function body, never at import time, and never contributes to
  `all_errors`. It defaults to development+validation scope only;
  `--include-holdout-diagnostic` is required to also scope holdout, so an
  ordinary development invocation cannot accidentally print holdout ground
  truth.
- **Tests:** `tests/test_benchmark_v2_integrity.py::
  test_schema_valid_label_disagreeing_with_current_input_guard_still_passes`
  (required regression #1 — reproduces the exact scenario above and
  confirms the mutated-label input passes `check_schemas`/
  `check_class_distribution`/`check_case_label_mapping` cleanly);
  `test_diagnostic_mode_reports_mismatch_without_changing_validator_result`
  (required regression #2 — confirms the diagnostic reports the same
  mismatch while `validate_mod.main([])` on the real files still returns
  0); `test_builder_output_unchanged_when_guard_module_is_monkeypatched`
  (required regression #3 — monkeypatches `app.guards.rag_guard` with a
  module that raises on every call, confirms `build_all()`'s byte-for-byte
  output is unaffected, since the generator never imports it);
  `test_default_validation_path_imports_no_guard_modules` (required
  regression #4 — clears `app.guards*`/`app` from `sys.modules`, runs the
  default checks, asserts none of `app.guards.*` was re-imported);
  `test_no_gating_check_function_imports_app_guards` (required regression
  #5 — inspects the source of every function called from `main()`'s
  gating path and asserts none references `app.guards`).
- **Residual risk:** none identified for this finding specifically. The
  optional diagnostic still exists and is genuinely useful for authoring
  (it caught real bugs during the Critical #2 fix, see below); its
  non-gating status is now enforced by the tests above, not merely by
  convention.
- **Status:** RESOLVED.

## Critical 2 — Holdout template contamination

- **Decision:** CONFIRMED and fixed.
- **Verified evidence:** direct read of the pre-fix
  `scripts/build_v2_benchmark.py` confirmed every family builder function
  (e.g. `build_multi_chunk_coordination`, `build_indirect_retrieved_
  injection`) constructed development/validation/holdout content from one
  shared Python literal, varying only the per-case `V2TOK#####` token and,
  for a few families, a language-rotation index — there was no per-split
  content variation at all for most families. This matches Code X's
  measured 34/60-holdout-queries-≥0.9-similar and 17/23-families-shared-
  template findings exactly, and the shape of the bug (parameter
  substitution, not independent authorship) matches Code X's description.
- **Fix:** `scripts/build_v2_benchmark.py` was rewritten so every one of
  the 23 families now sources its development/validation/holdout content
  from three disjoint module-level content banks (`_*_DEV`/`_*_VAL`/
  `_*_HOLD`), each independently authored — different topics, different
  sentence structure, different narrative framing, and, for rule-triggering
  content, a different alternative branch of the relevant guard rule's
  regex per split (e.g. `rag-system-override` alone offers eight
  independent trigger phrasings; development/validation/holdout each draw
  from different ones). Query text and filler/padding content that used to
  be literal, split-invariant strings (`"policy fragment {token}"`,
  `"shipping information {token}"`, a single shared filler paragraph for
  the two budget-boundary families) were moved into the same per-split-bank
  pattern — including the filler paragraphs themselves, since a long shared
  filler string dominates a similarity-ratio comparison even when the short
  meaningful portion of the sentence differs.
- **Bugs found and fixed during the rewrite (self-caught, documented
  transparently):** re-running the guard-agreement diagnostic after every
  content change caught several regressions: (a) new split-specific
  sentences using "memo"/"report" where the `this note must override ...`
  rule requires the literal word "note"; (b) a word ("operations")
  inserted between "this" and "note", breaking the rule's `\bthis note\b`
  boundary; (c) two `multi_chunk_coordination`/`fragment_beyond_per_chunk_
  prefix` holdout pairs where one half alone already tripped a per-chunk
  rule, defeating the "coordination" premise (a genuinely coordinated
  attack requires *neither* half to trigger alone); (d) several families'
  query text (not just document content) was still hardcoded identically
  across splits even after the first content-bank pass, caught by the new
  `check_cross_split_contamination` validator check itself, not the guard
  diagnostic — fixed by moving query construction into the same per-split
  pattern for `multi_chunk_coordination`, `fragment_beyond_per_chunk_
  prefix`, `zero_width_whitespace_variant`, `markdown_html_concealment`,
  and `indirect_retrieved_injection`.
- **Tests:** `scripts/validate_v2_benchmark.py::
  check_cross_split_contamination` (new) implements, with pure
  standard-library tools (`unicodedata`, `re`, `difflib.SequenceMatcher`):
  exact normalized-fingerprint equality across every cross-split pair
  (development-vs-validation, development-vs-holdout, validation-vs-
  holdout) for both case queries and corpus documents; a 0.9-threshold
  lexical-similarity check on the same pairs (threshold adopted directly
  from Code X's own audit methodology); and a check that no
  `template_id`/`translation_group_id` value repeats across splits.
  `check_v1_contamination` (new) compares every validation/holdout query
  against every `redteam/prompts.jsonl` v1 prompt at the same threshold
  (development is correctly excluded, per ADR-003). Regression tests in
  `tests/test_benchmark_v2_integrity.py`: `test_shared_template_across_
  splits_is_rejected`, `test_translation_copy_across_splits_is_rejected`,
  `test_superficial_numeric_token_substitution_is_rejected`,
  `test_v1_derived_validation_query_is_rejected`,
  `test_v1_reuse_in_development_is_not_checked`,
  `test_valid_independently_worded_same_family_cases_pass` (negative
  control), plus `test_contamination_exemption_requires_rationale` and
  `test_contamination_exemption_with_rationale_suppresses_the_specific_pair`
  for the exemption mechanism (`datasets/v2/contamination-exemptions.json`,
  currently empty — no exemption was needed after the content fix).
- **Verification against real data:** `test_no_cross_split_contamination_
  in_real_data` and `test_no_v1_contamination_in_real_data` run the same
  check functions against the actual regenerated `datasets/v2/` artifacts
  and assert an empty error list — **0 findings**, down from Code X's
  measured 34/60-holdout + 17/23-family + 1 v1-similarity findings. See
  "Split contamination statistics" below for the executed command output.
- **Residual risk:** the similarity check is lexical (`difflib.
  SequenceMatcher`), not semantic/embedding-based (no new dependency was
  added, per the task's explicit constraint) — a genuine paraphrase sharing
  no lexical substring pattern with another split's content would not be
  caught. Documented in `docs/benchmark-v2-methodology.md` §11 and §15.
- **Status:** RESOLVED.

## Major 1 — Validator completeness

- **Decision:** CONFIRMED and fixed.
- **Verified evidence:** direct read of the pre-fix validator confirmed
  `check_schemas` never validated `expected_final_decision` against the
  real `Decision` enum, never rejected an unknown label field (only
  required fields were checked, not exact field sets), and
  `check_category_coverage` compared families only against whatever was
  present across splits, not against a fixed required list — so removing
  an entire family from every split would report nothing missing. Direct
  read of `check_guard_cross_reference`'s `label_by_id[case_id]` and
  `docs_by_id[doc_id]` lookups confirmed both would raise `KeyError` on,
  respectively, a case with no matching label or a dangling document
  reference — an unhandled crash rather than a validation error.
- **Fix:** `check_schemas` now computes `missing = REQUIRED - keys` **and**
  `extra = keys - REQUIRED` for every corpus/case/label record (catching
  both missing and unknown fields), and separately validates every enum
  field (`expected_final_decision`/`allowed_final_decisions` against
  `Decision`, `language`, `evaluation_scope`, `category`,
  `expected_document_ingestion_status`, `expected_dlp_action`,
  `expected_stop_reason`/`allowed_stop_reasons`) plus basic types (`top_k`
  positive int, `expected_provider_called` bool, `expected_redaction_count`
  non-negative int). `check_family_registry` (renamed from
  `check_category_coverage`) checks split coverage against the fixed
  `REQUIRED_FAMILIES` frozenset (23 names), flagging both a missing
  required family and an unregistered one. `check_case_label_mapping` (new,
  replacing the crash-prone ad-hoc lookup) computes set differences instead
  of dict indexing, so a dangling case/label ID is reported as a normal
  sorted error string. `check_referential_integrity` was already
  `in`-based (safe); confirmed still safe. `_load_jsonl`'s error messages
  were changed to use `_rel(path)` (repository-relative) instead of the
  raw `Path` object, removing the absolute-path leak Code X's audit did
  not explicitly flag but which the "no internal absolute path" requirement
  covers.
- **Tests:** `tests/test_benchmark_v2_integrity.py`:
  `test_schema_check_rejects_invalid_decision_value`,
  `test_schema_check_rejects_unknown_case_field`,
  `test_schema_check_rejects_unknown_label_field`,
  `test_schema_check_rejects_missing_required_case_field`,
  `test_schema_check_rejects_invalid_evaluation_scope`,
  `test_schema_check_rejects_inconsistent_language`,
  `test_missing_required_family_is_rejected`,
  `test_split_consistency_rejects_mismatched_split_field`,
  `test_language_consistency_rejects_case_label_disagreement`,
  `test_dangling_document_reference_is_rejected_without_crashing`,
  `test_mismatched_case_label_mapping_is_rejected_without_crashing`,
  `test_malformed_jsonl_reports_clean_error_not_a_crash`,
  `test_missing_file_reports_relative_path_not_absolute`,
  `test_error_messages_use_relative_paths_not_absolute`,
  `test_cli_main_returns_nonzero_and_prints_no_traceback_on_bad_data`
  (asserts `"Traceback"` is absent from stderr and `"FAIL"` is present, for
  a fully empty/malformed candidate tree pointed at via monkeypatched
  paths).
- **Residual risk:** none identified beyond the general limitation that
  schema validation checks structure and enum membership, not semantic
  correctness of a label's *content* (that remains the optional diagnostic
  and manual authoring judgment's job).
- **Status:** RESOLVED.

## Major 2 — Label isolation and evaluation scope

- **Decision:** CONFIRMED and fixed.
- **Verified evidence:** direct read of the pre-fix `Registry.add_document`
  confirmed every corpus record carried `expected_ingestion_status`
  (`"indexed"`/`"rejected"`) — a ground-truth outcome claim living outside
  `labels/`, which the input/label separation invariant this whole phase is
  built around explicitly prohibits. Confirmed no `evaluation_scope` field
  existed anywhere in the pre-fix case or label schema.
- **Fix:** `expected_ingestion_status` was removed from the corpus record
  entirely; `Registry.add_case` gained an `expected_document_ingestion_
  status` parameter (default `"indexed"`, set to `"rejected"` only by
  `build_provenance_denied_at_ingestion`) that is stored in the **label**
  record instead. `ingestion_mode` (execution-routing metadata — which
  mechanism to attempt ingestion through) was deliberately retained in the
  corpus, since Code X's finding named `expected_ingestion_status`
  specifically as the outcome leak, not `ingestion_mode`. Every case now
  carries a required `evaluation_scope` field validated against
  `{end_to_end, component, availability_fault, residual_risk_only}`:
  `provenance_denied_at_ingestion` → `component` (requires an
  ingestion-then-query workflow, per Code X's own scenario-executability
  note), `availability_failure_case` → `availability_fault` (a policy-error
  setup, not a content check), `fragment_beyond_per_chunk_prefix` →
  `residual_risk_only` (Code X's own words: "effectively a residual-risk
  observation despite carrying an executable expected decision"), and all
  other 20 families → `end_to_end`.
- **Tests:** `tests/test_benchmark_v2_schema.py`:
  `test_corpus_no_longer_carries_expected_ingestion_status`,
  `test_corpus_contains_no_ground_truth_fields`,
  `test_case_files_never_contain_expected_decision_or_outcome_text`,
  `test_every_case_has_a_valid_evaluation_scope`,
  `test_labels_expected_document_ingestion_status_is_valid`; plus the
  general `test_case_files_never_contain_label_fields` (now covering the
  new label-only metadata fields too) and
  `test_schema_check_rejects_is_poisoned_in_corpus`.
- **Residual risk:** Phase 12E's runner design does not exist yet, so
  `evaluation_scope`'s consumption contract (skip `residual_risk_only` from
  detection denominators; use a two-step workflow for `component`; inject a
  policy fault for `availability_fault`) is specified in
  `docs/benchmark-v2-methodology.md` §6a but not yet exercised by running
  code — that is explicitly Phase 12E's job, not Phase 12D's.
- **Status:** RESOLVED.

## Major 3 — Class balance

- **Decision:** CONFIRMED and fixed.
- **Verified evidence:** recomputed the pre-fix corpus's actual category
  counts directly from `datasets/v2/labels/*.jsonl` before starting the fix:
  36 benign / 74 malicious / 6 mixed / 4 neutral (30% benign), matching
  Code X's cited numbers exactly.
- **Fix:** `FAMILY_TABLE` per-family counts were rebalanced to Code X's own
  explicitly preferred distribution (adopted verbatim, since it was already
  reviewed and given as a concrete alternative): development/validation 12
  benign / 12 malicious / 4 mixed / 2 neutral each, holdout 24/24/8/4 —
  totals 48/48/16/8 = 120. No scenario family was removed to hit these
  counts: the 9 benign families were adjusted from a uniform 1/1/2 to a mix
  of 1/1/2 and 2/2/4 (3 families bumped); the 12 malicious families were
  *normalized down* to a uniform 1/1/2 each (previously ranging 1/1/2 to
  2/2/6); the single mixed family
  (`mixed_benign_malicious_retrieval`) was raised to 4/4/8; the single
  neutral family (`availability_failure_case`) was raised to 2/2/4. All 23
  families remain present in every split.
- **Tests:** `scripts/validate_v2_benchmark.py::check_class_distribution`
  (new, gating) enforces the exact per-split, per-category counts above
  (not an "approximately balanced" claim). `tests/test_benchmark_v2_
  integrity.py::test_exact_class_distribution` asserts the real data
  matches exactly.
- **Residual risk:** per-family holdout sample sizes (2–8 cases) remain too
  small for statistically meaningful *per-family* rates even after
  rebalancing — this was Code X's own Minor finding, explicitly
  acknowledged rather than fixed away: `docs/benchmark-v2-methodology.md`
  documents that Phase 12E must report aggregate and `semantic_group_id`
  -grouped metrics (§6a's grouping mechanism), with per-family numbers
  presented as descriptive examples only, never as a claimed statistically
  meaningful rate. See "Statistical reporting limitations" below.
- **Status:** RESOLVED.

## Regenerated artifact counts

Executed in this session, in order:

```
$ python scripts/build_v2_benchmark.py --verify-determinism
Determinism check passed: two in-memory builds are byte-identical.

$ python scripts/build_v2_benchmark.py
Built v2 benchmark (CANDIDATE): 172 documents, 120 cases
(development=30, validation=30, holdout=60).

$ python scripts/validate_v2_benchmark.py
OK: 172 documents, 120 cases across 3 splits, all checks passed
(guard-independent; see --diagnose-current-guards for an optional,
non-gating guard-agreement report).
```

Category distribution (from `datasets/v2/labels/*.jsonl`, recomputed
directly): `{'benign': 48, 'malicious': 48, 'mixed': 16, 'neutral': 8}`.
Language distribution: `{'vi': 60, 'en': 40, 'bilingual': 20}` (unchanged by
this fix pass). `evaluation_scope` distribution: `{'end_to_end': 104,
'component': 4, 'residual_risk_only': 4, 'availability_fault': 8}`.

## Split contamination statistics

Executed directly against the regenerated corpus in this session:

- `check_cross_split_contamination(corpus, cases, labels)` → **0 findings**
  (down from Code X's measured 34/60 holdout queries ≥0.9 similar and 17/23
  families sharing an identical template).
- `check_v1_contamination(cases, corpus)` → **0 findings** (down from 1 —
  `V2-VAL-0007` at 0.929 similarity to v1's `RT-INJ-DIRECT-001`; that
  specific case's content no longer exists in this form after the content-
  bank rewrite).
- `check_no_cross_split_secret_reuse(corpus, cases)` → **0 findings**
  (unchanged; this check already passed pre-fix).

Both new checks are gating (part of `validate_v2_benchmark.py`'s default,
guard-independent `main()` path) and are re-run automatically on every
future `python scripts/validate_v2_benchmark.py` invocation.

## Guard-independence proof

Executed directly in this session:

```
$ python -c "... flip a direct_injection label's expected_final_decision
to 'allow' (disagreeing with the real Input Guard's BLOCK decision) and
re-run validate_v2_benchmark.py's main() against the mutated in-memory
data ..."
exit code: 0
```

Confirms the exact scenario Code X's Critical #1 probe described: a
structurally valid label that disagrees with the current Input Guard now
passes integrity validation, because the default validation path never
consults the guard at all. `--diagnose-current-guards` run separately
against the real, unmutated files reports `44 agree, 0 disagree` for
development+validation and `88 agree, 0 disagree` including holdout —
confirming the real, unmutated labels do currently agree with the real
guards (a bonus consistency signal, not a gate).

## Schema and validator contract

Case schema (runtime, execution-only): `case_id, split, scenario_family,
language, query, top_k, relevant_document_ids, evaluation_scope`. Label
schema (ground truth + non-runtime authoring metadata): `case_id,
scenario_family, language, template_id, semantic_group_id,
translation_group_id, authoring_set, expected_document_ingestion_status,
category, attack_family, expected_final_decision, allowed_final_decisions,
expected_stop_reason, allowed_stop_reasons, expected_provider_called,
expected_retrieval_behavior, expected_context_behavior,
expected_dlp_action, expected_redaction_categories,
expected_redaction_count, expected_security_property, rationale,
residual_risk`. Corpus schema: `document_id, external_id, source_key,
ingestion_mode, title, content, metadata, language, scenario_family` (no
ground-truth field). All three are exact-field-set validated (unknown
fields rejected) with full enum coverage, as described under Major 1 above.

## Candidate manifest

`scripts/freeze_v2_benchmark.py` now writes `"manifest_status": "candidate"`
into the manifest itself and every CLI message (`freeze`, `verify`) says
CANDIDATE explicitly (`tests/test_benchmark_v2_freeze.py::
test_manifest_is_explicitly_labeled_candidate`,
`test_freeze_cli_output_says_candidate`,
`test_verify_cli_output_says_candidate`). Executed in this session:

```
$ python scripts/freeze_v2_benchmark.py freeze
Froze 7 artifact file(s) into .../benchmark-v2-manifest.json
(CANDIDATE FREEZE -- not yet final).

$ python scripts/freeze_v2_benchmark.py verify
OK: 7 file(s) verified against the frozen CANDIDATE manifest, no drift detected.
```

Mutation-then-rebuild round trip (via `tests/test_benchmark_v2_freeze.py`,
against a `tmp_path` copy, never the real committed manifest): freeze →
mutate a copy → verify fails with a reported content/size mismatch →
restore original content → verify passes again. All passed. This manifest
is not a defensible final freeze; it becomes one only after Code X,
Gemini, and Grok all pass and a final regeneration is performed after all
accepted fixes across every audit.

## Statistical reporting limitations

Even after rebalancing (Major 3), individual scenario families have only
2–8 holdout cases — too few for a statistically meaningful standalone
per-family detection/false-positive rate. `docs/benchmark-v2-methodology.md`
§6a's `semantic_group_id` label field (six groups:
`benign_baseline`, `instruction_override`, `obfuscation`, `leakage`,
`provenance`, `availability`) exists specifically so a future Phase 12E
report can aggregate across a semantically related group of families where
individual family counts are too small, while still reporting per-family
numbers as descriptive examples, never as a claimed statistically
meaningful rate. This is documented as a permanent, acknowledged limitation
of a 120-case benchmark spread across 23 families, not something a further
count adjustment inside Phase 12D could fully resolve without either
inflating total size well beyond ADR-003's floor or reducing family-taxonomy
breadth — Code X's own audit reached the same conclusion ("insufficient for
reliable per-family rates").

## Acceptance gate

Full validation executed in this session after all fixes:

- Benchmark build twice + byte-for-byte in-memory compare: **PASS**.
- `scripts/validate_v2_benchmark.py` (default, guard-independent): **PASS**,
  0 errors.
- `scripts/validate_v2_benchmark.py --diagnose-current-guards
  --include-holdout-diagnostic`: **PASS** (non-gating), 88 agree / 0
  disagree.
- `scripts/freeze_v2_benchmark.py freeze` + `verify`: **PASS**.
- Mutation-then-rebuild-restores round trip: **PASS**.
- Focused Phase 12D suite (`test_benchmark_v2_schema.py`,
  `test_benchmark_v2_integrity.py`, `test_benchmark_v2_freeze.py`):
  **92 passed**.
- Full repository suite (excluding the 38 TestClient-blocked tests across 7
  files, a pre-existing shared-environment `httpx`/`httpx2` limitation
  unrelated to this phase — see `TASK_BOARD.md`'s Environment security
  observation note): **338 passed**, 0 failed, 0 regressions in any
  previously passing test.
- `python -m py_compile` on every changed file: **clean**.
- `git diff --check`: **clean**. `git status --short`: change set confined
  to `datasets/v2/`, the three scripts, the three test files, this document,
  and the documentation files listed in the final response — no file under
  `app/guards/`, `app/services/rag_query.py`, `app/services/gateway.py`,
  `app/services/llm_provider.py`, `app/retrieval/`, `app/api/routes.py`, the
  frozen v1 benchmark, or `requirements.txt` was touched.
- No tracked `.db`/`.sqlite`/`.sqlite3` file. No new dependency
  (`requirements.txt` diff empty). No network-call import in any of the
  three scripts (grep-verified). No `datasets/v2`/`benchmark-v2` reference
  under `app/` (grep-verified). No Phase 12E artifact (evaluation result,
  ASR/FPR/FNR number, ablation output) produced.

**Final recommendation (round 1): READY FOR CODE X RE-AUDIT.**

Not APPROVE. Not DONE. Phase 12D remains **IN REVIEW** per this task's
explicit instruction — it does not close until maintainer verification,
GitHub Copilot working-tree review, this Code X re-audit, Gemini Pro
academic methodology review, and Grok red-team coverage review all pass.
Gemini and Grok review the committed candidate only after this Code X
re-audit's technical blockers are confirmed resolved.

---

# Phase 12D Code X Re-Audit Resolution (Round 2)

## Reviewed audit

A second independent Code X technical re-audit of the round-1 fix above,
same branch (`phase-12d-v2-benchmark`), same reviewed HEAD
(`94f7bdefe166087a4edb6723558b888d7d062a06` — the working tree, uncommitted,
as with round 1). Verdict: **REVISE**, with 2 Critical + 1 Major finding
still open plus 2 additional Major findings raised for the first time
against round 1's own fixes:

- Critical 1 (guard independence): **RESOLVED** in round 1, reconfirmed
  unaffected by round 2's changes.
- Critical 2 (split independence): **PARTIALLY RESOLVED** in round 1 — the
  raw-text fingerprint/similarity mechanism was fixed, but a structurally
  identical EN/VI translation using two different self-declared
  `translation_group_id` values could still pass, since nothing checked
  whether the two IDs' underlying content was actually independent.
- Major 1 (validator completeness): **PARTIALLY RESOLVED** in round 1 — a
  duplicate/non-string `external_id`, a non-string `query`, and (most
  seriously) a non-string corpus `content` value (which crashed
  `check_no_cross_split_secret_reuse`'s `.finditer(content)` call with an
  unhandled `TypeError`) all still passed or crashed.
- New finding: `check_v1_contamination` accepted a `corpus` parameter but
  never read it — v1-reuse scanning covered queries only, so a v1 prompt
  copied verbatim into a validation/holdout corpus document would pass.
- New finding: the candidate manifest did not cover
  `contamination-exemptions.json`, a file that can change validation
  *policy* (which findings are suppressed), leaving it outside the
  integrity boundary the manifest is supposed to establish.
- Major 2 (label isolation/scope): **RESOLVED**, reconfirmed unaffected.
- Major 3 (class balance): **RESOLVED**, reconfirmed unaffected.

This section resolves round 2's findings only, per this task's explicit
scope. It does not restate or re-verify round 1's already-resolved
findings above beyond a brief reconfirmation.

## Evidence hierarchy

Unchanged from round 1: (1) executed command output in this session,
(2) direct source reads cross-checked against the real guard regexes where
relevant, (3) ad-hoc verification scripts run and inspected during
implementation, (4) the audit text itself, used only to state what was
found, never as a substitute for independent re-verification.

## Critical 2 (continued) — Split independence: translation contamination

- **Decision:** CONFIRMED and fixed.
- **Verified evidence:** constructed the exact scenario directly —
  `"What is the annual leave policy for full-time employees?"` in
  development and `"Chính sách nghỉ phép hàng năm cho nhân viên toàn thời
  gian là gì?"` (an honest Vietnamese translation of the same sentence) in
  holdout. Round 1's `check_cross_split_contamination` fingerprint/
  similarity check reported **zero findings** for this pair, since a
  translation shares almost no literal substring with its source language
  — confirming the gap exactly as described.
- **Fix:** two complementary, standard-library-only controls, detailed in
  `docs/benchmark-v2-methodology.md` §10a:
  - **Authoring provenance** (`datasets/v2/design/authoring-
    provenance.jsonl`, generated by `Registry._add_provenance` in
    `scripts/build_v2_benchmark.py`, cross-checked by
    `check_authoring_provenance` in `scripts/validate_v2_benchmark.py`):
    one record per query/document with a `semantic_group_id` and
    `translation_group_id` that are constructed to embed `(family, split)`
    (and `bank_index` for the latter), so neither can ever collide across
    splits *by construction*; the validator independently re-derives this
    from the committed file and additionally verifies each record's
    `normalized_text_hash` against the real, current artifact text using
    `build_v2_benchmark.normalized_text_hash` (the exact function that
    generated it), catching a missing, duplicate, or dishonest/stale hash
    mapping.
  - **Benchmark-specific bilingual canonicalization**
    (`check_bilingual_contamination`): a reviewed ~40-entry EN/VI phrase
    lexicon (`BILINGUAL_LEXICON`), matched longest-phrase-first with
    collision-free numeric substitution tokens (`@C<n>@`, not
    semantically-named tokens — see "Bugs found" below), compared
    cross-split by both `difflib.SequenceMatcher` ratio and token-Jaccard
    overlap (the latter specifically to catch clause-reordered
    translations, since reordering lowers a sequence ratio but not a set
    overlap).
- **Bugs found and fixed while building this control (self-caught before
  finalizing):** (1) the first lexicon draft used semantically-named
  tokens (e.g. `@leavepolicyfull@`), which themselves contained plain
  English words that a later, shorter lexicon entry's phrase text (e.g.
  `"policy"`) could then re-match and corrupt — fixed by switching to
  collision-free numeric tokens (`@C0@`, `@C1@`, ...); (2) trailing
  sentence punctuation (`?`) stuck directly to a substituted token,
  producing e.g. `"@whatis@?"` vs `"@whatis@"` and silently breaking
  token-level Jaccard comparison — fixed by stripping punctuation before
  substitution; (3) shorter lexicon entries were applied before longer,
  more specific ones in some orderings, fragmenting a multi-word phrase
  match — fixed by always matching longest-phrase-first
  (`_BILINGUAL_LEXICON_BY_LENGTH`).
- **Tests:** `tests/test_benchmark_v2_integrity.py` --
  `test_exact_translation_across_splits_with_distinct_ids_fails` (required
  #1), `test_clause_reordered_translation_fails_when_lexicon_covers_it`
  (required #2), `test_shared_semantic_group_id_across_splits_in_
  provenance_is_rejected` (required #3), `test_shared_translation_group_
  id_across_splits_in_provenance_is_rejected` (required #4),
  `test_incorrect_provenance_text_hash_is_rejected` (required #5),
  `test_missing_provenance_entry_is_rejected` (required #6),
  `test_independently_authored_en_vi_same_family_cases_pass` (required
  #7), `test_bilingual_exemption_without_rationale_fails` (required #8);
  plus `test_duplicate_provenance_artifact_id_is_rejected`,
  `test_provenance_wrong_artifact_type_is_rejected`,
  `test_authoring_provenance_covers_every_real_query_and_document`,
  `test_no_orphan_documents_in_real_data`.
- **Residual risk:** documented explicitly, not hidden — a reordering that
  splits a *single* lexicon phrase apart (rather than reordering whole
  clauses) is not caught, since the phrase then fails to match its
  lexicon entry at all; this was observed directly while building the
  required test fixtures (an earlier fixture using this exact pattern
  failed to trigger and had to be redesigned as a clause-level, not
  word-level, reordering). A translation using phrasing outside the
  ~40-entry lexicon is not guaranteed to be caught. This is a
  benchmark-specific lexical/provenance control, explicitly not a general
  semantic-duplicate detector — see `docs/benchmark-v2-methodology.md`
  §10a and §15.
- **Status:** RESOLVED (within the documented, tested boundary above).

## Major 1 (continued) — Complete field-type validation

- **Decision:** CONFIRMED and fixed.
- **Verified evidence:** constructed a corpus record with `content: 12345`
  (an int) directly and ran `check_no_cross_split_secret_reuse` against
  it before the fix — reproduced the unhandled `TypeError` from
  `_SECRET_LIKE_PATTERN.finditer(content)` exactly as described.
  Constructed a corpus with two documents sharing the same `external_id`
  and confirmed the pre-fix validator reported no error.
- **Fix:** `check_schemas` now validates, for every corpus/case/label
  field: `document_id`/`external_id`/`source_key`/`case_id`/`query`/
  `rationale` as non-empty strings (`_require_nonempty_str`); `title`/
  `content` as strings (not merely present); `metadata` as a `dict` whose
  contents are recursively JSON-safe (`_is_json_safe_value` — string keys
  only, no `NaN`/`Infinity`, depth-bounded); `ingestion_mode` against an
  explicit enum; `top_k` bounded to a documented `[1, 50]` range (not
  merely "positive"), still rejecting bool/float; `relevant_document_ids`
  elements individually type-checked as strings; label
  `allowed_final_decisions`/`allowed_stop_reasons`/`expected_redaction_
  categories` as lists (not merely present); `expected_provider_called`
  as bool; `expected_redaction_count` bounded `[0, 100]`;
  `scenario_family` (on all three record types) checked against
  `REQUIRED_FAMILIES`. A new `check_no_duplicate_external_ids` enforces
  `external_id` uniqueness across the corpus. The two content-scanning
  checks that previously crashed on non-string `content`
  (`check_no_cross_split_secret_reuse`, and the cross-split-contamination
  query/document loops) were made independently defensive
  (`isinstance(..., str)` guards), so they degrade to "skip this
  already-reported record" rather than ever raising, even if a future
  check is added that also touches `content` before `check_schemas` has
  had a chance to report it.
- **Tests:** `tests/test_benchmark_v2_integrity.py`, "Major #1 -- complete
  field-type validation" section: `test_duplicate_external_id_is_rejected`,
  `test_no_duplicate_external_ids_in_real_data`,
  `test_non_string_external_id_is_rejected`,
  `test_non_string_document_id_is_rejected`,
  `test_non_string_content_is_rejected_not_crashed` (asserts both the
  clean error message and that the downstream secret-reuse check no
  longer crashes on the same input), `test_non_dict_metadata_is_rejected`,
  `test_invalid_nested_metadata_is_rejected` (non-string key, NaN,
  Infinity -- three sub-cases), `test_non_string_query_is_rejected`,
  `test_bool_top_k_is_rejected`, `test_float_top_k_is_rejected`,
  `test_out_of_bounds_top_k_is_rejected`,
  `test_non_list_relevant_document_ids_is_rejected`,
  `test_non_string_document_reference_entry_is_rejected`,
  `test_invalid_label_scalar_and_list_types_are_rejected` (four
  sub-cases), `test_malformed_dlp_redaction_count_range_is_rejected` (two
  sub-cases), `test_cli_safe_failure_on_non_string_content_no_traceback`
  (constructs a full malformed candidate tree via monkeypatched paths,
  runs `main()`, asserts exit 1 with neither `"Traceback"` nor
  `"TypeError"` in stderr).
- **Residual risk:** none identified for the specific defects Code X
  named. Field-type validation is now complete for every field in the
  documented schema; a field added to the schema in the future without a
  corresponding type check would not be automatically covered (this is a
  process risk, not a code defect).
- **Status:** RESOLVED.

## New finding — v1 contamination must include corpus documents

- **Decision:** CONFIRMED and fixed.
- **Verified evidence:** direct read of round 1's `check_v1_contamination`
  confirmed its signature accepted `corpus: list[dict]` but the function
  body never referenced the parameter at all — only `cases` (queries) were
  scanned. Constructed a corpus document whose `content` was set to a
  verbatim `redteam/prompts.jsonl` prompt, referenced it from a holdout
  case, and confirmed the pre-fix function reported no error despite the
  verbatim v1 copy.
- **Fix:** `find_v1_contamination_matches` (new) scans both validation/
  holdout queries *and* every corpus document referenced by a validation/
  holdout case, returning `(kind, artifact_id, split, v1_id, ratio)`
  tuples so query and document statistics can be reported separately.
  `check_v1_contamination` wraps it into the existing error-message
  format. `check_no_orphan_documents` (new) independently verifies every
  corpus document is referenced by at least one case — this is what
  makes "every referenced document" equivalent to "the whole corpus," so
  an unreferenced document cannot be used to smuggle v1 content past the
  scan. Error messages use only safe artifact IDs (`case_id`/
  `document_id`), never the raw matched text.
- **Tests:** `tests/test_benchmark_v2_integrity.py`:
  `test_v1_prompt_copied_into_validation_query_fails` (required #1),
  `test_v1_prompt_copied_into_holdout_query_fails` (required #2),
  `test_v1_prompt_copied_into_validation_corpus_content_fails` (required
  #3), `test_v1_prompt_copied_into_holdout_corpus_content_fails` (required
  #4), `test_v1_prompt_in_unreferenced_document_is_rejected_by_orphan_
  check` (required #5 -- this benchmark's chosen policy is *prevention*:
  no unreferenced document can exist at all, verified via `check_no_
  orphan_documents`, rather than attempting to scan for one),
  `test_clean_independently_authored_content_passes_v1_check` (required
  #6), plus `test_no_v1_document_contamination_in_real_data` and
  `test_v1_error_messages_never_contain_raw_matched_text`.
- **Residual risk:** none identified. Document titles are not separately
  scanned against v1 (only `content`) -- titles in this benchmark are
  short generated labels (e.g. `"Suspicious policy note {token}"`), never
  copied from any source, so this was judged unnecessary rather than
  overlooked; noted here for transparency rather than silently narrowing
  scope.
- **Status:** RESOLVED.

## New finding — Candidate manifest must cover policy-bearing artifacts

- **Decision:** CONFIRMED and fixed.
- **Verified evidence:** direct read of round 1's
  `scripts/freeze_v2_benchmark.py::ARTIFACT_SUBDIRS = ("corpus", "cases",
  "labels")` confirmed `contamination-exemptions.json` (a top-level file,
  not inside any of those three subdirectories) was never hashed. Mutated
  the exemptions file in a `tmp_path` copy and confirmed `verify` reported
  no error before the fix.
- **Fix:** `ARTIFACT_SUBDIRS` extended to include `design/` (covering the
  new `authoring-provenance.jsonl`); a new `POLICY_FILES = ("contamination-
  exemptions.json",)` covers the one top-level policy file.
  `_iter_artifact_files` now returns all 9 files. The manifest itself
  (`manifests/`) remains excluded from its own hash set, as before.
- **Tests:** `tests/test_benchmark_v2_freeze.py`:
  `test_exemption_file_mutation_fails_verification` (required #1),
  `test_authoring_provenance_mutation_fails_verification` (required #2),
  `test_missing_policy_bearing_file_fails_verification` (required #3),
  `test_unexpected_new_policy_bearing_file_fails_verification` (required
  #4), `test_deterministic_rebuild_restores_candidate_verification_with_
  policy_artifacts` (required #5), plus
  `test_manifest_scope_includes_policy_artifacts` and an update to the
  pre-existing `test_manifest_covers_exactly_the_real_artifact_files` to
  include the two new artifact kinds.
- **Residual risk:** none identified.
- **Status:** RESOLVED.

## Regenerated artifact counts (round 2)

```
$ python scripts/build_v2_benchmark.py --verify-determinism
Determinism check passed: two in-memory builds are byte-identical.

$ python scripts/build_v2_benchmark.py
Built v2 benchmark (CANDIDATE): 172 documents, 120 cases
(development=30, validation=30, holdout=60).

$ python scripts/validate_v2_benchmark.py
OK: 172 documents, 120 cases across 3 splits, all checks passed
(guard-independent; see --diagnose-current-guards for an optional,
non-gating guard-agreement report).
```

Document/case/split counts, category balance, and language distribution
are **unchanged** from round 1 (172 documents; 120 cases, 30/30/60;
48/48/16/8 category balance; 60/40/20 vi/en/bilingual) -- this fix pass
did not touch content generation logic, only added the provenance/
bilingual/type-validation/manifest-scope controls around it, per this
task's explicit instruction not to change the case count/split/class
balance unless truly required.

## Updated similarity/contamination statistics

Computed directly against the regenerated corpus in this session (see
`docs/benchmark-v2-methodology.md` §11a for the same table in context):

| Metric | Value |
|---|---|
| Document count | 172 |
| Case split count | development=30, validation=30, holdout=60 (120 total) |
| Language distribution | vi=60, en=40, bilingual=20 |
| Class distribution | benign=48, malicious=48, mixed=16, neutral=8 |
| `evaluation_scope` distribution | end_to_end=104, component=4, availability_fault=8, residual_risk_only=4 |
| Maximum cross-split query similarity (any pair) | 0.7213 |
| Median of each holdout query's max similarity to dev/val | 0.4589 |
| Cross-split document similarity findings (>= 0.9 threshold) | 0 |
| Bilingual/translation contamination findings | 0 |
| Semantic-group-id cross-split reuse count | 0 |
| Translation-group-id cross-split reuse count | 0 |
| v1 query contamination count | 0 |
| v1 document contamination count | 0 |
| Active contamination exemptions | 0 |

## Guard-independence proof (reconfirmed unaffected)

Re-ran the same guard-independence probe as round 1 (flip a
`direct_injection` label's `expected_final_decision` to `"allow"`,
disagreeing with the real Input Guard's BLOCK decision) against the
current, round-2 codebase: `validate_v2_benchmark.main([])` on the
mutated in-memory data still returns 0. `--diagnose-current-guards
--include-holdout-diagnostic` against the real, unmutated files reports
`88 agree, 0 disagree`. Neither result changed from round 1, confirming
round 2's changes did not reintroduce guard-dependence.

## Candidate manifest (round 2)

```
$ python scripts/freeze_v2_benchmark.py freeze
Froze 9 artifact file(s) into .../benchmark-v2-manifest.json
(CANDIDATE FREEZE -- not yet final).

$ python scripts/freeze_v2_benchmark.py verify
OK: 9 file(s) verified against the frozen CANDIDATE manifest, no drift detected.
```

Mutation-then-restore round trip executed for **all five** artifact
kinds in this session (corpus, cases, labels, contamination-exemptions.json,
authoring-provenance.jsonl): each mutation independently caused `verify`
to fail with a correctly-identified path, and restoring the original
content made `verify` pass again for every one. Manifest file count is 9
(up from 7 in round 1's candidate).

## Acceptance gate (round 2)

- Benchmark build twice + byte-for-byte in-memory compare (including
  provenance): **PASS**.
- `scripts/validate_v2_benchmark.py` (default, guard-independent):
  **PASS**, 0 errors.
- `scripts/validate_v2_benchmark.py --diagnose-current-guards
  --include-holdout-diagnostic`: **PASS** (non-gating), 88 agree / 0
  disagree.
- `scripts/freeze_v2_benchmark.py freeze` + `verify`: **PASS**.
- Mutation-then-restore round trip for all 5 artifact kinds: **PASS**.
- Focused Phase 12D suite after the resumed completion hardening:
  **161 passed**.
- Full repository suite using the project `.venv`, with no ignored modules:
  **484 passed, 1 warning**. This supersedes the inherited partial command
  that omitted seven TestClient modules; no TestClient test failed.
- `python -m py_compile` on every changed file: **clean**.
- `git diff --check`: **clean**. `git status --short`: change set confined
  to `datasets/v2/`, the three scripts, the three test files, this
  document, and the documentation files listed in the final response — no
  file under `app/guards/`, `app/services/rag_query.py`,
  `app/services/gateway.py`, `app/services/llm_provider.py`,
  `app/retrieval/`, `app/api/routes.py`, the frozen v1 benchmark, or
  `requirements.txt` was touched.
- No tracked `.db`/`.sqlite`/`.sqlite3` file. No new dependency
  (`requirements.txt` diff empty; the bilingual/provenance controls use
  only `unicodedata`, `re`, `difflib`, `hashlib`, `math` -- all standard
  library, and `validate_v2_benchmark.py` importing `build_v2_benchmark.py`
  is a same-directory script import, not a new dependency). No
  network-call import in any of the three scripts (grep-verified). No
  `datasets/v2`/`benchmark-v2` reference under `app/` (grep-verified). No
  Phase 12E artifact produced.

**Final recommendation (round 2 continuation): READY FOR TECHNICAL READ-ONLY VERIFICATION.**

Not APPROVE. Not DONE. Phase 12D remains **IN REVIEW**. A clean independent
Code X verification is required before Gemini and Grok review the candidate.

## Resumed completion verification

The inherited implementation session ended before a complete, unignored
validation run. The continuation independently reviewed the working tree and
added three final defensive improvements:

- `check_schemas` is now a hard preflight, so malformed values never reach
  normalization, similarity, reference, or provenance logic.
- `check_authoring_provenance` now validates its exact schema, rejects unknown
  artifact records, cross-checks split/language/family/authoring-set identity
  against the real case or document, and verifies bilingual query-document
  translation-group linkage in addition to hash and cross-split checks.
- `freeze_v2_benchmark.py freeze` now refuses to create a candidate manifest
  when either required policy-bearing artifact is missing.

Executed evidence from this continuation:

- focused Phase 12D suite: **161 passed**;
- full repository suite, no ignored modules: **484 passed, 1 warning**;
- Python compile checks: clean;
- two external clean builds: identical 9-file path sets and bytes;
- default guard-independent validator: pass;
- optional diagnostic: 44 agree, 0 disagree over development/validation;
- candidate freeze and verify: 9 files, pass;
- corpus, case, label, exemption, and provenance mutations: each rejected;
- missing policy artifact: both verify and fresh freeze rejected;
- unexpected frozen-scope file: rejected;
- deterministic rebuild: restored successful verification.

Current measured integrity statistics are: maximum cross-split query
similarity `0.7213`, median maximum holdout similarity `0.4589`, zero query
or document pairs at/above `0.9`, zero benchmark-specific translation
findings, zero cross-split provenance group reuse, zero v1 query/document
matches, and zero active exemptions.

---

# Phase 12D Code X Re-Audit Resolution (Round 3)

## Reviewed audit

A third independent Code X technical re-audit, same branch
(`phase-12d-v2-benchmark`), same reviewed HEAD
(`94f7bdefe166087a4edb6723558b888d7d062a06` — the working tree, uncommitted,
as with rounds 1–2). **Final malformed-value verification verdict:
REVISE.** This round found that, despite round 2's Major #1 (continued)
fix covering non-string *scalar* values (an int `content`, a bool `top_k`),
neither `check_schemas` nor `check_authoring_provenance` had ever been
exercised against a **list or dict** value in a position that is directly
used as a `set`/`dict` membership or key operand — `expected_stop_reason:
[]` on a label, and `split: []` on an authoring-provenance entry, both
raised an unhandled `TypeError: unhashable type: 'list'` instead of a
clean validation error:

- Authoring provenance (round 2's translation-contamination control):
  **PARTIALLY RESOLVED** — the hash/group-reuse logic itself was correct,
  but per-entry field validation (`split`, `authoring_set`, `artifact_type`,
  `language`, `scenario_family`) performed `value not in ALLOWED_SET`
  directly, with no type check first.
- Schema/type validation (round 2's Major #1 continued fix): **NOT
  RESOLVED** for the list/dict/bool-adjacent case — the round 2 fix
  covered non-string scalars (`content=12345`, `top_k=True`) but every
  enum-membership check elsewhere in `check_schemas` (`expected_stop_
  reason`, `allowed_stop_reasons`, `category`, `expected_final_decision`,
  `expected_dlp_action`, `expected_document_ingestion_status`, `language`,
  `scenario_family`, `evaluation_scope`, `ingestion_mode`, `split`) still
  performed a bare `value in ALLOWED_SET`/`value not in ALLOWED_SET` test
  with no preceding `isinstance` check, so a list or dict value in any of
  those fields crashed the same way.

**Root cause:** Python's `set`/`dict` membership and key operations
(`in`, `not in`, `dict[key]`, `dict.get(key)`, `set.add(value)`,
`Counter.update(...)`) all call `hash(value)` on the operand before doing
anything else. A `list` or `dict` value is unhashable, so `value in
ALLOWED_SET` raises `TypeError: unhashable type: 'list'` (or `'dict'`)
immediately — before the membership test itself ever runs. Round 2's
Major #1 fix checked several fields for the right *value* but never
inserted an `isinstance(value, str)` gate *before* the `in` test for
every enum field; a scalar like `12345` or `True` is hashable (so it
reached the membership test and was correctly reported as "not a member
of the enum"), while a `list`/`dict` value is not hashable and crashed
before that message could ever be produced. This is why the round 2 fix
appeared complete against its own test matrix (which used only scalar
malformed values) while this exact class of crash remained live and
unexercised.

**Why the requested fix was absent from the previous working tree:**
round 2's fix pass was scoped and verified against a malformed-value test
matrix built entirely from non-list/non-dict scalars (`12345`, `True`,
`5.0`, `"not-a-list"`, `999`) — every one of those is hashable, so every
one of them was correctly caught by a bare `in`/`not in` test and no crash
was ever observed during that round's own testing. The unhashable case
(`[]`, `{}`) was never constructed as a test input in round 1 or round 2,
so the gap was never exercised until this round's explicit malformed-value
probe.

## Evidence hierarchy

Unchanged from rounds 1–2: (1) executed command output in this session,
(2) direct source reads, (3) ad-hoc verification scripts run and inspected
during implementation, (4) the audit text itself, used only to state what
was found, never as a substitute for independent re-verification.

## Unsafe operations found (exhaustive sweep)

A full read of `scripts/validate_v2_benchmark.py` plus a grep for every
`in ALLOWED_SET`, `not in ALLOWED_SET`, `dict[key]`, `dict.get(key)`,
`.setdefault(key, ...)`, `set.add(value)`, and `Counter(...)` construction
found ~20 unsafe sites across 15 functions, all sharing the same shape —
a value taken from an untrusted JSONL record used directly as a hash
operand with no prior type check:

`check_schemas` (every enum field), `check_authoring_provenance` (every
enum field: `artifact_type`, `split`, `language`, `scenario_family`,
`authoring_set`), `check_referential_integrity` (`doc_ids` set
construction and lookup), `check_family_registry` (`present` set),
`check_language_coverage` (`all_langs` set), `check_class_distribution`
(`Counter` over `category`), `check_case_label_mapping` (`case_ids`/
`label_ids` set construction), `check_no_duplicate_ids` (`seen_docs`/
`seen_cases` dict-key insertion), `check_cross_split_contamination`
(`doc_split`/`doc_by_id` dict-key insertion), `find_v1_contamination_
matches` (`case_id`/`doc_id` used as dict keys), `check_no_orphan_
documents` (`referenced` set), `check_no_cross_split_secret_reuse`
(`doc_split`/`value_to_docs` dict-key insertion),
`check_split_and_language_consistency` (`label_by_id` dict-key
insertion), `check_source_keys` (`KNOWN_SOURCE_KEYS` membership test),
`_exemption_errors`/`_is_exempt` (exemption-pair matching),
`diagnose_against_current_guards` (`docs_by_id`/`label_by_id` dict
construction, non-gating but still must not crash).

## Fix — type-first validation helpers

Eight reusable, crash-proof helpers were added to
`scripts/validate_v2_benchmark.py` (all documented in-module as "the
PRIMARY fix"): `is_non_empty_string`, `safe_record_identifier`,
`validate_string_field`, `validate_string_enum`,
`validate_optional_string_enum`, `validate_string_list`,
`validate_integer_field`, `validate_json_safe_value` (the public alias
for the existing `_is_json_safe_value`), plus two internal primitives
`_hashable`/`_safe_in` used as a defense-in-depth guard in functions that
can be called directly (e.g. from tests) without first passing through
`check_schemas`'s own gate. Every helper confirms the Python type of its
input **before** any membership test, `.strip()`/`.lower()` call, dict-key
insertion, or hashing — a list, dict, number, bool, or unexpected `None`
is always turned into one clean, appended error string, never an
unhandled exception. `validate_integer_field` explicitly rejects `bool`
even though `isinstance(True, int)` is `True` in Python (`bool` is an
`int` subclass), since a boolean is never a semantically valid `top_k`/
redaction-count value. `validate_string_list` validates every element's
type individually, before any per-element enum check, and reports the
offending index (`field[i]`) rather than crashing on the first
unhashable element.

## Validation-order refactor

`check_schemas` was rewritten field-by-field to call these helpers in a
strict order for every corpus/case/label record: (1) confirm the record
itself is a `dict`, (2) exact field-set diff (missing/unexpected/
prohibited/leaked fields), (3–4) per-field type validation via
`validate_string_field`/`validate_integer_field`/`validate_string_list`,
(5) non-empty-string constraints (folded into the same helper call),
(6) enum membership — always as the *second* step of
`validate_string_enum`, never reachable until the type check inside the
same call has already passed, (7) uniqueness/duplicate-ID checks run in
separate, later functions that themselves only build sets/dicts from
values pre-filtered by `isinstance(..., str)`, (8) referential integrity
(`check_referential_integrity`) uses the new `_safe_in` helper for the
membership test, (9) provenance identity/hash checks
(`check_authoring_provenance`) apply the same type-first pattern before
any cross-record comparison, (10) contamination/grouping/similarity
checks are downstream of all of the above. Malformed records are **not**
universally skipped by downstream checks: malformed provenance records
may continue through safe downstream validation to aggregate
deterministic field and consistency errors. What is guaranteed is that
hashing, membership, grouping, normalization, and dictionary-key
operations consume only type-validated or safely guarded values — every
downstream function was audited and given its own local
`isinstance`/`_safe_in` guard so that it remains individually crash-proof
even if called directly (as the test suite's negative-path tests do),
not only when reached through `main()`'s `check_schemas` gate. This is
deliberate: processing a partially malformed record through guarded
comparisons can intentionally produce several deterministic cascading
validation errors (see the 22-error `split=[]` probe below), and never a
traceback, `TypeError`, `KeyError`, raw-content disclosure, or
absolute-path disclosure.

## Corpus/case/label/provenance/exemption hardening

Every corpus field (`document_id`, `external_id`, `source_key`,
`ingestion_mode`, `title`, `content`, `metadata`, `language`,
`scenario_family`), case field (`case_id`, `split`, `scenario_family`,
`language`, `query`, `top_k`, `relevant_document_ids`,
`evaluation_scope`), and label field (`case_id`, `scenario_family`,
`language`, `authoring_set`, `template_id`, `semantic_group_id`,
`translation_group_id`, `expected_final_decision`,
`allowed_final_decisions`, `expected_stop_reason`,
`allowed_stop_reasons`, `category`, `attack_family`,
`expected_document_ingestion_status`, `expected_dlp_action`,
`expected_redaction_categories`, `expected_provider_called`,
`expected_redaction_count`, `expected_retrieval_behavior`,
`expected_context_behavior`, `expected_security_property`,
`residual_risk`, `rationale`) now goes through a type-first helper call
in `check_schemas`. `check_authoring_provenance`'s per-entry loop applies
the same pattern to `artifact_type`, `split`, `language`,
`scenario_family`, `authoring_set` (with the `authoring_set == split`
cross-field consistency check now gated behind both fields' own type
validation passing first) and `validate_string_field` for
`semantic_group_id`, `translation_group_id`, `normalized_text_hash`
(with the 64-hex-char format check gated behind the type check). A
non-dict provenance record is rejected with a dedicated "non-object
record" error and skipped entirely — never reaches `.get()`. Provenance
records with a usable string `artifact_id` may be indexed into
`by_artifact_id` for deterministic identity and duplicate reporting
**before** all remaining fields are validated — insertion is gated only
on the `artifact_id` type check, not on full-record validity. This is
fail-safe rather than fully exclusionary: all later provenance
comparisons, grouping, and hash operations are type-guarded, so a
malformed field on an indexed record cannot enter an unsafe
hash-dependent operation; it instead surfaces as one or more
deterministic validation errors. Invalid records are neither fully
accepted nor all excluded from `by_artifact_id`. The current committed
artifacts have exactly one valid provenance record per artifact, so this
indexing behavior changes nothing about the real candidate's result.
`_exemption_errors`/`_is_exempt` were rewritten identically:
`rationale`/`scope`/`id_a`/`id_b` are type-checked before any `.strip()`
or set-comparison, a malformed exemption entry is reported and excluded
from matching (never silently granted), and `_is_exempt` uses `_hashable`
guards on both the query pair and every candidate exemption's own
`id_a`/`id_b` before ever forming a `{a, b}` set for comparison.

## CLI fail-safe contract

`main()` retains its existing hard preflight (`check_schemas` gate before
any dependent check runs) and now additionally wraps the entire
validation flow in `_run_validation()`, called from `main()` inside a
`try/except`: `ValidationError` (missing file, invalid JSON, non-object
record) prints `FAIL: {message}` using the existing repository-relative
path helper; any other, truly unforeseen exception is caught by a final
`except Exception` that prints a single generic, non-traceback message
(`"FAIL: an unexpected internal error occurred during validation."`) and
returns 1 — deliberately never echoing the exception's own text, since
that could leak an absolute path or raw artifact content. This boundary
is documented in-code as the **secondary, last-resort** mechanism only;
the primary fix is the type-first preflight validation above, and the
acceptance evidence below confirms every known malformed-value scenario
is now resolved by that primary mechanism, never by falling through to
this boundary.

## Tests

`tests/test_benchmark_v2_integrity.py`, new section "malformed-value
(list/dict/number/bool/null) handling":
`test_expected_stop_reason_list_value_is_rejected_not_crashed` and
`test_provenance_split_list_value_is_rejected_not_crashed` (the two
exact reported crash reproductions); parametrized matrices
`test_corpus_field_malformed_value_is_rejected_not_crashed` (17 corpus
field/value parameter combinations), `test_case_field_malformed_value_
is_rejected_not_crashed` (17 case parameter combinations),
`test_label_field_malformed_value_is_rejected_not_crashed` (26 label
parameter combinations), `test_provenance_field_malformed_value_is_
rejected_not_crashed` (16 provenance parameter combinations) — counts
verified directly from the parameter arrays in
`tests/test_benchmark_v2_integrity.py` (`CORPUS_MALFORMED_FIELDS` etc.),
totalling 76 parametrized collected cases from these 4 test functions;
`test_non_object_provenance_entry_is_rejected_not_crashed` (direct-call
non-dict provenance records); `test_cli_expected_stop_reason_list_probe`
and `test_cli_provenance_split_list_probe` (true CLI-level, via
`validate_mod.main([])`, reproductions of the two headline crashes);
`test_combined_schema_malformed_fixture_cli_aggregates_without_crash`
(multiple simultaneous list/dict malformed values across corpus, case,
and label in one CLI run, asserting every distinct field is reported);
`test_cli_non_object_provenance_jsonl_record_fails_cleanly` (a raw JSON
string as a provenance line, verified to fail via the existing
`_load_jsonl` object check); `test_cli_error_order_is_deterministic_
across_repeated_runs` (two consecutive `main([])` runs against the same
malformed tree produce byte-identical, internally sorted error output);
`test_valid_current_candidate_still_passes_default_validation` (the
real, current, unmutated candidate benchmark still passes end to end
after all of this round's hardening). Existing round-1/round-2 negative
tests whose expected error-message substrings changed shape under the
new, more descriptive helper wording (e.g. `"invalid top_k"` →
`"top_k has invalid type ... (must be an integer, not bool/float)"`)
were updated to match the new wording, not weakened — each still asserts
the same underlying field and failure category.

## Malformed-value probe results

Executed directly in this session, via `validate_mod.main([])` against a
synthetic candidate tree pointed at through monkeypatched paths (matching
the pattern of the round-1/round-2 CLI tests already in this file), and
independently via a standalone script using `importlib.util.spec_from_
file_location` against the real module (not the test fixtures) to
reproduce the exact reported command-line scenario:

```
expected_stop_reason=[] on a label:
FAIL: 1 validation error(s):
  - label 'V2-DEV-9001' expected_stop_reason has invalid type list (must be a string)
RETURN CODE: 1   (no traceback, no absolute path)

authoring-provenance split=[]:
FAIL: 22 validation error(s):
  - authoring-provenance entry for 'V2-DEV-9001' split has invalid type list (must be a string)
  - ... (21 further, unrelated, correctly-aggregated errors from the otherwise-empty fixture)
RETURN CODE: 1   (no traceback, no absolute path)
```

Both previously crashed with `TypeError: unhashable type: 'list'`; both
now return a clean, non-zero, traceback-free result.

## Acceptance gate (round 3)

- Focused Phase 12D suite (`test_benchmark_v2_schema.py`,
  `test_benchmark_v2_integrity.py`, `test_benchmark_v2_freeze.py`):
  **246 passed** (up from 161; the +85 delta in *collected pytest cases*
  comes from 13 new test functions, all in
  `test_benchmark_v2_integrity.py` — 76 collected cases from the 4
  parametrized matrix functions (17 corpus + 17 case + 26 label + 16
  provenance parameter combinations) plus 9 single-case test functions;
  `test_benchmark_v2_schema.py` and `test_benchmark_v2_freeze.py`
  required no changes).
- Full repository suite, `.venv\Scripts\python.exe -m pytest -q`, no
  `--ignore`: **569 passed, 1 warning** (up from 484; the +85 delta is
  exactly the Phase 12D delta above — no other test file changed). The
  one warning is Starlette's pre-existing `httpx2` deprecation notice on
  `TestClient` import (`app/` and `requirements.txt` unchanged; `httpx2`
  was not installed).
- `python -m py_compile` on `scripts/validate_v2_benchmark.py`,
  `tests/test_benchmark_v2_schema.py`, `tests/test_benchmark_v2_
  integrity.py`: clean.
- `scripts/validate_v2_benchmark.py` (default, guard-independent) against
  the real candidate benchmark: **PASS**, `OK: 172 documents, 120 cases
  across 3 splits, all checks passed`.
- `scripts/validate_v2_benchmark.py --diagnose-current-guards`
  (non-gating): **PASS**, `44 agree, 0 disagree` (development+validation
  scope), exit code 0 — confirms the diagnostic remains non-gating.
- `scripts/build_v2_benchmark.py --verify-determinism`: **PASS**,
  byte-identical two-build comparison, unaffected by this round (no
  content-generation logic was touched).
- `scripts/freeze_v2_benchmark.py verify`: **PASS**, `OK: 9 file(s)
  verified against the frozen CANDIDATE manifest, no drift detected` —
  the nine-file candidate manifest remains valid because no generated
  artifact byte changed; this round modified only validator/test code.
- `git diff --check`: clean (no whitespace errors). `git status --short`:
  change set confined to `scripts/validate_v2_benchmark.py`,
  `tests/test_benchmark_v2_schema.py` (untracked, unchanged this round),
  `tests/test_benchmark_v2_integrity.py`, this document, and the other
  documentation files listed in the final response — no file under
  `app/`, `requirements.txt`, the frozen v1 benchmark,
  `reports/evaluation/`, or `report-latex-template/` was touched; no
  `scripts/build_v2_benchmark.py`/`scripts/freeze_v2_benchmark.py` change
  (freeze was investigated and found to operate purely on file bytes —
  SHA-256/size only, never parses JSONL field values into a set/dict — so
  it is not exposed to this bug class and required no change, per the
  scope restriction to modify build/freeze scripts only with direct
  evidence of the same issue).

**Final recommendation (round 3, superseded — see "Final Malformed-Value
Verification" below): the round-3 implementation pass closed with READY
FOR FINAL MALFORMED-VALUE READ-ONLY VERIFICATION; that verification has
since run and its result is recorded below.**

Not APPROVE. Not DONE. Phase 12D remains **IN REVIEW**; the manifest
remains **CANDIDATE**. Phase 12E has not been started.

## Final Malformed-Value Verification

An independent Code X read-only verification of the round-3 fix ran after
the implementation pass
(`docs/modernization-ai-reviews/codex-phase-12d-final-malformed-value-verification.md`):

- Implementation presence: **RESOLVED**
- Validation ordering: **RESOLVED**
- Corpus/case fail-safe handling: **RESOLVED**
- Label fail-safe handling: **RESOLVED**
- Provenance/exemption fail-safe handling: **RESOLVED**
- CLI error safety: **RESOLVED**
- Regression preservation: **RESOLVED**
- Critical issues: **None**
- Blocking Major issues: **None**
- Required action: **documentation alignment only**
- Code X verdict before documentation correction: **REVISE**

The REVISE was caused solely by three documentation inaccuracies in this
document's own round-3 narrative, not by any implementation defect:

1. It over-claimed that only fully preflight-valid provenance records
   enter `by_artifact_id` — in fact a record with a usable string
   `artifact_id` is indexed for deterministic identity/duplicate
   reporting before its remaining fields are validated (fail-safe, not
   fully exclusionary; corrected in the provenance-hardening section
   above).
2. It over-claimed that malformed values are simply skipped by all
   downstream checks — in fact selected downstream checks intentionally
   process malformed records through type guards, `_safe_in`, and safe
   identifiers to aggregate deterministic errors (for example, the 22
   errors of the `split=[]` probe are safe deterministic validation
   findings, not an exception; corrected in the validation-order section
   above).
3. It under-counted the corpus and label malformed-value parameter lists
   as 16 and 25 — the actual arrays in
   `tests/test_benchmark_v2_integrity.py` contain **17** corpus and
   **26** label parameter combinations (case 17 and provenance 16 were
   already correct; corrected in the Tests and Acceptance-gate sections
   above and in every other document repeating the same counts).

This documentation-alignment pass changed **no code, no tests, and no
generated benchmark artifact** — the independently verified evidence
(focused **246 passed**; full suite **569 passed, 1 warning**; 9-file
candidate manifest verified) is retained as-is, not re-run.

**Final recommendation: READY FOR FINAL DOCUMENTATION READ-ONLY
VERIFICATION.**

Not APPROVE. Not DONE. Phase 12D remains **IN REVIEW**; the manifest
remains **CANDIDATE**. Phase 12E has not been started.

## Remaining limitations (documented, not hidden)

- The top-level `except Exception` boundary in `main()` is, by design,
  never expected to trigger given the primary type-first fix above; it
  has no dedicated positive-path test that forces an exception past the
  primary defenses (doing so would require monkeypatching a helper to
  misbehave, which was judged lower value than the exhaustive
  malformed-value matrix already covering every real field). Its own
  logic (an `except Exception: print(...); return 1`) is simple enough
  to review directly rather than requiring a dedicated test.
- The malformed-value matrix covers `list`/`dict`/`bool`/`float` values
  in enum, string, list, and integer positions; it does not exhaustively
  cover every other conceivable JSON scalar oddity (e.g. a very large
  integer, a Unicode surrogate in a string) — those were not part of
  Code X's reported finding and are not a known crash.
- As with round 2, the bilingual/similarity controls remain lexical, not
  semantic — unaffected by, and unrelated to, this round's fix.
