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

### Phase 4 local run (Gateway skeleton)

As of Phase 4, `app/` contains a runnable FastAPI skeleton: rule-based Input/Output guards, a mock chat pipeline (**no real LLM call**), and JSONL audit logging. Dependencies are **not installed** in this repository — you must install them yourself:

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload
# then visit http://127.0.0.1:8000/docs for interactive Swagger UI
```

Run the test suite:

```bash
pytest
```

On Windows, `scripts/run_dev.ps1` automates the venv-create + install + run steps above.

**What this skeleton does NOT do yet:** call a real LLM API, perform real RAG retrieval/vector search, or make any network call at all. See `app/README.md` for the full scope and `TASK_BOARD.md` for what's next.

Everything before Phase 4 was documentation/data only — Phase 0–3.1 produced scaffolding, research, architecture/threat-model docs, and the synthetic benchmark (`datasets/`, `redteam/`). See [PROJECT_PLAN.md](PROJECT_PLAN.md) for the full roadmap.

## License

Internal academic project — license to be determined by university/institution policy.
