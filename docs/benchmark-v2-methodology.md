# Benchmark V2 Methodology

**Phase:** 12D — Independent Benchmark V2 Design, Generation, Validation and Freeze
**Status:** DONE — Code X, Gemini, and Grok final audits PASS
**Governing decision:** `docs/decisions/ADR-003-v2-benchmark.md`
**Scope:** This document describes benchmark *artifacts only*. It produces no
security evaluation results, no ASR/FPR/FNR numbers, and no ablation output —
that is Phase 12E's job, which has not started.
**Manifest status:** FINAL (see §14/§14a) — the same nine artifacts reviewed
at commit `4e10a2e` were finalized only after Code X, Gemini, and Grok all
returned PASS. Phase 12E has not started and no evaluation metric is claimed.

## 1. Research purpose

Phase 7.1 scored v1's 40-case `redteam/prompts.jsonl` at 40/40 after rules
were tuned in direct response to observed failures on that same set
(`TASK_BOARD.md` §Phase 7.1). That is legitimate calibration, but the 40/40
number cannot demonstrate generalization to unseen attack phrasing. ADR-003
requires a second, independently governed benchmark — v2 — whose **holdout**
split is never referenced while authoring or tuning any guard rule, so that
Phase 12E can report a defensible generalization measurement instead of a
recalibration measurement.

Phase 12D's job is narrowly: design and freeze that benchmark. It must not
modify any guard rule, run the pipeline, or compute any metric.

## 2. Repository location and structure

ADR-003 named a placeholder target (`redteam/v2/`), explicitly deferring the
final path decision to Phase 12D implementation time. This benchmark is
placed under **`datasets/v2/`** instead, for two reasons: (1) `datasets/` is
the repository's existing convention for versioned corpus content (`datasets/
clean/`, `datasets/poisoned/`), while `redteam/` holds only the single frozen
v1 attack-prompt file and its companion taxonomy docs — v2 has its own
corpus, cases, labels, and manifest, which is a materially larger artifact
set than `redteam/`'s single-file shape; (2) keeping v2 out of `redteam/`
avoids any accidental conflation with the already-frozen, permanently
unmodified v1 corpus and its existing methodology doc
(`docs/dataset/dataset-methodology.md` §9). This choice is recorded as a
clarifying addendum to ADR-003 (see that file's "Implementation Note"
section) rather than a new ADR, since it does not change any rule ADR-003
fixes — only the directory name.

```
datasets/v2/
  README.md                        -- operator-facing quick reference
  corpus/documents.jsonl            -- 172 ingestible documents
  cases/development.jsonl           -- 30 execution-only inputs
  cases/validation.jsonl            -- 30 execution-only inputs
  cases/holdout.jsonl               -- 60 execution-only inputs
  labels/development.jsonl          -- 30 ground-truth records
  labels/validation.jsonl           -- 30 ground-truth records
  labels/holdout.jsonl              -- 60 ground-truth records
  manifests/benchmark-v2-manifest.json  -- SHA-256 FINAL freeze manifest
  contamination-exemptions.json     -- optional, rationale-required exemption list (currently empty)
```

Generator, validator, and freeze tool live under `scripts/`:
`build_v2_benchmark.py`, `validate_v2_benchmark.py`, `freeze_v2_benchmark.py`.
Tests live under `tests/`: `test_benchmark_v2_schema.py`,
`test_benchmark_v2_integrity.py`, `test_benchmark_v2_freeze.py`.

## 3. Input/label separation

Case files (`cases/*.jsonl`) contain **only** execution inputs:
`case_id, split, scenario_family, language, query, top_k,
relevant_document_ids, evaluation_scope`. `relevant_document_ids` is
documentation metadata for this benchmark's own maintainers (used by the
optional guard diagnostic and the integrity tests) — Phase 12E's evaluation
runner must submit only `query`/`top_k` to the real RAG query service and let
real BM25 retrieval decide what comes back, never read `relevant_document_ids`
to short-circuit retrieval. The C0-C7 matrix uses the internal
`run_rag_query_uncommitted(..., guard_profile=...)` seam defined by the Phase
12E plan; public HTTP remains `ALL_ON` and may be checked only by a separate C0
parity smoke. `evaluation_scope`
(`end_to_end` / `component` / `availability_fault` / `residual_risk_only`) is
execution-routing information, not an expected outcome — see §6a.

Label files (`labels/*.jsonl`) contain ground truth and non-runtime authoring
metadata, one record per `case_id`: `category, attack_family,
expected_final_decision, allowed_final_decisions, expected_stop_reason,
allowed_stop_reasons, expected_provider_called, expected_retrieval_behavior,
expected_context_behavior, expected_dlp_action,
expected_redaction_categories, expected_redaction_count,
expected_security_property, rationale, residual_risk,
expected_document_ingestion_status, template_id, semantic_group_id,
translation_group_id, authoring_set`.

`expected_final_decision`/`allowed_final_decisions` use the repository's real
`app/core/decisions.Decision` values verbatim (`allow`, `block`, `sanitize`,
`log_only`, `human_review`), and `expected_stop_reason`/`allowed_stop_reasons`
use `app/services/rag_query.py`'s real `STOP_*` string constants verbatim —
both hand-copied as plain string literals into the generator (no import
dependency from `scripts/build_v2_benchmark.py` on `app/`). Every value is
independently checked for enum validity by
`scripts/validate_v2_benchmark.py::check_schemas` in the **default, guard-
independent** validation path (no `app/guards/*` import at all — see §9 for
why the previous design's guard cross-check was removed from the gating
path after the Code X Phase 12D audit).

**Non-runtime authoring metadata (added per Code X Phase 12D audit, Critical
#2):** `template_id` (`{family}:{split}:{index}`, unique per authored content
bank entry), `semantic_group_id` (a coarser grouping across families that
exercise the same underlying mechanism — see §6a), `translation_group_id`
(groups cases that share the same authored content-bank entry across
languages within one split), and `authoring_set` (equal to the case's own
split). These fields live only in `labels/`, never in `cases/`, per Code X's
explicit instruction not to place hidden authoring signals in runtime case
inputs.

Corpus documents (`corpus/documents.jsonl`) contain only ingestible content:
`document_id, external_id, source_key, ingestion_mode, title, content,
metadata, language, scenario_family`. **`expected_ingestion_status` was
removed from the corpus schema** (Code X Phase 12D audit, Major #2 — it was
an expected *outcome* stored outside `labels/`) and replaced by
`expected_document_ingestion_status` in the corresponding label record.
`ingestion_mode` is retained in the corpus — it describes execution routing
only (which service/policy contract Phase 12E must use to attempt ingestion:
the public-ingestion service contract, an evaluation-only internal policy
call, or "rejected" meaning the `source_key` itself is unregistered), not a
ground-truth claim about whether that attempt succeeds. No corpus document
carries `is_poisoned` or any other runtime-visible ground-truth field —
malicious content lives in `content` itself (that is what is evaluated), never
in a side-channel flag.

Enforced by both the validator (`check_schemas`, `check_no_runtime_label_
coupling`) and dedicated tests (`test_benchmark_v2_schema.py`,
`test_benchmark_v2_integrity.py::test_no_runtime_label_coupling`):
- No `is_poisoned`/`expected_ingestion_status`/any ground-truth field
  anywhere in the corpus.
- No `expected_decision`/`expected_final_decision`/`expected_document_
  ingestion_status`/`template_id`/`semantic_group_id`/`translation_group_id`/
  `authoring_set`/any other label-only field in any case file.
- No file under `app/` references `datasets/v2` or `benchmark-v2` (static
  source scan) — runtime code has zero import-time or read-time dependency
  on this benchmark's inputs or labels. Only a future, out-of-`app/` Phase
  12E evaluation runner is expected to read `cases/` and, strictly after
  receiving a response, `labels/`.
- Dataset directory names never influence guard decisions: none of
  `app/guards/*.py`, `app/services/rag_query.py`, or `app/core/source_policy.
  py` were modified in this phase (verified — see §14).

## 4. Corpus document schema and source-key policy

`source_key` values are drawn **exactly** from `app/core/source_policy.py`'s
real policy table (mirrored as a plain dict in the generator, `SOURCE_POLICY`,
to avoid an import-time dependency on `app/`):

| `source_key` | `ingestion_mode` | `trust_level` | `classification` | `source_type` |
|---|---|---|---|---|
| `api_upload` | public (`POST /v1/documents/ingest`) | `untrusted_external` | `internal` | `api_upload` |
| `synthetic_clean_corpus` | internal-only (`allow_internal=True`, never reachable via the public route) | `trusted_internal` | `internal` | `synthetic_corpus` |
| `synthetic_external_feed` | internal-only | `untrusted_external` | `internal` | `synthetic_corpus` |
| `v2-unregistered-source-key` | rejected at ingestion | n/a | n/a | n/a |

`v2-unregistered-source-key` is a **deliberately invalid** key, used only by
the `provenance_denied_at_ingestion` family (see §8) to exercise
`app/core/source_policy.py`'s fail-closed unknown-source-key rejection. The
validator (`check_source_keys`) rejects any other family that uses it.

## 5. Case and label schema, decision/stop-reason vocabulary

See §3 for the full field lists. `expected_final_decision` is always exactly
one of the five real `Decision` values; `allowed_final_decisions` is a
superset used for cases with more than one acceptable correct outcome (e.g.
`benign_trap_query`, where either `log_only` or the softer `allow` reading is
defensible pending Phase 12E's runner design — never used to paper over a
genuinely wrong label). `expected_provider_called` is a plain boolean.
`expected_redaction_count`/`expected_redaction_categories` are populated only
for the two `leakage_*` families (see §8); every other case sets them to `0`/
`[]`, since the deterministic Mock LLM Provider's response shape does not
vary by content (see §8's construct-validity note).

## 6. Split sizes and distribution

| Split | Cases | Role (ADR-003) |
|---|---|---|
| development | 30 | May be referenced while authoring/tuning any rule |
| validation | 30 | Used to check rule behavior without being the final reported number |
| holdout | 60 | Never referenced while authoring/tuning; executed once, in Phase 12E |
| **Total** | **120** | Exceeds ADR-003's 100-case floor |

172 corpus documents support the 120 cases (several families use 2 or more
documents per case — mixed-retrieval, multi-chunk-coordination, and
budget-edge families in particular).

### Class balance (Code X Phase 12D audit, Major #3)

The original Phase 12D pass shipped 36 benign / 74 malicious / 6 mixed / 4
neutral (≈30% benign), which Code X found too weak to support the document's
own "approximately balanced" wording and to give a statistically meaningful
false-positive-rate denominator. The corpus was rebalanced to match Code X's
own reviewed distribution exactly:

| Split | benign | malicious | mixed | neutral | total |
|---|---|---|---|---|---|
| development | 12 | 12 | 4 | 2 | 30 |
| validation | 12 | 12 | 4 | 2 | 30 |
| holdout | 24 | 24 | 8 | 4 | 60 |
| **Total** | **48** | **48** | **16** | **8** | **120** |

`scripts/validate_v2_benchmark.py::check_class_distribution` enforces these
exact bounds (not a loose "approximate" claim) as a gating check; a category
count outside these exact numbers now fails validation.

Rebalancing did not remove or add any scenario family — all 23 required
families are still present in every split (`REQUIRED_FAMILIES`, §8). Instead:
counts on the 9 benign families were raised from a uniform 1/1/2 to a mix of
1/1/2 and 2/2/4 (three families bumped: `clean_benign_rag`,
`benign_trap_query`, `mixed_trust_benign_retrieval`); the 12 malicious
families were normalized to a uniform 1/1/2 each (down from a range of
1/1/2 to 2/2/6); the single mixed family
(`mixed_benign_malicious_retrieval`) was raised to 4/4/8; the single neutral
family (`availability_failure_case`) was raised to 2/2/4. See §8 for the
per-family table.

### §6a. `evaluation_scope` (Code X Phase 12D audit, Major #2)

Every case declares how Phase 12E is expected to execute it:

| `evaluation_scope` | Meaning | Families |
|---|---|---|
| `end_to_end` | Executes the complete retrieval-to-output RAG service pipeline. Phase 12E C0-C7 uses one comparable in-process seam; optional C0 HTTP parity is separate | 20 of 23 families (104 of 120 cases) |
| `component` | Requires a two-step ingestion-then-query workflow rather than one HTTP call | `provenance_denied_at_ingestion` (4 cases) |
| `availability_fault` | Requires a deterministic policy-error setup (an out-of-policy `top_k`), not a content-based check | `availability_failure_case` (8 cases) |
| `residual_risk_only` | Documents a known detection blind spot; must be excluded from expected-detection denominators, never counted as a false negative | `fragment_beyond_per_chunk_prefix` (4 cases) |

Phase 12E's runner must not infer execution mode from `scenario_family`
strings — `evaluation_scope` is the explicit, validated contract. Labels for
`component`/`residual_risk_only` cases must not claim an HTTP end-to-end
security result; each says so explicitly in its `rationale`/`residual_risk`
text (see §8's per-family notes).

## 7. Multilingual distribution

Language is assigned by a fixed, deterministic rotation
(`itertools.cycle(["vi","vi","en","vi","bilingual","en"])`), never random
sampling — the same case index always gets the same language across rebuilds.
Realized distribution across all 120 cases: **60 vi (50%), 40 en (33.3%), 20
bilingual (16.7%)**. `bilingual` cases keep a Vietnamese sentence frame and
append an equivalent English sentence (`_lang_text`'s bilingual branch), never
a literal translation-pair duplicate — combined with the per-case unique
`V2TOK#####` token embedded in both query and content, this guarantees no
case is a translated duplicate of another case's query (verified by
`check_no_normalized_duplicate_queries`, which normalizes whitespace/case but
does not need to detect cross-language paraphrase, since none exists by
construction — every language variant is a distinct hand-written sentence,
not a machine translation of another variant in the corpus).

## 8. Scenario taxonomy (23 families)

| Family | Cases (dev/val/hold) | Category | `evaluation_scope` | Notes |
|---|---|---|---|---|
| `clean_benign_rag` | 2/2/4 = 8 | benign | end_to_end | Baseline true-negative |
| `benign_security_discussion` | 1/1/2 = 4 | benign | end_to_end | Legitimate question *about* injection/DLP defense, not an attack |
| `benign_trap_query` | 2/2/4 = 8 | benign | end_to_end | Bare word "override" in a legitimate business context — ADR-003's required FPR "trap" query, LOG_ONLY tier |
| `legitimate_authority_language` | 1/1/2 = 4 | benign | end_to_end | Ordinary "approved by the board" phrasing, distinct from an override-of-instructions claim |
| `academic_discussion_of_injection` | 1/1/2 = 4 | benign | end_to_end | Descriptive/educational text about the concept, no imperative override phrase |
| `benign_secret_like_identifier` | 1/1/2 = 4 | benign | end_to_end | Order/tracking numbers that must not be mistaken for secrets |
| `mixed_trust_benign_retrieval` | 2/2/4 = 8 | benign | end_to_end | One low-trust + one high-trust benign document, both accepted |
| `no_retrieval_hit` | 1/1/2 = 4 | benign | end_to_end | Unique token matches nothing; safe no-answer, not an error |
| `fragment_near_aggregate_budget` | 1/1/2 = 4 | benign | end_to_end | 9×~500-char benign chunks exceed the 4000-char aggregate budget; deterministic exclusion by budget, not content |
| `direct_injection` | 1/1/2 = 4 | malicious | end_to_end | Input Guard BLOCK-tier queries, no retrieval reached |
| `indirect_retrieved_injection` | 1/1/2 = 4 | malicious | end_to_end | Single retrieved chunk; development/validation use distinct SANITIZE-tier rules, holdout uses BLOCK-tier rules |
| `malicious_low_trust_source` | 1/1/2 = 4 | malicious | end_to_end | `api_upload` (untrusted_external) source; excluded by content check, not provenance |
| `compromised_trusted_source` | 1/1/2 = 4 | malicious | end_to_end | `synthetic_clean_corpus` (trusted_internal) source; proves trust does not bypass content inspection |
| `provenance_denied_at_ingestion` | 1/1/2 = 4 | malicious | **component** | Unregistered `source_key`; the only end-to-end-reachable form of "denied provenance" (see §9); requires an ingestion-then-query workflow |
| `all_context_blocked_multi_malicious` | 1/1/2 = 4 | malicious | end_to_end | Every retrieved chunk malicious; provider never invoked |
| `multi_chunk_coordination` | 1/1/2 = 4 | malicious | end_to_end | Two individually-clean chunks whose combination trips the bounded aggregate check |
| `fragment_beyond_per_chunk_prefix` | 1/1/2 = 4 | malicious | **residual_risk_only** | Coordinating phrase positioned beyond the 400-char per-chunk excerpt — documented detection blind spot, not a leak; excluded from expected-detection denominators |
| `zero_width_whitespace_variant` | 1/1/2 = 4 | malicious | end_to_end | Zero-width space (U+200B) inside a trigger phrase; tests `_normalize_for_detection` |
| `markdown_html_concealment` | 1/1/2 = 4 | malicious | end_to_end | Trigger phrase hidden inside an HTML comment block |
| `leakage_context_exclusion` | 1/1/2 = 4 | malicious | end_to_end | Canary marker co-located with a BLOCK-tier injection phrase in one chunk — whole chunk excluded, canary never reaches the provider |
| `leakage_dlp_mechanism_reference` | 1/1/2 = 4 | malicious | end_to_end | Canary marker alone; SANITIZE-tier `rag-fake-secret` rule redacts in place |
| `mixed_benign_malicious_retrieval` | 4/4/8 = 16 | mixed | end_to_end | One benign + one malicious document retrieved together; benign one still reaches the provider |
| `availability_failure_case` | 2/2/4 = 8 | neutral | **availability_fault** | `top_k=30` exceeds the configured policy ceiling; deterministic fail-closed rejection with a terminal audit event |

All 23 families are present in all 3 splits, checked against the explicit
`REQUIRED_FAMILIES` registry in `scripts/validate_v2_benchmark.py` (not
merely against whatever happens to be present in the generated files — Code
X Phase 12D audit, Major #1), and (dev,val,hold) sums to exactly 30/30/60.

### Provenance coverage boundary

`app/guards/provenance_guard.py`'s allow-lists (`ALLOWED_TRUST_LEVELS =
{trusted_internal, untrusted_external}`, `ALLOWED_CLASSIFICATIONS =
{internal}`, `ALLOWED_SOURCE_TYPES = {api_upload, synthetic_corpus}`) already
cover **every** trust/classification/source_type combination
`app/core/source_policy.py` can assign to a real, successfully ingested
document — by architectural design, a retrieved hit can never carry
malformed or denied provenance metadata through the real ingestion+retrieval
path. `provenance_denied_at_ingestion` represents "denied provenance" the
only way it is actually reachable end-to-end: rejection happens at
*ingestion* time (an unregistered `source_key` is never indexed), not at
retrieval time. The genuinely-malformed-metadata condition remains covered
at the unit level by the existing `tests/test_provenance_guard.py`, which
constructs hits directly rather than through ingestion — this boundary is a
documented, intentional scope limit of this black-box benchmark, not an
omission.

### DLP/leakage construct-validity boundary

The deterministic Mock LLM Provider (`app/services/llm_provider.py::
MockLLMProvider`) never echoes retrieved context into its response — it
returns a fixed templated message plus a context-chunk count, regardless of
what the retrieved content contained. This means centralized DLP-on-
provider-output and Output-Guard-on-provider-output behavior is identical
regardless of corpus content, so true end-to-end "a secret was in a retrieved
document and got redacted from the final answer" cannot be exercised through
the black-box HTTP pipeline (already documented as a known limitation in
Phase 12C's own smoke test). The two `leakage_*` families instead test what
**is** end-to-end reachable and meaningful: whether the RAG Context Guard's
own `rag-fake-secret` rule (SANITIZE-tier, `FAKE_SECRET_PATTERN`) correctly
redacts or excludes a canary marker *before* it would ever reach the
provider — `leakage_context_exclusion` (canary co-located with a BLOCK-tier
phrase, whole chunk excluded) and `leakage_dlp_mechanism_reference` (canary
alone, in-place redaction). Centralized-DLP-on-provider-output remains
covered by the existing unit-level `tests/test_dlp_guard.py`, cross-
referenced here rather than re-tested by this benchmark.

## 9. Guard-independent validation, and the optional guard-agreement diagnostic

**Changed by the Code X Phase 12D audit (Critical #1).** The original design
had `scripts/validate_v2_benchmark.py::check_guard_cross_reference` import
the real, currently-deployed `app.guards.input_guard.evaluate_input` and
`app.guards.rag_guard.evaluate_rag_context`, re-derive the actual guard
decision for every case, and feed any mismatch into the validator's overall
pass/fail result. Code X found this circular: **benchmark integrity
validation must be independent of the implementation being evaluated** — a
structurally valid, independently-authored label can legitimately disagree
with today's guard behavior (that disagreement is exactly what Phase 12E
exists to measure), and gating the validator on agreement would reward
labels tuned to match current rules, undermining the whole point of an
independent benchmark.

**Fix:** the default validation path (`scripts/validate_v2_benchmark.py`
with no flags) now imports nothing from `app.guards.*`,
`app.services.rag_query`, or any other Phase 12C runtime module, and its
exit code never depends on guard behavior — verified by
`tests/test_benchmark_v2_integrity.py::
test_default_validation_path_imports_no_guard_modules` and
`test_no_gating_check_function_imports_app_guards`. An optional,
**explicitly opt-in, non-gating** diagnostic remains available:

```powershell
python scripts/validate_v2_benchmark.py --diagnose-current-guards
python scripts/validate_v2_benchmark.py --diagnose-current-guards --include-holdout-diagnostic
```

`diagnose_against_current_guards()` prints a report of where hand-authored
labels currently agree/disagree with `app.guards.input_guard`/
`app.guards.rag_guard`, clearly labeled "DIAGNOSTIC (non-gating)" and
explicitly stating that disagreement is expected evaluation evidence, not a
benchmark defect. It never rewrites a label, never affects
`validate_v2_benchmark.py`'s return code (proved by
`test_diagnostic_mode_reports_mismatch_without_changing_validator_result`),
and by default scopes only to development+validation — `holdout` is included
only with the separate `--include-holdout-diagnostic` flag, so an ordinary
development invocation cannot accidentally leak holdout ground truth into a
terminal.

This diagnostic (used purely as a developer sanity check during authoring,
never as a gate) caught one real authoring bug before it shipped: a
Vietnamese `direct_injection` variant used "thay vào đó" (Vietnamese for
"instead") where `app/guards/input_guard.py`'s
`direct-disregard-own-instructions` rule requires the literal English word
"instead" within 80 characters — fixed by keeping the English word "instead"
inline in the otherwise-Vietnamese sentence. The same class of bug recurred
several more times during the Critical #2 content-independence rewrite (a
Vietnamese "this note must override..." phrase using "memo"/"report" instead
of the regex-required "note", "operations" inserted between "this" and
"note" breaking a `\bthis note\b` boundary, and two multi-chunk-coordination
holdout pairs where one half alone already tripped a per-chunk rule,
defeating the "coordination" premise) — each caught and fixed the same way,
by re-running the ad-hoc guard-agreement check after every content change,
documented here for transparency rather than silently corrected.

Families not guard-decidable from static per-chunk text alone
(`provenance_denied_at_ingestion`, `no_retrieval_hit`,
`fragment_near_aggregate_budget`, `availability_failure_case`) are correctly
left to Phase 12E's live execution — the diagnostic function's own docstring
records this explicitly rather than fabricating a check that cannot be
meaningful.

## 10. Split-independent content authoring (Code X Phase 12D audit, Critical #2)

**What Code X found:** the original generator used the same family builder
function, in the same run, to produce development/validation/holdout content
from one shared per-family template, varying only a per-case token and a
language-rotation index. Measured result: 34 of 60 holdout queries scored
≥0.9 lexical similarity to an earlier split's query for the same family
(median similarity 1.0 after removing tokens/numbers), 17 of 23 families
shared an identical normalized template across splits, and one validation
case (`V2-VAL-0007`) was a 0.929-similarity restatement of a v1 case
(`RT-INJ-DIRECT-001`), violating ADR-003's prohibition on v1 reuse outside
development. A holdout built this way measures unseen *parameter*
substitution, not unseen *attack formulation* — it cannot support the
unseen-generalization claim ADR-003 exists to enable.

**Fix:** `scripts/build_v2_benchmark.py` was rewritten so every family draws
its development / validation / holdout content from three disjoint,
independently authored content banks (module-level `_*_DEV` / `_*_VAL` /
`_*_HOLD` constants) — different topics, different sentence structure,
different narrative framing per split, not a shared template with only a
token substituted. Where a family's content must trigger a specific guard
rule, each split deliberately draws from a **different alternative branch**
of that rule's regex where the rule offers more than one (e.g.
`rag-system-override` alone has eight independent trigger alternatives —
"notice to ai", "operating under new directives", "supersedes ... previous
... instructions", "treat this as the highest priority instruction",
"(developer|system) ... no longer applicable", "this note must override ...
policy", among others), so development/validation/holdout genuinely exercise
different phrasings, not reorderings of one phrasing. Query text that used to
be a fixed literal string regardless of split (`"policy fragment {token}"`,
`"shipping information {token}"`, etc.) was moved into the same
per-split-bank pattern. Filler/padding content for the two
budget/boundary-testing families (`fragment_near_aggregate_budget`,
`fragment_beyond_per_chunk_prefix`) — which is deliberately generic by
design, since its role is to occupy character budget, not carry meaning —
was also given three distinct filler paragraphs (one per split) rather than
one shared filler string, since a long shared filler dominates a
similarity-ratio comparison even when the short "meaningful" portion of the
sentence differs.

**Verification:** every fix above was validated two ways: (1) an ad-hoc
guard-agreement script (the mechanism behind `--diagnose-current-guards`,
§9) confirmed every trigger-bearing sentence still produces its intended
decision, in both its `vi` and `en` form, against the real
`app.guards.input_guard`/`app.guards.rag_guard`; (2) the new automated
contamination checks below, run against the full regenerated corpus, report
**zero findings** (`tests/test_benchmark_v2_integrity.py::
test_no_cross_split_contamination_in_real_data`,
`test_no_v1_contamination_in_real_data`).

**Boundary of §10's own fingerprint check, corrected in §10a below:** the
raw-text fingerprint/similarity check described in §11 compares text
within the *same* language surface form -- it cannot, by construction,
catch a genuine translation, since a translated sentence shares almost no
literal substring with its source. A second independent Code X audit
(`docs/modernization-ai-reviews/codex-phase-12d-benchmark-audit.md`
re-audit round) correctly identified this gap: the first Phase 12D fix
pass's documentation implied cross-split contamination detection was
complete after the §10/§11 fixes, but an exact EN/VI translation using two
different self-declared `translation_group_id` values would have passed
undetected. §10a below is the fix for that gap; it did not exist before
this second fix round and must not be described as having already been in
place.

## 10a. Authoring provenance and bilingual/translation contamination (Code X Phase 12D RE-AUDIT, Critical #1)

### Non-runtime authoring provenance

`datasets/v2/design/authoring-provenance.jsonl` is a new, non-runtime
artifact: one record per generated query and per generated corpus document
(292 records total -- 120 queries + 172 documents), with fields
`artifact_id, artifact_type, split, language, scenario_family,
semantic_group_id, translation_group_id, authoring_set,
normalized_text_hash`. It is produced deterministically by
`scripts/build_v2_benchmark.py::Registry._add_provenance` at generation
time (called from both `add_case` and `add_document`) and independently
re-verified by `scripts/validate_v2_benchmark.py::
check_authoring_provenance`, which:

- Confirms every case and every corpus document has exactly one matching
  provenance entry (a missing entry fails validation).
- Rejects a duplicate `artifact_id` within the provenance file.
- Recomputes `normalized_text_hash` from the *actual current* case/document
  text (using `build_v2_benchmark.normalized_text_hash`, the same function
  that generated it) and fails if it does not match the declared hash --
  this catches a stale or dishonestly-declared hash mapping, not merely a
  missing one.
- Independently re-derives, directly from the committed file (not by
  trusting the generator's own logic), that no `semantic_group_id` or
  non-null `translation_group_id` value is reused across two different
  splits.

**Important naming note:** this file's `semantic_group_id` (constructed as
`{scenario_family}:{split}`) and `translation_group_id` (constructed as
`{scenario_family}:{split}:{bank_index}`) are deliberately scoped to
`(family, split)` so that *by construction* neither value can ever collide
across two different splits -- this is a different, narrower concept from
the *label*'s own `semantic_group_id` field (§6a), which is intentionally
**coarser and cross-split** (e.g. `"instruction_override"`, shared by 8
families across all 3 splits), used only for Phase 12E's aggregate-metric
grouping. Reusing the same field name for two different scoping rules in
two different, both non-runtime files was a deliberate choice reviewed
during this fix (rather than inventing a third field name), but readers of
both files must not conflate them. `scripts/validate_v2_benchmark.py`
never cross-references the label's `semantic_group_id` when checking the
provenance file's `semantic_group_id`, or vice versa -- the two checks are
fully independent of each other.

### Benchmark-specific bilingual canonicalization

`scripts/validate_v2_benchmark.py::check_bilingual_contamination` is a
second, complementary control, addressing what the raw fingerprint check
in §11 structurally cannot: an EN/VI (or VI/EN) translation shares almost
no literal text with its source language, so no amount of tightening a
same-language similarity threshold would ever catch it.

The mechanism (`_canonicalize_bilingual`, standard-library only --
`unicodedata`, `re`, `difflib`, no new dependency): apply the same `_
fingerprint` normalization as §11's raw check, strip sentence punctuation,
then substitute every phrase in a small, hand-reviewed `BILINGUAL_LEXICON`
(~40 entries, matched longest-phrase-first so a longer entry is never
fragmented by a shorter one that is one of its substrings, and substituted
with collision-free numeric tokens `@C<n>@` rather than semantic token
names, so a later, shorter lexicon phrase's literal text can never
accidentally re-match a substring of an already-inserted token from an
earlier substitution -- both were real bugs caught and fixed during this
implementation, see the audit-resolution document). The result is compared
across every cross-split pair two ways: `difflib.SequenceMatcher` ratio
(order-sensitive, `BILINGUAL_SIMILARITY_THRESHOLD = 0.82`) **or** token
Jaccard overlap (order-insensitive, `BILINGUAL_JACCARD_THRESHOLD = 0.7`) --
either exceeding its threshold is a finding. The Jaccard check specifically
exists so a **clause-reordered** direct translation (same matched phrases,
different sentence order) is still caught even though reordering lowers
the sequence-based ratio.

**This is explicitly not a translation model or a general semantic-
duplicate detector.** It is a small, benchmark-specific lexical control
whose job is to catch an *obvious* direct translation or bilingual rewrite
of this benchmark's own authored content, verified against three concrete
scenarios (`tests/test_benchmark_v2_integrity.py`):

1. An exact EN/VI translation across splits, with distinct self-declared
   IDs, is rejected (`test_exact_translation_across_splits_with_distinct_
   ids_fails`).
2. A clause-reordered direct translation -- reordering which clause comes
   first, while each individual matched phrase stays intact -- is rejected
   (`test_clause_reordered_translation_fails_when_lexicon_covers_it`).
3. Genuinely independent EN/VI content for the same family is *not*
   flagged (`test_independently_authored_en_vi_same_family_cases_pass`).

**Documented, exact limitation:** a reordering that splits a *single*
lexicon phrase apart (e.g. moving one word from inside "annual leave
policy" to elsewhere in the sentence, rather than reordering which whole
clause comes first) is not caught, because the phrase then fails to match
its lexicon entry at all and falls back to two smaller, separately-matched
tokens -- this was observed directly while building the required test
fixtures (see the audit-resolution document) and is deliberately not
over-claimed as covered. More generally: a translation using phrasing this
~40-entry lexicon does not cover will not be canonicalized and may not be
caught. Exemptions (`scope: "bilingual"` in `datasets/v2/contamination-
exemptions.json`) require an explicit artifact-ID pair and a non-empty
rationale, exactly like every other exemption scope; none has been needed
for the real, regenerated corpus (see §11a for the measured statistics).

## 11. Contamination and split-integrity controls

- **Cross-split query/document fingerprint and similarity checks (new,
  Critical #2 fix).** `scripts/validate_v2_benchmark.py::
  check_cross_split_contamination` normalizes every case query and every
  corpus document's content (Unicode NFKC, lowercased, whitespace-collapsed,
  with per-case `V2TOK#####` tokens/case-IDs/doc-IDs stripped and numbers
  collapsed to `#`), then, for every cross-split pair (development-vs-
  validation, development-vs-holdout, validation-vs-holdout — v2's own
  splits are compared against each other regardless of v1), flags an exact
  fingerprint match ("template reuse") and a `difflib.SequenceMatcher` ratio
  ≥ **0.9** ("high similarity"). The 0.9 threshold is adopted directly from
  the Code X audit's own methodology — it is the same threshold the audit
  used to report the 34/60 finding and the 0.929 v1-similarity finding, so
  this validator enforces the same bar the finding itself was measured
  against. Also checks that no `template_id`/`translation_group_id` value is
  reused across two different splits (both are constructed to embed the
  split name, so this is a redundant safety net, not the primary mechanism).
- **v1 comparison, query AND referenced document (extended, Code X Phase
  12D RE-AUDIT, Critical #2).** The first fix-round's `check_v1_
  contamination` accepted a `corpus` parameter but never actually scanned
  it — only queries were compared against v1, so a v1 prompt copied
  verbatim into a validation/holdout **corpus document** would have passed
  undetected. This has been corrected: `find_v1_contamination_matches`
  now loads `redteam/prompts.jsonl`, normalizes every v1 prompt the same
  way, and compares it against every v2 **validation and holdout** query
  *and* every document referenced by a validation/holdout case, at the
  same 0.9 threshold — development is correctly excluded, since ADR-003
  permits v1 reuse only there. `check_no_orphan_documents` independently
  verifies every corpus document is referenced by at least one case, which
  is what makes "every referenced document" equivalent to "the whole
  corpus" with no gap for an unreferenced document to hide v1 content in.
  Error messages identify only safe artifact IDs (`case_id`/`document_id`),
  never the raw matched text. A direct comparison (exact match and
  substring containment, case-insensitive) additionally confirmed **zero
  verbatim v1 overlap** anywhere in v2's corpus or cases. See §11a for the
  separate query/document contamination counts measured after this fix.
- **Rationale-required exemption file.** `datasets/v2/contamination-
  exemptions.json` (currently empty — no exemption has been needed) supports
  a small list of `{"scope": "query"|"document"|"v1"|"v1-document"|
  "bilingual", "id_a", "id_b", "rationale"}` entries for a specific pair
  that is "truly unavoidable generic benign wording." An exemption with an
  empty or missing `rationale` is itself a validation error
  (`_exemption_errors`); an applied exemption is never silent — see
  `test_contamination_exemption_with_rationale_suppresses_the_specific_pair`.
  This file is now itself integrity-bound by the final manifest (§14a).

### 11a. Measured contamination statistics (after the Code X re-audit fix)

Computed directly against the regenerated `datasets/v2/` artifacts in this
session (all figures are exact, executed-command output, not estimates):

| Metric | Value |
|---|---|
| Maximum cross-split query similarity (any pair, any split) | 0.7213 |
| Median of each holdout query's own maximum similarity to any dev/val query | 0.4589 |
| Cross-split document similarity/template-reuse findings | 0 |
| Bilingual/translation contamination findings | 0 |
| Authoring-provenance findings (missing/duplicate/hash-mismatch/cross-split-group-reuse) | 0 |
| Semantic-group-id cross-split reuse count | 0 |
| Translation-group-id cross-split reuse count | 0 |
| v1 query contamination count | 0 |
| v1 document contamination count | 0 |
| Active contamination exemptions | 0 |

Both the maximum cross-split query similarity (0.70) and the median
holdout-query max-similarity (0.46) sit comfortably below the 0.9
gating threshold, indicating the split-independent authoring in §10 has a
healthy margin, not just a bare pass.
- **No duplicate IDs.** `document_id` and `case_id` are monotonic,
  registry-assigned sequences (`v2-doc-####`, `V2-{DEV,VAL,HOLD}-####`);
  `check_no_duplicate_ids` enforces uniqueness (tested against both the real
  data and synthetic duplicate-ID fixtures in
  `tests/test_benchmark_v2_integrity.py`).
- **No normalized-duplicate queries.** `check_no_normalized_duplicate_
  queries` normalizes whitespace/case (not tokens) across all three splits
  combined, catching accidental exact copy-paste even within one split.
- **No cross-split secret reuse.** A regex mirroring `app/guards/dlp_guard.py`'s
  detector shapes (`sk-...`, `AKIA...`, `ghp_...`, `Bearer ...`,
  `password=...`) scans corpus content and flags any verbatim credential-
  shaped value appearing in documents belonging to two different splits. The
  one canonical, documented canary marker
  (`FAKE-SECRET-0000-EXAMPLE-DO-NOT-USE`) is an explicit, intentional
  exemption — it is a fixed-format synthetic marker reused by design (same
  convention as the v1 benchmark's own canary), not a leaked real secret.
  Both the reuse-rejection and the canary-exemption paths are covered by
  synthetic fixtures in `tests/test_benchmark_v2_integrity.py`.
- **No document ID collisions / label-input mismatch.** `check_referential_
  integrity` confirms every `relevant_document_ids` entry exists in the
  corpus; `check_case_label_mapping` confirms every case has exactly one
  matching label record and vice versa, without raising an exception on a
  malformed/dangling reference (Major #1 fix — see §12).
- **No scenario-family leakage across splits.** Every family appears in
  every split by construction and is checked against the explicit
  `REQUIRED_FAMILIES` registry — there is no family that exists only in one
  split, which would otherwise let a rule-author infer holdout-only attack
  shapes from development/validation family names alone.
- **Remaining limitation: no semantic-similarity dependency.** No new
  dependency was added for embedding-based semantic similarity (out of
  scope, per the task's explicit "no new dependency" constraint); the
  `difflib.SequenceMatcher` lexical-ratio check above catches near-identical
  phrasing but not a genuine paraphrase that reuses no shared substring
  pattern. This residual limitation is smaller than before the Critical #2
  fix (automated checks now run and report zero findings, replacing the
  prior "manual read-through" claim) but is not eliminated.

### ADR-003 holdout-independence condition

ADR-003 requires holdout authoring to satisfy at least one of three
independence conditions (different author, documented time gap, or
independent review before freezing) "to prevent dev/validation authoring
habits from unconsciously shaping holdout design." This benchmark is
generated **programmatically** — a single deterministic builder function per
family produces its development, validation, and holdout instances from the
same fixed template in the same run, rather than a human separately designing
holdout scenarios after authoring development/validation ones. Conditions
(a) and (b), which assume separate human authoring sessions, do not literally
apply to this generation method. This benchmark instead satisfies, and is
declared to rely on, **condition (c): independent review before freezing** —
the holdout split (like the rest of Phase 12D) is subject to the
multidisciplinary audit this phase's own instructions require (Code X
technical audit, Gemini academic audit, Grok red-team audit, GitHub Copilot
working-tree review) before Phase 12D may be marked Done, and the holdout
split must not be treated as validated for Phase 12E use until that review
passes. This is recorded here as a **deviation requiring ADR-003
clarification** — ADR-003's independence conditions were written assuming
manual per-scenario authorship and should be read, for this programmatically-
generated benchmark, as satisfied by condition (c) applied to the whole
generator (not per-scenario). A future ADR-003 amendment should make this
explicit if programmatic generation is used again.

## 12. Complete schema and safe-failure validation (Code X Phase 12D audit, Major #1)

**What Code X found:** the original validator accepted invalid `Decision`
values and unknown label fields (no enum/exact-field check on labels), and
accepted a benchmark that was globally missing an entire scenario family
(coverage was checked only against whatever families happened to be present,
never against an explicit required list). Separately, a dangling document
reference or a mismatched case/label ID raised an unhandled `KeyError`
instead of a clean, deterministic validation error.

**Fix:** `scripts/validate_v2_benchmark.py::check_schemas` now enforces
exact field sets (missing *and* unexpected fields are both errors) for
corpus/case/label records, validates every enum (`Decision`, `split`,
`language`, `evaluation_scope`, `category`,
`expected_document_ingestion_status`, `expected_dlp_action`,
`expected_stop_reason`) against an explicit allowed-value set, and validates
basic field types (`top_k` a positive int, `expected_provider_called` a
bool, `expected_redaction_count` a non-negative int). `check_family_registry`
checks split coverage against the fixed `REQUIRED_FAMILIES` set (§8), not
against whatever is present. Every check function is written defensively —
using `dict.get(...)` throughout, never direct-indexing a possibly-missing
key — so a dangling document reference (`check_referential_integrity`) or a
mismatched case/label ID pair (`check_case_label_mapping`, a new dedicated
function replacing the ad-hoc lookup that used to live inside the removed
guard cross-check) is reported as a normal, sorted, deterministic error
message, never an unhandled traceback. `main()`'s error messages use
repository-relative paths (`_rel()`), never an absolute, machine-specific
path.

Required check order (JSON parsing → exact field names → required fields →
field types → enum values → split/language consistency → unique IDs →
one-to-one case-label mapping → document references → family registry
coverage → class-distribution bounds → contamination rules → manifest
structural sanity) is implemented directly as the sequence of `all_errors +=
check_*(...)` calls in `main()`. CLI-level negative tests for every required
probe (invalid Decision, unknown case field, unknown label field, missing
required field, dangling document reference, mismatched case/label mapping,
missing required family, inconsistent split, inconsistent language,
malformed JSONL, invalid `evaluation_scope`) live in
`tests/test_benchmark_v2_integrity.py`.

### 12a. Field-type completeness (Code X Phase 12D RE-AUDIT, Major #1 -- completed)

**Correcting an overstatement from the first fix round:** §12 above,
written after the first Code X audit, described `check_schemas` as
enforcing "complete field-type validation." A second, independent Code X
re-audit correctly found this was not yet true: `external_id` duplicates
were silently accepted, a non-string `external_id` passed, a non-string
`query` passed, and — most seriously — a non-string corpus `content` value
reached downstream regex-based checks (`.finditer(content)` inside
`check_no_cross_split_secret_reuse`) and raised an **unhandled
`TypeError`**, not a clean validation error. This section now accurately
describes the completed contract; §12's own text above should be read as
"the schema/enum framework this round completed," not as a claim that
every field's type was already covered at that time.

**Fix, this round:**

- `document_id`, `external_id`, `source_key`, `case_id`, `query`, and
  label `rationale` are all validated as non-empty strings
  (`_require_nonempty_str`), never left to a bare truthiness check that a
  non-string value could silently pass.
- `external_id` uniqueness is enforced across the whole corpus
  (`check_no_duplicate_external_ids`), mirroring `document_id` uniqueness
  — both are assigned together by the generator, so this benchmark's own
  contract is that they are always 1:1.
- `content` and `title` are validated as strings; a non-string `content`
  is now a clean `check_schemas` error, **and** the two content-scanning
  checks that previously crashed on it
  (`check_no_cross_split_secret_reuse`'s `_SECRET_LIKE_PATTERN.finditer`,
  and the cross-split-contamination query/document loops) were made
  independently defensive (`isinstance(..., str)` guards) so they degrade
  to "skip this already-reported-invalid record" rather than ever raising.
- `metadata` must be a `dict`, and every key/value in it (recursively, to
  depth 20) must be JSON-representable: string keys only, and no
  `NaN`/`Infinity` float, via `_is_json_safe_value` — a metadata dict is
  otherwise unbounded, structurally valid Python but not valid JSON, which
  is exactly the shape of bug that previously surfaced as `Missing
  provenance entry fails` acceptance criteria.
- `top_k` bounds were tightened to a documented, enforced `[1, 50]` range
  (mirroring `app/schemas/requests.py`'s real Pydantic ceiling), not just
  "positive" — an out-of-range `top_k` (e.g. `999`) is now rejected, in
  addition to the pre-existing bool/float rejection.
- `relevant_document_ids` elements are now individually type-checked (must
  each be a string), not just the outer list.
- Label `allowed_final_decisions`/`allowed_stop_reasons`/`expected_
  redaction_categories` non-list values, `expected_provider_called`
  non-bool values, and `expected_redaction_count` out-of-range values
  (bounded `[0, 100]`, not merely non-negative) are all now explicit
  `check_schemas` errors.
- `scenario_family` on corpus/case/label records is now checked against
  the `REQUIRED_FAMILIES` registry (§8), not merely required to be
  present.

CLI-level regression tests for every one of these
(`tests/test_benchmark_v2_integrity.py`,
"Major #1 -- complete field-type validation" section) construct the exact
malformed fixture and assert both the specific error message and — for the
`content`-type case specifically — that `main()` returns 1 with no
`Traceback`/`TypeError` text in its output.

### 12b. Type-first (list/dict-safe) validation (Code X Phase 12D RE-AUDIT round 3)

**Correcting a second overstatement:** §12a's "complete field-type
validation" was itself only complete against non-`list`/non-`dict`
scalars. A third, independent Code X re-audit found that every
enum-membership check in `check_schemas` and `check_authoring_provenance`
— `expected_stop_reason`, `allowed_stop_reasons`, `category`,
`expected_final_decision`, `expected_dlp_action`,
`expected_document_ingestion_status`, `language`, `scenario_family`,
`evaluation_scope`, `ingestion_mode`, provenance `split`/`authoring_set`
— performed a bare `value in ALLOWED_SET` test with no `isinstance` check
first. Python's `in`/`not in` against a `set` hashes its operand before
comparing anything; a `list` or `dict` value is unhashable, so
`expected_stop_reason: []` on a label, or `split: []` on an
authoring-provenance entry, raised an unhandled `TypeError: unhashable
type: 'list'` — a genuine crash, not a validation error, and one that
§12a's own scalar-only test matrix (`12345`, `True`, `5.0`,
`"not-a-list"`, `999`) never exercised because every value in that matrix
was hashable.

**Fix:** eight reusable helpers (`is_non_empty_string`,
`safe_record_identifier`, `validate_string_field`, `validate_string_enum`,
`validate_optional_string_enum`, `validate_string_list`,
`validate_integer_field`, `validate_json_safe_value`) now enforce a strict
type-first order everywhere a field is checked: confirm the Python type
(rejecting `list`, `dict`, `bool`-where-not-wanted, and `None`-unless-
allowed) **before** any `in`/`not in`/dict-key/hash operation ever sees
the value. `validate_string_list` additionally validates every list
element's type individually, before any per-element enum check, and
reports the offending index (`field[i]`) instead of crashing on the first
unhashable element. `validate_integer_field` explicitly rejects `bool`
even though `isinstance(True, int)` is `True` in Python. Every downstream
check function that builds a `set`/`dict`/`Counter` from a field this
validation-order covers (`check_referential_integrity`,
`check_family_registry`, `check_language_coverage`,
`check_class_distribution`, `check_case_label_mapping`,
`check_no_duplicate_ids`, `check_cross_split_contamination`,
`find_v1_contamination_matches`, `check_no_orphan_documents`,
`check_no_cross_split_secret_reuse`,
`check_split_and_language_consistency`, `check_source_keys`,
`diagnose_against_current_guards`) was independently audited and given
its own local `isinstance` guard, so it remains individually crash-proof
even when called directly (as this file's negative-path tests do)
without first passing through `check_schemas`'s gate. `main()` retains a
final, last-resort `except Exception` boundary that prints a single
generic, non-traceback message and returns 1 if a truly unforeseen
exception still occurs — documented in-code as secondary only; the
type-first helpers above are the primary fix.

CLI-level regression coverage
(`tests/test_benchmark_v2_integrity.py`, "malformed-value (list/dict/
number/bool/null) handling" section) includes a parametrized matrix
across every corpus (17), case (17), label (26), and authoring-provenance
(16) field with a `list`/`dict` value; direct CLI reproductions of both
exact reported crashes; a combined multi-field malformed fixture; a
non-object provenance record (both direct-call and real-JSONL-line); a
deterministic-error-order check; and a confirmation the real, unmutated
candidate benchmark still passes end to end. See
`docs/modernization-ai-reviews/phase-12d-audit-resolution.md` ("Round 3")
for the full evidence.

## 13. Holdout policy

- Development: may be freely referenced while debugging the Phase 12E
  evaluation runner.
- Validation: may be referenced for limited threshold/config selection during
  Phase 12E, but is not the final reported number.
- Holdout: never referenced for guard development (none of `app/guards/*.py`
  was read *for the purpose of* authoring holdout content beyond what was
  needed to author development/validation instances of the same family in
  the same generator run — see §10-11's independence discussion); executed
  only once, in Phase 12E, after this freeze.
- Any edit to frozen content after this phase requires a new version (v3)
  and a new manifest — no silent mutation of `datasets/v2/` is permitted once
  `scripts/freeze_v2_benchmark.py freeze` has been run and committed.
- No runtime module (`app/**/*.py`) imports `datasets/v2/labels` or
  `datasets/v2/cases` (statically verified, §3).

## 14. Determinism, generation, and freeze

- **Seed:** `SEED = 1220126`, fixed and documented in
  `scripts/build_v2_benchmark.py`. Drives only cosmetic content selection
  (language rotation cycling, trigger-phrase-variant pool selection by case
  index) — case counts, IDs, splits, and expected outcomes are always fixed
  by the explicit `FAMILY_TABLE`, never randomized.
- **Determinism:** `python scripts/build_v2_benchmark.py --verify-determinism`
  builds the registry twice in memory and fails if the two JSON dumps differ
  (no files written by the check). Verified passing; also covered by
  `tests/test_benchmark_v2_integrity.py::test_deterministic_rebuild_is_byte_
  identical` and `test_verify_determinism_cli_flag_passes`.
- **Idempotent file output:** `_write_jsonl` writes with `ensure_ascii=False,
  sort_keys=True, newline="\n"` — re-running the build against an unchanged
  repository produces byte-identical files.
- **No network, no wall-clock content:** the generator has zero network
  imports (verified: `tests/test_benchmark_v2_integrity.py::
  test_scripts_contain_no_network_calls`) and embeds no timestamp in any
  generated record.

### Commands

```powershell
# Build (writes datasets/v2/corpus, cases, labels)
python scripts/build_v2_benchmark.py

# Verify the generator is deterministic (no files written)
python scripts/build_v2_benchmark.py --verify-determinism

# Validate schemas, counts, coverage, integrity, and contamination controls (guard-independent)
python scripts/validate_v2_benchmark.py

# Optional, non-gating: report agreement/disagreement with the CURRENT guard implementation
python scripts/validate_v2_benchmark.py --diagnose-current-guards

# Authoring-time freeze: write a CANDIDATE manifest
python scripts/freeze_v2_benchmark.py freeze

# Audit-gated finalization: write the FINAL manifest explicitly
python scripts/freeze_v2_benchmark.py finalize

# Verify the current tree against the frozen FINAL manifest (Phase 12E must run this first)
python scripts/freeze_v2_benchmark.py verify
```

### Manifest format

```json
{
  "manifest_version": 1,
  "benchmark_version": "v2",
  "manifest_status": "final",
  "file_count": 9,
  "files": [
    {"path": "cases/development.jsonl", "size_bytes": 12345, "sha256": "..."},
    ...
  ]
}
```

Paths are POSIX-relative to `datasets/v2/` (never absolute, never
machine-specific), sorted by path, with a 64-character lowercase hex SHA-256
digest per file. The manifest file itself is excluded from its own hash set
(`manifests/` is not scanned). No timestamp field exists in the manifest, so
`freeze` run twice against an unchanged tree produces a byte-identical
manifest file. The default `freeze` command continues to emit a candidate
manifest; only the explicit `finalize` command emits `manifest_status=final`.
Both modes cover the same nine paths and are deterministic.

### 14a. Manifest scope now covers every validation-policy artifact (Code X Phase 12D RE-AUDIT)

**What Code X found:** the candidate manifest covered only `corpus/`,
`cases/`, and `labels/`. `contamination-exemptions.json` — which can
*change benchmark meaning* by suppressing a contamination finding — sat
outside the manifest's integrity scope, and the new `design/authoring-
provenance.jsonl` artifact would have been in the same position.

**Fix:** `scripts/freeze_v2_benchmark.py`'s `ARTIFACT_SUBDIRS` now includes
`design/` (covering `authoring-provenance.jsonl`), and a new
`POLICY_FILES = ("contamination-exemptions.json",)` covers the one
top-level policy file outside any subdirectory. The candidate manifest now
covers exactly 9 files:

```
cases/development.jsonl        cases/holdout.jsonl        cases/validation.jsonl
labels/development.jsonl       labels/holdout.jsonl       labels/validation.jsonl
corpus/documents.jsonl
design/authoring-provenance.jsonl
contamination-exemptions.json
```

A mutation to `contamination-exemptions.json` or to `design/authoring-
provenance.jsonl` now fails `freeze_v2_benchmark.py verify` exactly like a
mutated `corpus`/`cases`/`labels` file — verified directly in this session
(mutate-each-artifact-in-turn, confirm `verify` fails, restore, confirm
`verify` passes again; see the audit-resolution document for the executed
output). Still excluded from the manifest's own hash set: the manifest
file itself (`manifests/`), and (as before) any machine-specific temp
file, generated log, or Phase 12E output — none of which exist under
`datasets/v2/` in the first place.

## 15. Known limitations

- **Synthetic corpus.** All 172 documents are hand-authored templates with
  per-case unique tokens, not sampled from any real enterprise document set
  or public red-team corpus. No claim of production-representativeness is
  made or should be inferred from any Phase 12E result.
- **Rule-based guard target only.** This benchmark evaluates a deterministic,
  rule-based multi-stage gateway. It is not a general-purpose prompt-
  injection benchmark and its results do not transfer to guard
  implementations using different detection mechanisms (e.g., a trained
  classifier or an LLM-based judge).
- **No real LLM.** The pipeline under test always uses `MockLLMProvider`, a
  fixed deterministic responder (see §8's construct-validity note). Real
  LLM stochasticity, partial compliance, and hallucination are not exercised
  by this benchmark at all.
- **No semantic retrieval.** Retrieval is SQLite FTS5/BM25 keyword matching.
  Cases are designed around lexical term overlap (shared `V2TOK#####`
  markers); a vector-embedding retriever would behave differently and is not
  evaluated here.
- **No production-representativeness claim.** Per `docs/modernization-v2-
  architecture.md`'s and ADR-003's own framing, any Phase 12E result must be
  reported as "filtered X% of this synthetic benchmark within the rule-based
  constraints," never as "prevents X% of real-world prompt injections."
- **Residual semantic/encoded/homoglyph/paraphrased bypasses.** `rag_guard`/
  `input_guard` match literal trigger phrases (with light zero-width/
  whitespace normalization). Paraphrased attacks, base64/hex-encoded
  payloads, and homoglyph substitution are known, out-of-scope bypasses —
  `fragment_beyond_per_chunk_prefix` and `compromised_trusted_source`
  explicitly document specific instances of this class as residual risk
  rather than falsely claiming detection.
- **Benchmark-author/guard-author overlap.** The same team that owns
  `app/guards/*.py` also authored this benchmark's trigger phrases, working
  from the guards' own rule tables (necessarily — labels have to state what
  the current implementation is expected to do). This is the exact
  construct-validity risk ADR-003 exists to bound: mitigated by (a) v2's
  holdout split being subject to independent multidisciplinary review before
  Phase 12E use (§11), and (b) v2 deliberately not reusing any v1 payload
  verbatim (§10-11), but not eliminated — a rule-author/benchmark-author who is
  the same person can still unconsciously favor phrasings their own rules
  already catch.
- **Near-duplicate detection limitations.** No semantic-similarity
  (embedding-based) dependency was added; §11's automated
  fingerprint-and-`difflib`-ratio checks now run on every rebuild and report
  zero cross-split contamination findings (superseding the original Phase
  12D pass's weaker "manual template read-through" claim, which Code X
  correctly identified as insufficient — see §10), but a lexical-similarity
  check still cannot catch a genuine paraphrase that shares no lexical
  substring pattern with anything in another split.
- **Bilingual/translation-detection lexicon coverage (§10a).** The
  benchmark-specific EN/VI phrase lexicon (~40 entries) catches an exact
  translation or a clause-level reordering of this benchmark's own
  recurring content concepts, verified by three concrete test scenarios,
  but it is not a translation model: a translation using phrasing outside
  the lexicon, or a reordering that splits a single lexicon phrase apart
  rather than reordering whole clauses, is not guaranteed to be caught.
  This is a deliberately narrow, benchmark-specific control, not a general
  semantic-duplicate detector — see §10a for the exact boundary and the
  concrete example found while building the required test fixtures.
- **Authoring-provenance naming overlap with the label schema (§10a).**
  The new `datasets/v2/design/authoring-provenance.jsonl` artifact and the
  existing per-case label both have a field called `semantic_group_id`,
  with deliberately different scoping rules (split-scoped in the
  provenance file vs. intentionally cross-split in the label). This is
  documented explicitly in §10a to prevent misreading one for the other;
  a future revision could rename one of the two fields to remove the
  ambiguity entirely, which was not done in this fix pass to avoid an
  unnecessary breaking change to the already-reviewed label schema.

## 16. Phase 12E usage boundary

Phase 12E, when it begins, is expected to: run `scripts/freeze_v2_benchmark.py
verify` first and abort before producing any report if it fails (ADR-003's
runtime-precondition requirement); execute all C0-C7 ablation observations via
the single internal `run_rag_query_uncommitted(..., guard_profile=...)` seam
(never short-circuit retrieval using `relevant_document_ids`); read
`labels/*.jsonl` only after receiving each actual result, to score it; and never
modify a guard rule in response to a holdout failure without treating the
holdout split as contaminated under ADR-003's Rule of Freezing.

This Phase 12E-specific rule **supersedes this section's former HTTP-only wording
for the ablation matrix**. The public `POST /v1/rag/query` endpoint remains
permanently `ALL_ON`, exposes no profile field/header/environment setting, and
is not an ablation executor. An optional C0 HTTP-versus-in-process parity smoke
may be reported separately, never mixed into matrix effectiveness or latency.
Consequently the matrix evaluates pipeline-layer behavior, not the FastAPI/
Pydantic perimeter on every run. None of that runner exists yet — Phase 12D
produces artifacts only.

## 17. Multidisciplinary audit closure

Before final closure, Phase 12D deliberately remained **IN REVIEW**, not
Done, throughout three Code X audit rounds:

- **Round 1** (`docs/modernization-ai-reviews/codex-phase-12d-benchmark-
  audit.md`): verdict REVISE, 2 Critical + 3 Major. Fixed: guard-
  independent validation; an initial split-independent content-authoring
  rewrite; an initial contamination/v1-comparison check (queries only);
  initial schema/enum completeness; label isolation and
  `evaluation_scope`; class-balance rework.
- **Round 2** (this document's current state, resolving the same audit
  document's re-audit pass — see `docs/modernization-ai-reviews/phase-12d-
  audit-resolution.md`): found Round 1's fixes were **partially** complete
  — Critical #2 (split independence) had no defense against an
  EN/VI translation using different self-declared group IDs; Major #1
  (validator completeness) still accepted a duplicate/non-string
  `external_id` and crashed with an unhandled `TypeError` on non-string
  `content`; the v1-comparison check never actually scanned corpus
  documents despite accepting one as a parameter; the candidate manifest
  did not cover `contamination-exemptions.json`. All four addressed this
  round: §10a (authoring provenance + bilingual canonicalization), §11
  (v1 document scanning), §12a (complete field types), §14a (manifest
  policy-artifact scope).
- **Round 3** (`docs/modernization-ai-reviews/phase-12d-audit-resolution.md`,
  "Round 3"): found Round 2's §12a field-type fix covered non-string
  scalars only — a `list`/`dict` value in an enum-field position
  (`expected_stop_reason=[]`, authoring-provenance `split=[]`) still
  raised an unhandled `TypeError: unhashable type` from a bare `value in
  ALLOWED_SET` test with no type check first. Fixed by making every
  enum/list/integer field's validation type-first across `check_schemas`
  and `check_authoring_provenance`, plus a defense-in-depth `isinstance`
  guard added to every downstream check function that builds a set/dict
  from a validated field: §12b.

All final gates have now passed against commit `4e10a2e`: Code X final
technical verification **PASS**, Gemini final academic audit **PASS**, and
Grok final red-team coverage audit **PASS**. Remaining Critical issues:
**None**. Remaining blocking Major issues: **None**. The manifest was then
produced through the explicit `finalize` path and covers the same nine
byte-identical artifacts as the audited candidate.

Final validation recorded **255 passed** across the three Phase 12D test
modules and **578 passed, 1 warning** across the complete repository suite.
The validator, six-file compile check, deterministic rebuild, FINAL manifest
verification, and mutation check against a temporary copy all passed.

Gemini's non-blocking statistical observation is accepted as a binding
Phase 12E reporting rule: percentage metrics may be reported at aggregate
or predeclared high-level grouped-family levels only when the group has
adequate support; individual-family outcomes are descriptive or qualitative.
Grok's recommended adversarial probes remain deferred to Phase 12E, and its
semantic-coordination and benign-over-redaction observations remain future
work. These points constrain future evaluation and do not require benchmark
regeneration.

**Final status: Phase 12D DONE; manifest FINAL; Phase 12E not started.** Any
later change to one of the nine frozen artifacts creates a new benchmark
version and requires fresh integrity checks and multidisciplinary review.
