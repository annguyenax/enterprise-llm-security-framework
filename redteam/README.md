# redteam/

Synthetic attack prompts and test cases used to evaluate the gateway's guards.

**Status: empty — Phase 0 scaffold only.** Populated starting Phase 2 (Threat Modeling & Test Data Design).

## Rules (per `AGENT_RULES.md`)

- All content here must be **synthetic** and **original** — no real PII, no real secrets, no verbatim copies of third-party datasets with incompatible licenses.
- Payloads must target **only this project's own lab-scale demo system** — never crafted for use against real third-party production systems (rule 7).
- Each test case should be traceable to a threat-model entry in `docs/diagrams/threat-model.md`.

## Planned Contents (not yet created)

- `prompt_injection/` — direct prompt injection test prompts.
- `indirect_injection/` — synthetic documents with embedded malicious instructions, for RAG Guard testing.
- `jailbreak/` — jailbreak attempt prompts.
- `leakage_probes/` — prompts designed to test whether Output Guard catches synthetic secret/PII leakage.
- `poisoned_documents/` — synthetic poisoned documents for RAG poisoning tests.
