# Tool & Framework Comparison

> Status: **Phase 1 in progress.** Guardrail/red-teaming tool entries below originate from an AI-assisted research pass (`docs/research/raw/gemini-phase-1-research.md`), cross-checked by Claude via live web search on 2026-07-11 to confirm each tool/project actually exists. Any performance number attributed to a vendor is that vendor's **own unverified claim**, not a number this project has measured — per `AGENT_RULES.md` rule 3, this project's own benchmark numbers only ever come from an actual reproducible test run in this repo, which has not happened yet (Phase 7).

## Purpose

Compare candidate tools/frameworks for each layer of the planned architecture before locking decisions in via ADRs.

## RAG Orchestration Framework

| Framework | Pros (to verify) | Cons (to verify) | Notes |
|---|---|---|---|
| LlamaIndex | | | Decision deferred — see `docs/decisions/ADR-001-mvp-scope.md`. Not covered by the Phase 1 Gemini research pass; still Future Work. |
| LangChain | | | Decision deferred. Not covered by the Phase 1 Gemini research pass; still Future Work. |

## Vector Store

| Store | Pros (to verify) | Cons (to verify) | Notes |
|---|---|---|---|
| ChromaDB | | | Leading candidate for lab-scale MVP (local, simple). Not covered by the Phase 1 Gemini research pass; still Future Work. |
| Alternative (TBD) | | | Only evaluate if ChromaDB proves insufficient. |

## Guardrail / Runtime Security Tools (researched — existence verified 2026-07-11)

| Tool | Type | Description | Notes / Verification |
|---|---|---|---|
| **NVIDIA NeMo Guardrails** | Open-source framework | Uses a domain-specific language (`Colang`) to enforce programmable topical, safety, and dialogue constraints/boundaries on LLM-based conversations and agents. | Confirmed real, well-known project (`github.com/NVIDIA/NeMo-Guardrails`). No first-hand testing done by this project yet. |
| **Lakera Guard** | Commercial product | A hosted security layer using multiple classifiers to detect prompt injection and PII leaks before reaching the underlying LLM. Vendor claims sub-200ms inference latency, positioned for low-latency customer-facing use. | Confirmed real commercial product. The "<200ms" latency figure is **Lakera's own vendor claim**, not verified by this project — flagged per `AGENT_RULES.md` rule 3. Requires evaluating pricing/paid-API implications before any hands-on trial (rule 4). |
| **deepteam** (Confident AI) | Open-source red-teaming framework | Runs locally; simulates adversarial attacks including multi-turn "crescendo" jailbreaks and single-turn injections, without sending prompts to a third party. | Confirmed real (`github.com/confident-ai/deepteam`). Candidate for Phase 7 evaluation harness — runs locally, so lower risk of unintentional paid-API usage, but should still be checked for any LLM-as-judge calls that might hit a paid API. |
| **garak** (Generative AI Red-teaming & Assessment Kit) | Open-source vulnerability scanner | Automated probing of LLMs for known weaknesses, prompt leakage, and safety bypasses — analogous to a traditional pentest scanner. | Confirmed real (`github.com/leondz/garak`). Candidate for Phase 2/7 as a source of known attack "probes" to review for inspiration (not verbatim reuse — see `docs/research/dataset-review.md`). |
| **Microsoft PyRIT** (Python Risk Identification Tool) | Open-source automation framework | Enterprise-grade framework for scaling identification of security/privacy risks in generative AI systems. | Confirmed real (`github.com/Azure/PyRIT`). Candidate for Phase 7 evaluation harness inspiration; scope/complexity vs. this MVP's needs still to be assessed. |

**None of the five tools above have been installed, run, or hands-on tested by this project yet.** They are documented here as researched candidates only. Per `AGENT_RULES.md` rule 11, installing any of these (especially heavier frameworks like NeMo Guardrails or PyRIT) requires explicit approval before adding to `requirements.txt`.

## Guardrail / Prompt-Injection Detection Approaches (planned, from Phase 0)

| Approach | Description | Notes |
|---|---|---|
| Rule/regex-based heuristics | Pattern matching for known injection phrasing | Likely first layer — fast, explainable |
| Existing OSS guardrail libraries | e.g., NeMo Guardrails, deepteam (see table above) | Candidates identified in Phase 1; not yet evaluated hands-on |
| LLM-as-judge classifier | Secondary LLM call to classify input/output risk | Requires paid API approval per `AGENT_RULES.md` rule 4 if using a hosted model |

## API-based LLM Provider

| Provider | Notes |
|---|---|
| TBD | Selection pending approval for paid API usage; see `AGENT_RULES.md` rule 4. Not covered by the Phase 1 Gemini research pass. |

## Candidate Evaluation Metrics (researched, planned for Phase 7)

The Gemini research notes propose the following metrics for evaluating guardrail effectiveness. These are **candidate metric definitions only** — no measurement has been taken; all figures in the table are placeholders for what will be *tracked*, not results:

| Metric | Description | Status |
|---|---|---|
| Jailbreak Success Rate (JSR) | Percentage of adversarial prompts that successfully bypass the guardrails. | Planned for Phase 7 |
| False Positive Rate | How often benign, legitimate queries are incorrectly blocked. | Planned for Phase 7 |
| Latency Overhead | Additional processing time (ms) introduced by runtime security checks. | Planned for Phase 7 |
| LLM-as-a-Judge | Using a separate LLM to score outputs for toxicity, bias, or data leakage. | Planned for Phase 7; requires paid-API approval if using a hosted judge model (`AGENT_RULES.md` rule 4) |

## Next Steps (Phase 1)

- Research LlamaIndex vs. LangChain and ChromaDB vs. alternatives — not covered by the current Gemini research pass; still needed.
- Decide whether any of the five guardrail/red-team tools above merit a hands-on trial in Phase 2 (with approval per rule 11 if heavy).
- Record the final decision and rationale as ADRs under `docs/decisions/` once choices are made.

## Future Work (not in Phase 1 scope)

- Hands-on comparative testing (latency, detection accuracy) of any adopted tool — this is Phase 7 evaluation work, not Phase 1 research.
