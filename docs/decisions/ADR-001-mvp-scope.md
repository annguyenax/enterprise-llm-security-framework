# ADR-001: MVP Scope

- **Status:** Accepted
- **Date:** 2026-07-11
- **Deciders:** Nguyen Van An, Le Dinh Nghia (with Supervisor Nguyen Hoang Thanh)

## Context

This is a university internship project with a fixed deadline structure (periodic reports, final submission). The full space of "enterprise LLM security" is far larger than what two students can build and evaluate rigorously in the available time. A scope decision is needed up front to keep the project achievable and honestly described.

## Decision

The project will build a **lab-scale LLM Security Gateway / Guardrail Proxy** in front of a demo RAG application, covering exactly five threat categories:

1. Prompt injection (direct)
2. Indirect prompt injection (via retrieved documents)
3. Jailbreak attempts
4. Sensitive information leakage
5. Basic RAG document poisoning risks

Technical constraints adopted for the MVP:

- API-based LLM provider only; **no local training or fine-tuning**.
- Local small model via Ollama is an **optional future exploration**, explicitly not part of Phase 0–9 MVP scope unless later approved.
- **Synthetic data only** — no real secrets, PII, or private/proprietary documents anywhere in the repository.
- RAG framework (LlamaIndex vs LangChain) and vector store (ChromaDB vs alternative) decisions are **deferred** to dedicated ADRs once Phase 1 research and Phase 5 implementation needs are clearer.

## Consequences

- The system will **not** claim production-readiness, comprehensive attack coverage, or enterprise-grade guarantees. Terminology is restricted to "proof-of-concept" / "MVP" / "lab-scale" (`AGENT_RULES.md` rule 8).
- Evaluation results will only cover the synthetic test set actually built in Phase 2 — no generalization claims beyond that set.
- Any request to expand scope (e.g., add agentic tool-use security, multi-modal input, additional attack classes) requires an explicit new decision, not silent expansion (`AGENT_RULES.md` rule 1).
- Framework/vector-store lock-in risk is deferred but must be resolved before Phase 5 begins in earnest.
- The system must run entirely on a **two-student team's own laptops (16GB RAM each)** — no infrastructure requiring a server fleet, container cluster, or paid always-on hosting is assumed for the MVP.

## MVP Scope vs. Future Thesis Scope (Phase 2 addendum, 2026-07-11)

Phase 2 architecture work (`docs/diagrams/architecture.md` §5) made explicit a distinction that was implicit in this ADR's original decision: several enterprise-grade capabilities are **future thesis scope only** and must never be treated as MVP requirements, regardless of how the report frames the project's ambitions.

| Explicitly future thesis scope (NOT MVP) | Why it's excluded from MVP |
|---|---|
| **Kubernetes** / container orchestration | Adds operational complexity far beyond a lab-scale, single/dual-laptop setup; no scaling need exists for a demo with a synthetic corpus and two users. |
| **SIEM integration** (e.g., Splunk/ELK/Sentinel log shipping) | Assumes an enterprise security-operations context this internship does not have; JSONL local logging is sufficient for Phase 7 evaluation. |
| **Local model fine-tuning / training** | Already excluded by the original decision above (no local training in MVP); restated here for clarity now that it's being explicitly asked about per phase. |

If a future continuation of this work (e.g., a full thesis beyond the internship) wants to pursue any of these, that requires a **new ADR**, not an extension of this one — per `AGENT_RULES.md` rule 1 (no scope creep) and rule 12 (stop at phase boundaries).

## Alternatives Considered

- **Full enterprise-grade security product** — rejected: infeasible within internship timeline and resources, and would require real production data/traffic to validate meaningfully.
- **Local fine-tuned model for detection** — rejected for MVP: adds significant training infrastructure and time cost; API-based approach lets the team focus on gateway/guard architecture instead of model training. May be revisited as a stretch goal.
- **Cover all OWASP LLM Top 10 categories** — rejected: several categories (e.g., Model DoS, Supply Chain, Excessive Agency) are not relevant to a non-agentic, non-plugin lab demo; covering them would dilute focus without adding real learning value for this scope.
