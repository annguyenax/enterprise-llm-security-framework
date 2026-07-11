# Threat Model (STRIDE) — Phase 2

> Planning-level threat model for the MVP gateway + RAG pipeline. Builds on the Phase 0 draft and the module design in `docs/diagrams/architecture.md`. Risk ratings below are **qualitative team judgment** (High/Medium/Low), not measured metrics — no evaluation numbers exist yet (that's Phase 7).

## Scope

Assets: user's conversation, system prompt, retrieved RAG documents, LLM provider API key/credentials, gateway logs, the synthetic RAG corpus itself.

Trust boundaries: User ↔ Demo UI/API, Gateway ↔ LLM Provider (external network), Gateway ↔ Vector Store (retrieved content is semi-trusted/untrusted), ingestion pipeline ↔ synthetic document sources.

This threat model covers the architecture in `docs/diagrams/architecture.md` §3–4 only. It does **not** cover infrastructure-layer threats that only become relevant under the Future Thesis Scope items (Kubernetes, SIEM) — see §4 below.

## STRIDE Mapping to LLM/RAG Risks

| STRIDE Category | LLM/RAG-specific Risk | Relevant Module (see architecture.md §4) | Planned Mitigation (MVP) | Risk Rating (qualitative) |
|---|---|---|---|---|
| **S**poofing | Attacker impersonates a legitimate document source to get malicious content ingested into the RAG corpus | RAG Guard / Vector Store (ingestion) | Track document provenance/source ID at ingestion; flag unverified sources in synthetic corpus design | Medium |
| **T**ampering | Indirect prompt injection: retrieved document contains hidden instructions that alter LLM behavior | RAG Guard | Sanitize/flag documents with embedded instruction-like patterns before adding to context | High |
| **T**ampering | RAG document poisoning: malicious/misleading content inserted into knowledge base to bias future answers | RAG Guard / Vector Store (ingestion) | Synthetic poisoned-document test set (Phase 2 dataset work); detection heuristics in RAG Guard | High |
| **R**epudiation | No record of why a request was blocked/flagged, making later analysis impossible | Logging/Evaluation | JSONL structured logs for every guard decision with reason codes, request ID, timestamp (FR7) | Low (mitigation is straightforward) |
| **I**nformation Disclosure | Sensitive information leakage: system prompt, secrets, or private data exposed in LLM output | Output Guard | Pattern-based detection of synthetic secret/PII markers and system-prompt leakage in output | High |
| **D**enial of Service | Resource-exhausting prompts, oversized inputs, or retrieval-amplification requests | Security Gateway | **Out of scope for MVP** — noted as a limitation, not mitigated | N/A (accepted risk) |
| **E**levation of Privilege | Direct prompt injection / jailbreak: user input overrides system instructions to bypass intended constraints | Input Guard | Prompt injection & jailbreak pattern detection before LLM call (FR2) | High |
| **E**levation of Privilege | Injected instructions in retrieved content attempt to make the LLM take actions beyond intended scope (e.g., reveal system prompt) | RAG Guard + Output Guard | Combination of RAG sanitization (FR4) and output-side leakage detection (FR6) | High |

### Compound-attack note (from Phase 1 research)

Phase 1 research (`docs/research/related-work.md`) surfaced a compound attack pattern (prompt injection combined with RAG poisoning) confirming that the Tampering and Elevation-of-Privilege rows above are not independent — the Input Guard, RAG Guard, and Output Guard are designed as a **coordinated pipeline** (see architecture.md §3) specifically because a single-layer defense is known to be insufficient against such compound attacks. No numeric claim from that research is treated as this project's own result.

## Explicitly Out of Scope (MVP)

- Denial of Service / resource-exhaustion attacks (noted above, not defended against in MVP).
- Attacks on the LLM provider's own infrastructure.
- Supply-chain attacks on this project's own dependencies (tracked as a general engineering concern, not a gateway feature).
- Multi-agent / tool-execution privilege escalation (no agentic tool use in MVP — see architecture.md §5).

## 4. Threats Deferred to Future Thesis Scope (not modeled for MVP)

These threat classes only become relevant if the corresponding architecture piece is ever built — per `docs/diagrams/architecture.md` §5, none of it is MVP scope, so it is **not modeled here**, only listed so it isn't silently forgotten if the project ever expands:

| Deferred infrastructure | Threats that would need modeling if adopted later |
|---|---|
| Kubernetes / container orchestration | Container escape, misconfigured RBAC, exposed control-plane, pod-to-pod lateral movement |
| SIEM integration | Log-tampering in transit to the SIEM, SIEM credential compromise, alert-fatigue-driven missed detections |
| Local fine-tuning / model training pipeline | Training-data poisoning (distinct from the RAG document poisoning already in scope), model exfiltration, training-infra compromise |

## Next Steps

- Phase 2 (continued): derive specific synthetic test cases from each STRIDE row above (`redteam/`, `datasets/` — not started in this documentation-only pass).
- Phase 2 (continued): assign detection responsibility precisely per threat, cross-referenced against the module table in `docs/diagrams/architecture.md` §4 (largely done above; refine as guards are implemented in Phase 4–6).
