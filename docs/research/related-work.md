# Related Work

> Status: **Phase 1 in progress.** Entries below originate from an AI-assisted research pass (Gemini notes at `docs/research/raw/gemini-phase-1-research.md`), cross-checked by Claude via live web search on 2026-07-11 to confirm each source actually exists and to catch citation errors before anything goes into `report-latex/references.bib`. Existence + core metadata (title, authors, venue) have been machine-verified; a **team member has not yet read the full text** of any of these papers. Do not treat this list as "reviewed" in the full sense of the entry template below until a team member has actually read the source and filled in the Summary/Relevance fields from their own understanding.

## Purpose

Track prior academic and industry work relevant to:

- Prompt injection detection and defense
- Indirect prompt injection via retrieved/tool content
- Jailbreak detection
- Sensitive information / PII leakage prevention in LLM outputs
- RAG document/data poisoning attacks and defenses
- LLM security evaluation frameworks and benchmarks

## Entry Template

```
### <Title>

- **Authors:**
- **Venue/Year:**
- **Link:**
- **Reviewed by:** (team member) — (date)
- **Summary:** 2-4 sentences on what the work does.
- **Relevance to this project:** how it informs the Input/RAG/Output Guard design.
```

## Entries (researched — existence verified, full read pending)

### PoisonedRAG: Knowledge Corruption Attacks to Retrieval-Augmented Generation of Large Language Models

- **Authors:** Wei Zou, Runpeng Geng, Binghui Wang, Jinyuan Jia
- **Venue/Year:** arXiv:2402.07867 (Feb 2024; accepted at USENIX Security Symposium 2025)
- **Link:** https://arxiv.org/abs/2402.07867
- **Reviewed by:** _Not yet — team member should read full text before citing in the LaTeX report._
- **Verification note:** Gemini's original draft cited this as "Zou, Y. et al." — confirmed via web search that the correct first-author initial is **Zou, W.** (Wei Zou), not Zou, Y. Corrected here; **needs verification** by a team member reading the actual paper before this citation is used in `references.bib`.
- **Summary (from abstract, unverified by direct read):** Proposes an attack where injecting a small number of malicious texts into a RAG knowledge database can manipulate an LLM's generated answers; reports up to ~90% attack success rate when injecting five malicious texts per target question, per the paper's own claims.
- **Relevance to this project:** Directly informs the **RAG Guard** threat model — this is a foundational reference for "RAG document poisoning" as scoped in `docs/decisions/ADR-001-mvp-scope.md`.

### PIDP-Attack: Combining Prompt Injection with Database Poisoning Attacks on Retrieval-Augmented Generation Systems

- **Authors:** Haozhen Wang, Haoyue Liu, Jionghao Zhu, Zhichao Wang, Yongxin Guo, Xiaoying Tang
- **Venue/Year:** arXiv:2603.25164 (submitted March 2026)
- **Link:** https://arxiv.org/abs/2603.25164
- **Reviewed by:** _Not yet — team member should read full text before citing in the LaTeX report._
- **Verification note:** This is a very recent (March 2026) preprint, confirmed to exist via web search (authors, institution — CUHK-Shenzhen and Taobao/Tmall Group — and claimed ~98% ASR match across independent search results). Flagged as **needs verification** for a team member's own read, since preprints are not peer-reviewed and claimed numbers are the authors' own, unverified by us.
- **Summary (from abstract, unverified by direct read):** Proposes a compound attack combining a small number of universally poisoned passages pre-injected into the retrieval database with a lightweight malicious suffix appended to user queries at inference time, removing the need for advance knowledge of the victim's queries.
- **Relevance to this project:** Illustrates that **prompt injection and RAG poisoning are not independent threats** — reinforces the project's decision to have Input Guard, RAG Guard, and logging work together rather than treating each guard as a standalone defense. Relevant to Phase 2 threat model refinement (`docs/diagrams/threat-model.md`).

### Prompt Injection Attacks in Large Language Models and AI Agent Systems: A Comprehensive Review of Vulnerabilities, Attack Vectors, and Defense Mechanisms

- **Authors:** Gulyamov, Rodionov, Khursanov, Mekhmonov, Babaev, Rakhimjonov
- **Venue/Year:** *Information* (MDPI, ISSN 2078-2489), Volume 17, Article 54 — **2026**, not 2025
- **Link:** https://www.mdpi.com/2078-2489/17/1/54
- **Reviewed by:** _Not yet — team member should read full text before citing in the LaTeX report._
- **Verification note:** Gemini's draft cited this as "MDPI Foundation (2025)" with no author list. Web search confirms the article is real and identifies the author list above, but also indicates the correct year is **2026** (Volume 17 of this MDPI journal corresponds to 2026, not 2025) — **corrected here, still needs a team member to confirm directly from the published PDF before citing.**
- **Summary (from secondary sources, unverified by direct read):** A literature review synthesizing ~45 sources plus industry reports (2023–2025) on prompt injection taxonomy (direct/indirect), agent/MCP-specific attack surface expansion (tool poisoning, credential theft), and proposes a "PALADIN" defense-in-depth framework mapped to the OWASP Top 10 for LLM Applications 2025.
- **Relevance to this project:** Useful as a broad literature-review anchor for Chapter 1 of the report (`report-latex/chapters/01-tong-quan.tex`) and for the "defense-in-depth" framing already used in `docs/diagrams/architecture.md`. The "PALADIN" framework name should **not** be adopted or referenced as if this project implements it — it's cited context only.

## Future Work (not yet researched)

- Broader academic survey of jailbreak-specific defenses (separate from the general prompt-injection reviews above).
- Papers specifically on sensitive-information / PII leakage detection in LLM outputs — not covered by the current Gemini research pass.
- Full-text read-through of all three entries above by a team member, per `AGENT_RULES.md` rule 2.
