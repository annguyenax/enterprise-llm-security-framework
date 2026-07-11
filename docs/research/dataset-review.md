# Dataset Review

> Status: **Phase 1 in progress — no named public dataset reviewed yet.** This project uses **synthetic data only** for its own test/training data (`AGENT_RULES.md` rule 5). Public datasets reviewed here are for research/inspiration on attack patterns, not for direct inclusion of real-world sensitive content.

## Purpose

Survey existing public prompt-injection / jailbreak / red-team datasets to inform the design of this project's own synthetic red-team set (Phase 2), without copying any real PII or third-party proprietary content.

## Entry Template

```
### <Dataset Name>

- **Source/Link:**
- **License:**
- **Reviewed by:** (team member) — (date)
- **Content type:** (e.g., prompt injection strings, jailbreak prompts, poisoned documents)
- **Usable for inspiration?** yes/no — rationale
- **Notes on synthetic adaptation:** how patterns observed will be reimplemented as original synthetic examples for this project
```

## Entries

_No named public dataset has been directly reviewed yet._ The Phase 1 Gemini research pass (`docs/research/raw/gemini-phase-1-research.md`) did not surface a specific standalone red-team dataset by name — it surfaced **tools** that bundle their own attack probes/datasets internally (see `docs/research/tool-comparison.md`):

- **garak** ships a library of built-in "probes" (known attack patterns) as part of the scanner itself.
- **Microsoft PyRIT** and **deepteam** both include datasets/prompt libraries used to drive their automated red-teaming.

None of these bundled probe sets have been opened, read, or reviewed yet — they are noted here only as **candidate sources** to examine in a future Phase 1/2 session, using the entry template above once actually reviewed.

## Planned Work (Phase 1/2)

- Open and review garak's probe library, PyRIT's dataset directory, and deepteam's attack templates for licensing terms and content type, then log proper entries here.
- Identify any well-known standalone public prompt-injection/jailbreak benchmark datasets (e.g., through further targeted research) not yet surfaced by the Gemini research pass.

## Future Work (not in Phase 1 scope)

- Actual synthetic dataset construction for `datasets/` and `redteam/` — that is Phase 2 work, not Phase 1 research.

## Reminder

Per `AGENT_RULES.md` rule 5 and rule 7: any dataset entries here must not be copy-pasted wholesale into `datasets/` if they contain real PII, real secrets, or content licensed in a way that prohibits redistribution. This project's actual test data must be original synthetic content, only *inspired* by patterns found in public research datasets or tool-bundled probe sets.
