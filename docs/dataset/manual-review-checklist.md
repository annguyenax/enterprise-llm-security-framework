# Manual Review Checklist

> A checklist a human team member should apply to **every** item in `datasets/clean/`, `datasets/poisoned/`, and `redteam/prompts.jsonl` before the benchmark is considered "reviewed" rather than just "automatically validated." See `docs/dataset/dataset-validation-report.md` for what has already been checked by script, and `docs/dataset/source-mapping.md` for the per-item `Review Status` column this checklist feeds into.

## How to use this checklist

For each of the 50 items (10 documents + 40 prompts), a reviewer should be able to check every box below. If any box cannot be checked, the item should be flagged in `docs/dataset/source-mapping.md` (change `pending` to `flagged: <reason>`) rather than silently passed.

## Checklist Items

- [ ] **Synthetic-only data.** The item contains no reference to any real organization other than the fictional "Northwind Retail Group" (and its fictional sub-entities: "Aurora Widget" product, "ServiceDesk Pro" tool).
- [ ] **No real PII.** No real person's name, email, phone number, address, or other identifying data appears anywhere in the item.
- [ ] **No real credentials.** No real API key, password, token, or credential appears; any "secret-like" string is exactly `FAKE-SECRET-0000-EXAMPLE` (or an explicitly-labeled variant of it) and cannot be mistaken for a real vendor key format.
- [ ] **No real company secrets.** No item describes a real company's actual internal process, system name, or confidential information.
- [ ] **Clear category label.** The item's `category` (prompts) or `attack_type` (poisoned documents) is present and matches one of the categories defined in `redteam/attack-categories.md`.
- [ ] **Expected decision defined.** The item's `expected_decision` (prompts) or `expected_guard_decision` (poisoned documents) is present and is one of the 5 canonical values in `redteam/expected-behaviors.yaml` (`allow`/`block`/`sanitize`/`log_only`/`human_review`). Clean documents' expected `allow` behavior is stated in prose ("Notes for RAG Ingestion") rather than a front-matter field — this is acceptable since clean documents have only one possible expected value.
- [ ] **Target guard defined.** The item's `target_guard` is present and is composed only of the 4 canonical guard names (`input_guard`, `rag_guard`, `output_guard`, `gateway`), optionally `+`-joined.
- [ ] **Safe enough for academic demo.** The item does not contain a fully operational exploit, malware, or step-by-step real-world attack instructions — it is illustrative enough to exercise a guard decision without teaching real abuse (per this project's quality rules).
- [ ] **Mapped to threat model or a recognized LLM risk category.** The item's risk basis traces to a row in `docs/diagrams/threat-model.md` and/or a category in `docs/research/owasp-llm-top10-mapping.md`, as recorded in `docs/dataset/source-mapping.md`.
- [ ] **Human reviewer status recorded.** A specific team member's name and review date is recorded once reviewed (not just "pending" indefinitely) — see the tracking table in §2 below.
- [ ] **Limitation noted, if any.** If the item is a deliberately ambiguous/borderline case (e.g., has an `acceptable_alternate_decision`), this is explicitly noted rather than presented as an unambiguous ground truth.

## §1. Category-Level Pre-Checks (already performed by the automated pass — see validation report)

These do not need to be re-checked item-by-item by a human, since they were already verified programmatically for all 50 items in `docs/dataset/dataset-validation-report.md`:

- JSONL parses without error; no duplicate IDs; no missing required fields; `expected_decision`/`target_guard` values belong to the canonical sets.
- Front-matter of every clean/poisoned document parses; `document_id` values are unique; `based_on_clean_doc` cross-references resolve to an actual clean document.
- No occurrence of realistic secret-key prefixes (`sk-`, `AKIA`, `ghp_`, PEM headers) anywhere in `datasets/` or `redteam/`.
- No occurrence of well-known real company names anywhere in `datasets/` or `redteam/`.

## §2. Human Reviewer Sign-Off Tracking

| Reviewer | Items reviewed | Date | Outcome |
|---|---|---|---|
| _(none yet)_ | _(none yet)_ | _(none yet)_ | **Not started** — no team member has performed a full manual read-through against this checklist yet. |

This table should be updated as team members complete reviews. Until at least one row is filled in, `docs/dataset/source-mapping.md`'s `Review Status` column should remain `pending` for all 50 items — this is the honest current state as of the Phase 3.1 review, not an oversight.

## §3. What "Reviewed" Does Not Mean

Per `docs/dataset/dataset-methodology.md` §6–7: even a fully checked-off item does not mean the corresponding guard behavior has been *implemented* or *measured*. This checklist is about the **trustworthiness of the test-case definition itself** (is it safe, well-labeled, and correctly mapped to a risk category) — not about whether any guard actually produces the expected decision. That is Phase 4–7 work.
