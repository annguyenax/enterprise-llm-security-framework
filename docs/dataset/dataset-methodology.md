# Dataset Methodology

> Explains *why* this project's synthetic enterprise benchmark (`datasets/`, `redteam/`) is built the way it is, what it can and cannot prove, and how it stays trustworthy despite being AI-assisted. This is a methodology document, not a results document — no guard exists yet to run this data against (see `TASK_BOARD.md`).

## 1. Why Real Enterprise Data Is Not Used

- **Legal/consent:** The team has no data-sharing agreement, NDA, or consent from any real organization to use its documents, policies, or employee data. Using real data without such an agreement would be a legal and ethical violation, independent of this being a student project.
- **Privacy:** Real enterprise documents (HR policies, IT tickets, finance records) routinely contain real PII (names, emails, salaries, leave balances). There is no way to use them without either exposing real people's data or spending significant effort anonymizing them — effort that would not improve the actual research question (does the guard detect the *pattern*, not whose *name* is in the document).
- **Reproducibility for grading:** A supervisor or reviewer needs to be able to inspect every test case without requesting access to a real company's internal systems. Synthetic data ships with the repository and is inspectable by anyone.
- **Rule alignment:** `AGENT_RULES.md` rule 5 explicitly requires synthetic-only data for this project; rule 7 explicitly forbids payloads crafted against real systems. This methodology exists to operationalize those two rules, not to introduce a new constraint.

## 2. Why Controlled Synthetic Data Is Acceptable for This Project

The research question this MVP investigates is **"does a rule-based guard pipeline correctly classify a known attack pattern embedded in enterprise-style content?"** — not **"what fraction of real Northwind-style companies get attacked this way?"**. For the first question, a *realistic-shaped* but *fully synthetic* corpus is sufficient and arguably preferable:

- The team controls every variable (document structure, exact attack phrasing, exact expected outcome), which is necessary to compute clean detection metrics (`docs/evaluation/metrics-definition.md`).
- Every clean/poisoned document pair is deliberately near-identical except for the injected attack (see `docs/dataset/source-mapping.md`), isolating the guard's sensitivity to the attack itself rather than to incidental document differences — something a scraped real-world corpus could not guarantee.
- This is explicitly a **lab-scale proof-of-concept** (`docs/decisions/ADR-001-mvp-scope.md`), not a claim about real-world attack prevalence. Section 6 below states plainly what this dataset cannot prove.

## 3. AI-Assisted Generation vs. Trusted Ground Truth

Parts of this benchmark's initial text (document wording, prompt phrasing) were drafted with AI assistance across several working sessions (Phase 2.5 design, Phase 3 materialization). **AI-drafted text is not treated as ground truth.** Concretely:

- The **taxonomy** (5 decision states in `redteam/expected-behaviors.yaml`; 8 prompt categories + 5 poisoning categories in `redteam/attack-categories.md`) is the actual ground truth artifact — it was designed against the project's own threat model (`docs/diagrams/threat-model.md`) and OWASP/LLMSVS mapping (`docs/research/owasp-llm-top10-mapping.md`, `docs/research/llmsvs-checklist.md`), not invented ad hoc by an AI session.
- Every individual test case's `expected_decision`/`expected_guard_decision` was assigned by **applying that taxonomy**, not by asking an AI "what should happen here" and accepting the answer directly.
- A validation pass (`docs/dataset/dataset-validation-report.md`) was run specifically to catch AI-introduced inconsistencies — and did: several poisoned documents originally had `expected_guard_decision` values (e.g., `sanitize_or_block`) that were not valid members of the 5-state taxonomy. These were corrected to the canonical taxonomy value plus an explicit `acceptable_alternate_decision` field where genuine ambiguity exists, rather than silently left as free-text.
- No claim in this dataset about "real-world" attack effectiveness, prevalence, or citation is made anywhere — see `AGENT_RULES.md` rule 3 (no fabricated results) and rule 2 (no fabricated citations).

## 4. Human Review Process

See `docs/dataset/manual-review-checklist.md` for the itemized checklist and `docs/dataset/source-mapping.md` for the per-case review status column. Summary of the process used so far:

1. **Automated validation** (this session): JSONL parses, front-matter parses, no duplicate IDs, all `expected_decision`/`target_guard` values belong to the canonical taxonomy, no missing required fields, no realistic-looking secret formats. Full results in `docs/dataset/dataset-validation-report.md`.
2. **Taxonomy-consistency fixes**: 4 front-matter fields across 3 poisoned documents were corrected in this session (documented in the validation report) because they used non-canonical decision/guard values — this is a narrow, targeted fix, not a regeneration of the dataset.
3. **Outstanding — team member read-through**: no team member has yet read every one of the 50 dataset items (10 documents + 40 prompts) end-to-end against the checklist below. This is recorded honestly as `human_reviewer_status: pending` in `docs/dataset/source-mapping.md` for every row, and is listed as a manual-review item, not silently assumed done.

## 5. How Test Cases Map to OWASP/NIST-Style Risk Categories and the Project Threat Model

Every case in this benchmark traces to a specific row in the project's own threat model, which is itself informed by (but not a direct copy of) recognized external frameworks:

| Benchmark category | Threat model row (`docs/diagrams/threat-model.md`) | OWASP LLM Top 10 category (`docs/research/owasp-llm-top10-mapping.md`) |
|---|---|---|
| `direct_prompt_injection`, `role_override`, `instruction_hierarchy_attack`, `jailbreak` | Elevation of Privilege | Prompt Injection |
| `sensitive_extraction` | Information Disclosure | Sensitive Information Disclosure |
| `rag_context_manipulation`, document poisoning categories (B1–B5 in `redteam/attack-categories.md`) | Tampering (and Spoofing for ingestion-time cases) | Prompt Injection (indirect) / Training Data Poisoning (relabeled as RAG document poisoning per ADR-001) |
| `tool_action_misuse` | Elevation of Privilege (structurally out of scope — no tool-use in MVP) | Insecure Plugin Design / Excessive Agency (both explicitly out of MVP scope) |

The project's lightweight internal checklist (`docs/research/llmsvs-checklist.md`) loosely draws on OWASP LLMSVS's architecture/operation control areas — this dataset is designed to exercise exactly the checklist items under "Input Guard" and "RAG Guard" in that document. No claim of LLMSVS compliance is made; see that document's own scope-honesty note.

## 6. What This Dataset Can Prove (once a guard exists)

- Whether a specific guard implementation's decision **matches the documented expected decision** for each of the 50 controlled cases.
- Aggregate detection-quality metrics on **this specific corpus**: ASR, Block Rate, FPR, FNR (`docs/evaluation/metrics-definition.md`).
- Whether a guard change (e.g., a new heuristic rule) improves or regresses performance on a **fixed, versioned, reproducible** test set — i.e., regression testing.
- Whether the logging subsystem completely and correctly records the reason for every decision (Reason Logging Completeness).

## 7. What This Dataset Cannot Prove

- **Real-world attack prevalence or severity.** This dataset says nothing about how often real attackers use these patterns, or how damaging a successful attack would be in a real enterprise.
- **Generalization to unseen attack phrasing.** 40 prompts and 10 documents cannot demonstrate robustness against the space of possible attack phrasings; a guard could overfit to this exact wording and still fail on a rephrased attack.
- **Adversarial robustness against an adaptive attacker.** All cases are static, single-turn, and known in advance — there is no red-team loop where an attacker adapts to the guard's behavior (multi-turn/adaptive attacks are explicitly out of scope; see `docs/evaluation/red-team-test-design.md` §7).
- **Comparison to commercial/production guardrail products.** No commercial tool has been run against this same corpus (see `docs/research/tool-comparison.md` — the 5 surveyed tools have not been installed or tested).
- **Statistical significance.** With only 50 total cases, any percentage reported later (Phase 7) should be read as descriptive of this fixed set, not as a statistically powered estimate (`docs/evaluation/metrics-definition.md` §9).

## 8. Dataset Limitations (known, as of this review)

- English-only; no non-English test cases (explicitly noted as a gap in `docs/evaluation/red-team-test-design.md` §7).
- Single-turn only; no gradual/multi-turn jailbreak sequences.
- Small sample size (5 clean docs, 5 poisoned docs, 40 prompts) — a lab-scale benchmark, not an industry-scale one, consistent with the project's MVP scope (`docs/decisions/ADR-001-mvp-scope.md`).
- Two categories (`benign`, and the 5 clean documents) intentionally dominate the "should never be flagged" side less than the attack side dominates the "should be flagged" side (5 benign prompts + 5 clean docs = 10 negative cases vs. 35 attack prompts + 5 poisoned docs = 40 positive cases) — this asymmetry should be kept in mind when interpreting aggregate metrics; FPR and ASR/FNR are computed on different denominators specifically to avoid this imbalance distorting a single blended score (`docs/evaluation/metrics-definition.md`).
- A handful of cases are intentionally ambiguous (`policy-bypass.md`, `hidden-html-instruction.md`) to test the `sanitize`/`log_only`/`block` boundary — these are flagged with `acceptable_alternate_decision` rather than a single rigid answer, and should not be graded as strictly right/wrong by an automated runner without accounting for the alternate.

## 9. Reproducibility and Safety Rules

- Every file in `datasets/` and `redteam/` is plain text (Markdown with YAML-style front matter, or JSON Lines/YAML) checked into the repository — no external downloads, no generation-at-runtime, no dependency on a live LLM call to reconstruct the corpus.
- **Synthetic-only, enforced structurally:** every document/prompt either uses the fictional "Northwind Retail Group" (and its fictional product "Aurora Widget" / fictional tool "ServiceDesk Pro"), or is a generic security-test prompt with no company reference at all.
- **Fake secrets use one fixed format only:** `FAKE-SECRET-0000-EXAMPLE` (see `docs/dataset/dataset-validation-report.md` for the confirmation scan) — never a realistic vendor-key format.
- **Versioning:** any future change to `datasets/` or `redteam/` content should be treated as a new corpus version; evaluation reports (Phase 7) must cite which version they ran against (`docs/evaluation/metrics-definition.md` §8) — this document set is the "freeze point" referred to in the Phase 3.1 title.
- No packages were installed and no LLM API was called to produce this document or the validation/fix pass in this session — validation used only Python's standard library (`json` module) already available in the environment.
