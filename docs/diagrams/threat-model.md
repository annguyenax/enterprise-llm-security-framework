# Threat Model (STRIDE)

> Planning-level threat model for the MVP gateway + RAG pipeline. To be refined in Phase 2 alongside synthetic test data design.

## Scope

Assets: user's conversation, system prompt, retrieved RAG documents, LLM provider API key/credentials, gateway logs.

Trust boundaries: User ↔ Demo UI/API, Gateway ↔ LLM Provider (external network), Gateway ↔ Vector Store (retrieved content is semi-trusted/untrusted).

## STRIDE Mapping to LLM/RAG Risks

| STRIDE Category | LLM/RAG-specific Risk | Relevant Component | Planned Mitigation (MVP) |
|---|---|---|---|
| **S**poofing | Attacker impersonates a legitimate document source to get malicious content ingested into the RAG corpus | RAG Guard / ingestion | Track document provenance/source ID; flag unverified sources in synthetic corpus design |
| **T**ampering | Indirect prompt injection: retrieved document contains hidden instructions that alter LLM behavior | RAG Guard | Sanitize/flag documents with embedded instruction-like patterns before adding to context |
| **T**ampering | RAG document poisoning: malicious/misleading content inserted into knowledge base to bias future answers | RAG Guard / ingestion | Synthetic poisoned-document test set (Phase 2); detection heuristics in RAG Guard |
| **R**epudiation | No record of why a request was blocked/flagged, making later analysis impossible | Logging/Evaluation | JSONL structured logs for every guard decision with reason codes |
| **I**nformation Disclosure | Sensitive information leakage: system prompt, secrets, or private data exposed in LLM output | Output Guard | Pattern-based detection of synthetic secret/PII markers and system-prompt leakage in output |
| **D**enial of Service | Not a primary MVP focus; e.g., resource-exhausting prompts | Gateway | Out of scope for MVP — noted as a limitation |
| **E**levation of Privilege | Direct prompt injection / jailbreak: user input overrides system instructions to bypass intended constraints | Input Guard | Prompt injection & jailbreak pattern detection before LLM call |
| **E**levation of Privilege | Injected instructions in retrieved content attempt to make the LLM take actions beyond intended scope (e.g., reveal system prompt) | RAG Guard + Output Guard | Combination of RAG sanitization and output-side leakage detection |

## Explicitly Out of Scope (MVP)

- Denial of Service / resource-exhaustion attacks (noted above, not defended against in MVP).
- Attacks on the LLM provider's own infrastructure.
- Supply-chain attacks on dependencies (tracked as a general engineering concern, not a gateway feature).
- Multi-agent / tool-execution privilege escalation (no agentic tool use in MVP).

## Next Steps

- Phase 2: derive specific synthetic test cases from each row above.
- Phase 2: assign detection responsibility precisely (Input Guard vs RAG Guard vs Output Guard) per threat.
