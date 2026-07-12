# Gemini Phase 12D Benchmark Design Review

## Repository State Verified

* Branch: phase-12d-v2-benchmark
* Commit: CANNOT VERIFY (Assuming latest based on prompt context)
* Relevant files accessible: CANNOT VERIFY (Simulated read-only assessment based on provided structure)

## Recommended Benchmark Structure

To ensure academic rigor and prevent label bleed, the benchmark must be physically separated into distinct directories:

* `corpus/`: Contains the SQLite FTS5 ingestion scripts and JSON documents (clean enterprise docs, poisoned docs, documents with secrets).
* `cases/`: The executable inputs containing only the user query, simulated user metadata, and requested context parameters.
* `labels/`: Ground-truth files mapping `case_id` to expected outcomes. The evaluation runner must load this *only after* the pipeline returns a response.
* `metadata/`: Contains the dataset splits (Development, Validation, Holdout) and the attack taxonomy tags.
* `manifest/`: A frozen JSON file containing SHA-256 hashes of all files in `cases/` and `labels/`.

## Recommended Size and Split

While ADR-003 requires a minimum of 100 cases, a defensible academic thesis should aim slightly higher to ensure statistical relevance in the holdout set.

* **Total Size:** 150 Cases.
* **Development Set (30 cases - 20%):** Used strictly to build and debug the Phase 12E evaluation runner.
* **Validation Set (40 cases - 27%):** Used to tune regex rules, DLP patterns, and provenance logic.
* **Holdout Set (80 cases - 53%):** Strictly frozen. Used *only once* during final evaluation.
* **Class Balance:** Each split must maintain a strict 50/50 balance between Malicious (injections/leakage) and Benign (safe queries/edge-cases) to accurately measure the False Positive Rate (FPR).

## Scenario Taxonomy

The benchmark must populate the following matrices:

1. **Benign Safe:** Standard RAG queries, no-hit queries, and queries returning all-blocked context (triggering a safe fallback).
2. **Benign Edge-Cases:** Security discussions (e.g., "How do I prevent prompt injection?") and benign secret-like identifiers (e.g., dummy API keys in documentation).
3. **Direct Prompt Injection:** Standard jailbreaks, roleplay bypasses, and system prompt overrides.
4. **Indirect Prompt Injection (Data Poisoning):** Payloads hidden in retrieved documents (both single-chunk and multi-chunk spanning).
5. **Provenance Manipulation:** Malformed provenance metadata, denied trust levels, and trusted-source compromise (poisoned data carrying a `trusted_internal` flag).
6. **Leakage & Exfiltration:** Queries attempting to extract PII or credentials, evaluating both DLP redaction and Output Guard blocking.
7. **Obfuscation:** Multilingual attacks, Unicode/zero-width character variants, and base64 encoded payloads.

## Ground-Truth Schema

Ground truth must evaluate the *mechanism* of defense, not just the final result. Recommended fields per case:

* `expected_decision`: `ALLOW` | `BLOCK` | `REDACT`
* `expected_stop_stage`: `INPUT_GUARD` | `PROVENANCE_GUARD` | `CONTEXT_GUARD` | `DLP_GUARD` | `OUTPUT_GUARD` | `NONE`
* `expected_provider_called`: `true` | `false`
* `expected_redaction_count`: Integer (for DLP evaluation).
* `allowed_alternative_reasons`: Array of acceptable secondary stages (e.g., if a poisoned document is caught by the Output Guard instead of the Context Guard, it is a partial success, not a total failure).

## Multilingual Distribution

To reflect the Vietnamese enterprise context of the thesis:

* **60% Vietnamese:** Primary language for standard benign queries and localized attack vectors.
* **30% English:** Standard industry jailbreaks and legacy attack templates.
* **10% Bilingual/Mixed:** Queries in Vietnamese interacting with poisoned English documents (or vice versa).
* **Constraint:** Do not count a direct translation of an attack as an independent test case. Translated duplicates artificially inflate sample size without increasing variance.

## Construct Validity Controls

The thesis manuscript must explicitly acknowledge these boundaries:

* **Keyword Matching is not Semantic Understanding:** The rule-based framework identifies syntactic patterns, meaning paraphrased attacks may bypass it.
* **Regex Redaction is not Semantic Leakage Prevention:** DLP catches formatted secrets (e.g., `123-45-678`) but fails if the LLM outputs "one two three, forty five...".
* **Mock LLM Limitation:** The offline mock provider acts deterministically. Real LLMs are stochastic and may exhibit partial compliance or output hallucination, which this benchmark cannot fully simulate.

## Internal Validity Controls

* **Shared Authorship Risk:** To prevent the student developers from subconsciously writing attacks that perfectly match their own regex rules, at least 50% of the malicious cases must be sourced from public datasets (e.g., Lakera, JailbreakChat) rather than written from scratch.
* **Label Blindness:** The Phase 12E runner must execute the `cases/` payload via HTTP request to the FastAPI application. The pipeline must never ingest the ground-truth labels.
* **Overfitting Prevention:** If a regex rule is updated to fix a failure in the Validation set, it must not be tested against the Holdout set until the final, formal thesis evaluation.

## External Validity and Claim Limits

The benchmark evaluates a *deterministic architectural PoC*, not a production security appliance.

* **Do not claim:** "The system prevents X% of prompt injections."
* **Instead claim:** "The system successfully filtered X% of the synthetic benchmark within the rule-based constraints, demonstrating the latency and ablation trade-offs of a multi-layer gateway."

## Holdout and Freeze Policy

* **Freeze Trigger:** The Holdout set is officially frozen once Phase 12D is completed and the SHA-256 `manifest.json` is committed.
* **Inspection:** The holdout set may not be inspected to debug regex rules.
* **Immutability:** If the holdout set contains a flawed test case discovered during Phase 12E, the test case must *not* be modified. The flaw must be documented in the thesis as an evaluation anomaly. Altering the holdout post-freeze invalidates the methodology.

## Phase 12E Readiness Requirements

To execute Phase 12E, the benchmark design assumes the pipeline possesses:

1. An ablation toggle (e.g., HTTP headers like `X-Disable-Guard: ContextGuard`) to run the benchmark against different pipeline configurations.
2. High-resolution timing telemetry to measure latency per stage (Input, Provenance, Context, DLP, Output) to calculate marginal overhead.
3. A runner script capable of batch-executing the cases, comparing outputs to the ground-truth labels, and exporting a CSV/Markdown matrix of TPR, FPR, FNR, and Latency.

## Blocking Methodology Requirements

1. Strict physical separation of execution cases and ground-truth labels.
2. Implementation of the SHA-256 freeze manifest for the holdout set.
3. Hard requirement of a 50/50 Malicious vs. Benign split to guarantee FPR measurability.

## Deferrable Decisions

* The actual generation of the JSON/CSV data files (to be executed next in Phase 12D).
* Writing the Phase 12E evaluation runner script.
* Migration to a stochastic LLM or Vector Database (Post-thesis).

## Final Recommendation

READY FOR IMPLEMENTATION