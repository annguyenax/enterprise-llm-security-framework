# OWASP Top 10 for LLM Applications — Mapping

> Status: skeleton for Phase 1. Category list below reflects the general structure of the OWASP Top 10 for LLM Applications project; verify exact wording/version against the current official OWASP publication before citing it in the report (`AGENT_RULES.md` rule 2 — no fabricated/unverified citations).

## Purpose

Map this project's in-scope threats (prompt injection, indirect prompt injection, jailbreak, sensitive information leakage, RAG document poisoning) to the OWASP LLM Top 10 categories, and note which categories are explicitly **out of scope** for the MVP.

## Mapping Table (to be verified & completed in Phase 1)

| OWASP LLM Top 10 Category | In scope for this project? | Notes |
|---|---|---|
| Prompt Injection | Yes | Core focus — Input Guard + RAG Guard |
| Insecure Output Handling | Partially | Output Guard covers leakage; broader output-handling (e.g., code execution) out of scope |
| Training Data Poisoning | No (relabeled) | Project targets **RAG document poisoning**, not model training data poisoning — no local training in MVP |
| Model Denial of Service | No | Out of scope for MVP |
| Supply Chain Vulnerabilities | No | Out of scope for MVP |
| Sensitive Information Disclosure | Yes | Output Guard focus |
| Insecure Plugin Design | No | No tool/plugin execution in MVP |
| Excessive Agency | No | No autonomous agent/tool-use in MVP |
| Overreliance | Partially | Discussed in report limitations, not a technical control |
| Model Theft | No | Out of scope |

## Next Steps (Phase 1)

- Confirm exact current category names/definitions against the official OWASP source.
- Add citation to `report-latex/references.bib` once source is verified.
- Expand each "in scope" row with specific detection strategies planned for Input/RAG/Output Guard.
