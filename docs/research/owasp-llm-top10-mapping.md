# OWASP Top 10 for LLM Applications — Mapping

> Status: **Phase 1 in progress.** Source existence verified by Claude via web search on 2026-07-11 (see `docs/research/raw/gemini-phase-1-research.md` for the original AI-assisted research pass this is based on). Category list below is still the project team's own restatement, not a verbatim copy of the OWASP text — a team member should cross-check exact current wording against the live OWASP page before final report submission.

## Purpose

Map this project's in-scope threats (prompt injection, indirect prompt injection, jailbreak, sensitive information leakage, RAG document poisoning) to the OWASP LLM Top 10 categories, and note which categories are explicitly **out of scope** for the MVP.

## Source (researched, existence verified)

- **OWASP Foundation.** *OWASP Top 10 for Large Language Model Applications.* https://owasp.org/www-project-top-10-for-large-language-model-applications/
- **Verification note:** This is a real, well-known OWASP Foundation project; URL confirmed live. Gemini's notes dated it "(2025)" — OWASP has published multiple dated versions of this list; a team member should confirm which specific dated version (e.g., 2025 vs. an earlier revision) is being cited before adding to `references.bib`, since OWASP LLM Top 10 has had more than one release.

## Mapping Table

| OWASP LLM Top 10 Category | In scope for this project? | Notes |
|---|---|---|
| Prompt Injection | Yes | Core focus — Input Guard + RAG Guard. Confirmed as the #1 category across all OWASP LLM Top 10 revisions reviewed so far. |
| Insecure Output Handling | Partially | Output Guard covers leakage; broader output-handling (e.g., downstream XSS/SQL injection from blindly executed LLM output, as described in the Gemini research notes) is out of scope — MVP has no downstream code-execution consumer of LLM output. |
| Training Data Poisoning | No (relabeled) | Project targets **RAG document poisoning** at retrieval time, not model training data poisoning — no local training in MVP (see `docs/decisions/ADR-001-mvp-scope.md`). |
| Model Denial of Service | No | Out of scope for MVP. |
| Supply Chain Vulnerabilities | No | Out of scope for MVP. |
| Sensitive Information Disclosure | Yes | Output Guard focus — system prompt leakage, PII/secret pattern leakage (synthetic test fixtures only). |
| Insecure Plugin Design | No | No tool/plugin execution in MVP — no AI-agent/tool-use surface as described in the "AI Agents and tool usage" concept from the Gemini research notes. |
| Excessive Agency | No | No autonomous agent/tool-use in MVP. |
| Overreliance | Partially | Discussed in report limitations, not a technical control. |
| Model Theft | No | Out of scope. |

## Additional Context from Phase 1 Research (researched, needs team verification)

The Gemini research pass and follow-up verification surfaced a **compound-attack pattern** worth noting in the threat model: prompt injection and RAG/data poisoning are not always independent — see the PIDP-Attack entry in `docs/research/related-work.md`, which combines a poisoned retrieval corpus with query-time injected suffixes. This suggests the Phase 2 STRIDE threat model (`docs/diagrams/threat-model.md`) should continue treating Input Guard and RAG Guard as a coordinated pipeline rather than fully independent layers — which is already the current design, so no architecture change is implied, just a research citation supporting the existing decision.

## Planned Work (Phase 1, not yet done)

- Confirm exact current category names/definitions against the official OWASP source with a direct team read (not just search-result summaries).
- Add a properly dated citation to `report-latex/references.bib` once the exact OWASP LLM Top 10 revision year is confirmed.
- Expand each "in scope" row with specific detection strategies planned for Input/RAG/Output Guard (deferred to Phase 2 threat-model work).

## Future Work (not in Phase 1 scope)

- Formal gap analysis against categories marked "No" / "Partially" to justify their exclusion in the final report's limitations section.
