# redteam/

Synthetic prompt-based attack test suite used to evaluate the gateway's Input Guard (and, for a few categories, RAG/Output Guard as a backstop). Complements the document-based poisoning fixtures in `datasets/poisoned/`.

**Status: Phase 3 — test suite populated.** No gateway or guard implementation exists yet (Phase 4–6 build the code; Phase 7 builds the runner that will execute this suite). This directory currently contains data/design artifacts only.

## Purpose

Provide a **controlled, categorized benchmark of 40 synthetic red-team prompts** (plus a 5-state expected-behavior taxonomy) that a future evaluation runner (Phase 7) will send through the gateway to measure detection quality (ASR, Block Rate, FPR, FNR — see `docs/evaluation/metrics-definition.md`).

## Contents

| File | Purpose |
|---|---|
| `prompts.jsonl` | 40 test-case records, one JSON object per line, across 8 categories (5 each). |
| `expected-behaviors.yaml` | Canonical definition of the 5 possible guard decisions (`allow`, `block`, `sanitize`, `log_only`, `human_review`). |
| `attack-categories.md` | Explains every category (definition, attack goal, expected response, example IDs) for both this file and `datasets/poisoned/`. |

## `prompts.jsonl` Schema

One JSON object per line (JSON Lines format). Fields:

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Unique test-case ID, e.g. `RT-INJ-DIRECT-001`, following the convention in `docs/evaluation/red-team-test-design.md` §6. |
| `category` | string | One of: `benign`, `direct_prompt_injection`, `role_override`, `instruction_hierarchy_attack`, `jailbreak`, `sensitive_extraction`, `rag_context_manipulation`, `tool_action_misuse`. |
| `prompt` | string | The literal synthetic test prompt text. |
| `expected_behavior` | string | Human-readable description of the correct assistant behavior. |
| `expected_decision` | string | One of the 5 keys in `expected-behaviors.yaml`: `allow` / `block` / `sanitize` / `log_only` / `human_review`. |
| `target_guard` | string | Which guard(s) are primarily responsible: `input_guard`, `rag_guard`, `output_guard`, `gateway`, or a `+`-joined combination (e.g. `input_guard+rag_guard`). |
| `notes` | string | Rationale, cross-references, or caveats for evaluators. |

### Category breakdown (5 each, 40 total)

`benign` · `direct_prompt_injection` · `role_override` · `instruction_hierarchy_attack` · `jailbreak` · `sensitive_extraction` · `rag_context_manipulation` · `tool_action_misuse`

The `benign` category exists specifically to measure **False Positive Rate** — it is not filler; a guard that blocks any benign prompt is failing.

## Expected Behavior Labels

Defined in full in `expected-behaviors.yaml`; summary:

| Label | Meaning |
|---|---|
| `allow` | No issue found; request proceeds unmodified. |
| `block` | Clear violation; pipeline halts, safe refusal returned. |
| `sanitize` | Partial issue; offending portion stripped, rest proceeds. |
| `log_only` | Low/ambiguous signal; proceeds like `allow` but flagged for review. |
| `human_review` | High-severity but ambiguous; MVP treats this like `block` with a distinct reason code (no live human-review queue exists yet — future thesis scope). |

## Rules (per `AGENT_RULES.md`)

- All content is **synthetic** and **original** — no real PII, no real secrets, no verbatim copies of third-party datasets.
- Every prompt targets **only this project's own (not-yet-built) lab-scale gateway** — never phrased against a real third-party system.
- Jailbreak/tool-misuse prompts are kept **illustrative, not operational** — enough to exercise a guard decision, not a working exploit or malware recipe.
- Every test case is traceable to a STRIDE row in `docs/diagrams/threat-model.md` via `docs/evaluation/red-team-test-design.md`.

## How the Future Guardrail Evaluation Will Use This (planned, Phase 7 — not implemented)

1. A batch runner (planned under `scripts/`, not yet built) will read `prompts.jsonl` line by line and send each `prompt` through the gateway.
2. The runner records the guard's **actual** decision, reason code, and response time.
3. Actual decision is compared against `expected_decision` to classify the case as a true positive, true negative, false positive, or false negative, per the mapping in `docs/evaluation/red-team-test-design.md` §5.1.
4. Results are aggregated into the metrics defined in `docs/evaluation/metrics-definition.md` (ASR, Block Rate, FPR, FNR, Latency Overhead, Reason Logging Completeness) and reported per category, not just as one blended number.

**No such run has happened yet.** Every field in `prompts.jsonl` is a design-time expectation, not a measured result.

## Related Documents

- `docs/evaluation/red-team-test-design.md` — original design rationale for this suite (7 prompt categories were originally designed there; `tool_action_misuse` was included as the optional 8th category with a full 5 prompts).
- `docs/evaluation/evaluation-plan.md` — baseline-vs-guarded methodology this suite will be run under.
- `datasets/poisoned/` — the companion document-based (non-prompt) attack benchmark.
