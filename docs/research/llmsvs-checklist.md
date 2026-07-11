# LLM Security Verification Checklist (adapted)

> Status: **Phase 1 in progress.** A real anchor standard has now been identified and verified (see "Source" below). This checklist is still a lightweight, **project-defined** adaptation for a lab-scale MVP — it does not claim compliance with the full OWASP LLMSVS standard, which is far broader in scope than this internship project.

## Purpose

A lightweight, project-scoped checklist used to sanity-check the gateway's guard implementations before evaluation runs. This is **not** a claim of compliance with any formal certification — it is an internal engineering checklist for a lab-scale MVP, loosely inspired by (not equivalent to) a real published standard.

## Source (researched, existence verified 2026-07-11)

- **OWASP Foundation.** *OWASP Large Language Model Security Verification Standard (LLMSVS).* https://owasp.org/www-project-llm-verification-standard/
- **Verification note:** Confirmed real via web search — latest stable version found is **0.1 (February 2024)**, project leads Vandana Verma Sehgal and Elliot Ward. The standard covers architectural, model-lifecycle, model-training, model-operation/integration, and model-storage/monitoring concerns, with **three levels of security assurance**. Gemini's original notes cited this as "(2024)" without a version number — corrected here with the specific version found. A team member should still confirm this against the live OWASP page before final citation, since verification-standard projects are updated over time.
- **Scope honesty note:** This project's checklist below only draws loosely on the *architecture* and *model-operation/integration* areas of LLMSVS that are relevant to a gateway/guardrail proxy. It does **not** attempt model-training or model-storage verification, since this project does no local training (`docs/decisions/ADR-001-mvp-scope.md`). Do not describe this project's checklist as "LLMSVS-compliant" — it is "LLMSVS-inspired" at most.

## Draft Structure (project-defined, to be finalized in Phase 2)

### Input Guard

- [ ] Detects direct prompt injection patterns in user input (project-defined test set)
- [ ] Detects common jailbreak phrasing patterns (project-defined test set)
- [ ] Logs every blocked/flagged input with reason code

### RAG Guard

- [ ] Sanitizes or flags retrieved documents containing embedded instructions
- [ ] Flags documents from the synthetic poisoned-document set in evaluation
- [ ] Logs source document ID for every retrieval used in a response

### Output Guard

- [ ] Flags responses containing known synthetic secret/PII patterns (test fixtures only)
- [ ] Flags responses that appear to leak system prompt content
- [ ] Logs every blocked/flagged output with reason code

### Evaluation

- [ ] Every guard has at least one automated test in `tests/`
- [ ] Evaluation run against synthetic red-team set is reproducible from checked-in scripts/data
- [ ] Evaluation metrics defined and tracked (see `docs/research/tool-comparison.md` for candidate metrics identified in Phase 1: Jailbreak Success Rate, False Positive Rate, Latency Overhead, LLM-as-Judge scoring)

## Planned Work (Phase 1/2)

- Team member reads the actual OWASP LLMSVS controls document (not just the project landing page) to identify which specific control IDs, if any, are worth explicitly referencing per checklist item.
- Phase 2: finalize checklist items alongside threat model and test dataset design.

## Future Work (not in Phase 1 scope)

- Deciding whether to attempt a specific LLMSVS assurance level (1/2/3) as a stretch goal — not planned for MVP; would require scope-expansion approval per `AGENT_RULES.md` rule 1.
