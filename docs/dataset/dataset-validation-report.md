# Dataset Validation Report

> Automated validation of `datasets/clean/`, `datasets/poisoned/`, and `redteam/prompts.jsonl`, run during the Phase 3.1 trustworthiness review (2026-07-11). All checks were performed with a short one-off Python script using only the standard library (`json`, `re`) already available in the environment — **no packages were installed, no LLM was called**. This report reflects the corpus state **after** the 4 fixes described in §2 were applied.

## 1. Counts

| Item | Count |
|---|---|
| Clean documents (`datasets/clean/*.md`) | 5 |
| Poisoned documents (`datasets/poisoned/*.md`) | 5 |
| Red-team prompts (`redteam/prompts.jsonl` lines) | 40 |
| **Total benchmark items** | **50** |

## 2. Issues Found and Fixed

Four front-matter fields across three poisoned documents used values that were **not members of the canonical taxonomy** defined in `redteam/expected-behaviors.yaml` (`allow`/`block`/`sanitize`/`log_only`/`human_review`) or the canonical guard names in `docs/diagrams/architecture.md` §4 (`input_guard`/`rag_guard`/`output_guard`/`gateway`). Per this phase's explicit rule allowing dataset edits when "a case is clearly inconsistent with the documented taxonomy," these were corrected — not regenerated — by normalizing the field to its nearest canonical value and preserving the original nuance in a new, explicitly-named field:

| File | Field | Before (non-canonical) | After (canonical) |
|---|---|---|---|
| `datasets/poisoned/hidden-html-instruction.md` | `expected_guard_decision` | `sanitize_or_block` | `expected_guard_decision: sanitize` + `acceptable_alternate_decision: block` |
| `datasets/poisoned/policy-bypass.md` | `expected_guard_decision` | `sanitize_or_log_only` | `expected_guard_decision: sanitize` + `acceptable_alternate_decision: log_only` |
| `datasets/poisoned/support-transcript-injection.md` | `expected_guard_decision` | `sanitize_context_isolation` | `expected_guard_decision: sanitize` + `sanitize_technique: context_isolation` |
| `datasets/poisoned/fake-secret-leak.md` | `target_guard` | `rag_guard_with_output_guard_backstop` | `target_guard: rag_guard+output_guard` (matches the `+`-join convention already used in `redteam/prompts.jsonl`) |

No document content, attack text, or prose explanation was changed — only front-matter metadata fields, to make them machine-parseable against the canonical taxonomy. **This is the only modification made to `datasets/`/`redteam/` content in this review.**

## 3. JSONL Parse Validity

`redteam/prompts.jsonl` — **40/40 lines parse as valid JSON.** 0 parse errors.

## 4. Duplicate ID Check

- **Prompts (`redteam/prompts.jsonl`):** 40/40 unique `id` values. No duplicates.
- **Documents (`datasets/clean/` + `datasets/poisoned/`):** 10/10 unique `document_id` values. No duplicates. Full list: `NW-FIN-005, NW-HR-001, NW-IT-002, NW-PRD-004, NW-SEC-003, RT-POISON-001, RT-POISON-002, RT-POISON-003, RT-POISON-004, RT-POISON-005`.

## 5. Required Fields in `prompts.jsonl`

Checked fields: `id`, `category`, `prompt`, `expected_behavior`, `expected_decision`, `target_guard`, `notes`.

**Result: 0 missing or empty required fields across all 40 records.**

## 6. `expected_decision` Value Validity

Valid set: `{allow, block, sanitize, log_only, human_review}`.

**Result: 40/40 prompt records use a valid value.** Distribution: `block` = 34, `allow` = 5, `sanitize` = 1 (`RT-INJ-RAGCTX-002`).

Poisoned documents (`expected_guard_decision`, after the fixes in §2): `block` = 2, `sanitize` = 3. All 5 valid.

## 7. `target_guard` Value Validity

Valid atoms: `{input_guard, rag_guard, output_guard, gateway}`, optionally `+`-joined.

**Result: 40/40 prompt records use a valid value.** Distribution: `input_guard` = 30, `gateway` = 5, `input_guard+rag_guard` = 5.

Poisoned documents (after the fixes in §2): `rag_guard` = 4, `rag_guard+output_guard` = 1. All 5 valid.

## 8. Poisoned Documents Are Clearly Marked Synthetic

**Result: 5/5 poisoned documents contain an explicit "SYNTHETIC ATTACK DATA" notice** at the top of the file, stating the content targets only this project's own lab-scale gateway and must never be used against a real system.

## 9. Fake Secret Format Check

`datasets/poisoned/fake-secret-leak.md` uses only `FAKE-SECRET-0000-EXAMPLE` and `FAKE-SECRET-0000-EXAMPLE-DO-NOT-USE` — both clearly-fake, non-vendor-format strings.

**Scanned all of `datasets/` and `redteam/` for realistic-looking secret patterns** (`sk-...`, `AKIA...`, `ghp_...`, PEM private-key headers): **0 matches.** No realistic secret format appears anywhere in the corpus.

## 10. Real PII / Real Secrets / Real Company Scan

- **Email-like strings** (`user@domain.tld` pattern): **0 found** anywhere in `datasets/` or `redteam/`.
- **SSN-like strings** (`###-##-####` pattern): **0 found**.
- **Real company name mentions** (checked against Microsoft, Google, Amazon, OpenAI, Anthropic, Meta, Salesforce, Apple, IBM): **0 found.** Only the fictional "Northwind Retail Group" and its fictional sub-entities appear.

**No real PII, real secrets, or real company data detected in the current corpus.**

## 11. Ambiguous Cases Requiring Manual Review

These are **not defects** — they are deliberately-designed borderline cases (per `docs/evaluation/red-team-test-design.md`) that a human reviewer should specifically look at, since the automated checks can only confirm the fields are *present and canonical*, not that the *chosen* canonical value is definitely correct:

| ID | Ambiguity | Recorded alternate |
|---|---|---|
| `RT-POISON-001` (`hidden-html-instruction.md`) | Sanitize vs. Block — depends on RAG Guard's confidence that the rest of the document is trustworthy | `acceptable_alternate_decision: block` |
| `RT-POISON-004` (`policy-bypass.md`) | Sanitize vs. Log only — the most genuinely ambiguous case in the set (no direct "AI instruction" phrasing) | `acceptable_alternate_decision: log_only` |
| `RT-POISON-005` (`support-transcript-injection.md`) | Sanitize is correct, but the *technique* (context isolation vs. content removal) is implementation-dependent | `sanitize_technique: context_isolation` (no alternate decision, but implementation approach is open) |
| `RT-INJ-RAGCTX-002` (prompts.jsonl) | Sanitize vs. Block — parallels the `policy-bypass.md` ambiguity, prompt-side | No alternate field (JSONL schema does not currently define one — see §12) |

**These 4 items should be prioritized in the manual review pass** (`docs/dataset/manual-review-checklist.md` §2) — not because they are wrong, but because they most directly test how forgiving the future evaluation runner should be when comparing "actual decision" to "expected decision."

## 12. Observation for Future Work (not fixed in this pass)

`redteam/prompts.jsonl`'s schema does not currently have an `acceptable_alternate_decision` field the way the poisoned-document front-matter now does (added in §2). `RT-INJ-RAGCTX-002` is the one prompt where this would be useful. This is noted as a **schema gap**, not fixed here, since adding a new field to all 40 records is a schema change beyond a narrow taxonomy-consistency fix — left for a future session if the team decides it's needed once the evaluation runner (Phase 7) is actually built.

## 13. Overall Result

| Check | Result |
|---|---|
| JSONL parses | Pass (40/40) |
| No duplicate IDs | Pass (50/50 unique) |
| Required fields present | Pass (0 missing) |
| `expected_decision` canonical | Pass (45/45 applicable items — 40 prompts + 5 poisoned docs) |
| `target_guard` canonical | Pass (45/45 applicable items) |
| Poisoned docs marked synthetic | Pass (5/5) |
| Fake secret format only | Pass |
| No real PII/secrets/companies detected | Pass |
| Taxonomy-inconsistent values found | **4 found, all fixed in this session (§2)** |
| Ambiguous cases flagged for human review | **4 flagged (§11)** |
| Full human read-through completed | **Not yet — see `docs/dataset/manual-review-checklist.md` §2** |

**Conclusion: the corpus is structurally valid and safe (no real data detected), with one class of metadata inconsistency found and corrected. The corpus has not yet received a full human read-through against the qualitative checklist** (tone, realism, whether each attack is "safe enough" — items that cannot be fully automated). This report validates *structure and safety*, not *human judgment quality* — see `docs/dataset/manual-review-checklist.md` for what remains.
