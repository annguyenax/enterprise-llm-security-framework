# LLM Security Verification Checklist (adapted)

> Status: placeholder — to be adapted in Phase 1 from a real, verified security verification standard (e.g., an LLM-focused adaptation of OWASP ASVS-style controls). Do not fabricate checklist items attributed to a named standard; clearly mark any project-original items as "project-defined," not sourced.

## Purpose

A lightweight, project-scoped checklist used to sanity-check the gateway's guard implementations before evaluation runs. This is **not** a claim of compliance with any formal certification — it is an internal engineering checklist for a lab-scale MVP.

## Draft Structure (to be filled in Phase 1/2)

### Input Guard

- [ ] Detects direct prompt injection patterns in user input (project-defined test set)
- [ ] Detects common jailbreak phrasing patterns (project-defined test set)
- [ ] Logs every blocked/flagged input with reason code

### RAG Guard

- [ ] Sanitizes or flags retrieved documents containing embedded instructions
- [ ] Flags documents from the synthetic poisoned-document set in evaluation
- [ ] Logs source document ID for every retrieval used in a response

### Output Guard

- [ ] Flags responses containing known synthetic secret/PII patterns (test fixtures only)
- [ ] Flags responses that appear to leak system prompt content
- [ ] Logs every blocked/flagged output with reason code

### Evaluation

- [ ] Every guard has at least one automated test in `tests/`
- [ ] Evaluation run against synthetic red-team set is reproducible from checked-in scripts/data

## Next Steps

- Phase 1: identify a real reference standard to anchor this checklist against (if one is adopted), and cite it properly.
- Phase 2: finalize checklist items alongside threat model and test dataset design.
