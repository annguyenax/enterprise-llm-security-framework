# Enterprise LLM Security Framework

**Xây dựng Hệ thống Bảo mật LLM Chống Tấn công Prompt Injection và Data Poisoning trong Môi trường Doanh nghiệp**

> Status: **Phase 0 — Scaffold only.** No application code has been implemented yet. This is a university internship proof-of-concept (PoC), not a production system.

## Project Summary

This project explores defenses against prompt injection, indirect prompt injection, jailbreak attempts, sensitive information leakage, and basic RAG document poisoning in enterprise LLM applications. The planned deliverable is a lab-scale **LLM Security Gateway / Guardrail Proxy** sitting in front of a Retrieval-Augmented Generation (RAG) application.

This is an **academic internship MVP**. It is explicitly **not** production-ready, is built and evaluated with **synthetic data only**, and makes **no real security guarantees** for production deployments.

## Team

| Name | Student ID | Class |
|---|---|---|
| Nguyen Van An | N22DCAT001 | D22CQAT01-N |
| Le Dinh Nghia | N22DCAT038 | D22CQAT01-N |

**Supervisor:** Nguyen Hoang Thanh

## Repository Structure

```
├── app/                 # Application code (Phase 1+, not yet implemented)
├── redteam/             # Synthetic attack prompts / red-team test cases
├── datasets/            # Synthetic datasets only — no real PII/secrets
├── tests/                # pytest test suite
├── scripts/             # Utility / automation scripts
├── docker/              # Docker Compose setup (later phase)
├── docs/
│   ├── report/           # Periodic report drafts (Markdown, source of truth)
│   ├── research/         # Literature review, OWASP mapping, tool comparison
│   ├── diagrams/         # Mermaid architecture / threat-model / data-flow diagrams
│   ├── weekly-notes/      # Weekly progress notes
│   └── decisions/         # Architecture Decision Records (ADRs)
├── report-latex/         # LaTeX academic report (compiled deliverable)
├── PROJECT_PLAN.md
├── AGENT_RULES.md
├── TASK_BOARD.md
├── requirements.txt
└── .env.example
```

## Current Phase

See [TASK_BOARD.md](TASK_BOARD.md) for the full phase breakdown (Phase 0–9). We are currently in **Phase 0: scaffold, planning, and research setup**.

## Guiding Principles

1. API-based LLMs first; no local fine-tuning in the internship MVP.
2. Synthetic data only — no real secrets, PII, or private documents.
3. Every phase produces documentation and evidence.
4. No scope creep without explicit approval — see [AGENT_RULES.md](AGENT_RULES.md).
5. Terminology stays honest: "proof-of-concept", "MVP", "lab-scale" — never "production-ready".

## Getting Started

Nothing to run yet. Phase 0 only produces scaffolding, planning docs, and the LaTeX report skeleton. See [PROJECT_PLAN.md](PROJECT_PLAN.md) for what comes next.

## License

Internal academic project — license to be determined by university/institution policy.
