# Release Notes (Documentation Perspective)

**Through Phase 12F accepted HEAD:** `409e5f3e0770d1bf908d217481994dac3e786c76`  
**Implementation feature base commonly referenced:** `93ad09ddea90eb9712e82f3df5beacbd94399b9a`

---

## Summary

This project provides a lab-scale LLM security gateway for RAG, a frozen synthetic evaluation design with strict holdout isolation, and Phase 12F release-engineering tools that materialize ignored frozen artifacts without clobbering, optionally provision a redteam test fixture under a tracked manifest, and build sanitised auditor packets only after a real closure PASS.

Phase 12F integration closed with recorded mechanical success (1011 passed, 0 failed, 4 capability skips), release-readiness PASS, and PASS cross-reviews (Claude, Codex, Grok R2) plus Gemini final audit PASS, with no Critical or Major findings reported. These results are release-integrity evidence, not production security scores.

A historical Phase 12E.4 holdout run remains **exploratory/diagnostic only** and is not a final evaluation PASS.

---

## Notable technical themes

- Fail-closed evaluation governance (authorization, attempt roots, receipts).  
- Content-free evaluation artifacts and claims_control.  
- Manifest-driven materialization; atomic no-clobber publish (`os.link`).  
- Explicit Windows basetemp and symlink-capability honesty.  
- Evidence inventory allowlists and sanitised packets.

---

## What this release is not

- Not a commercial product launch.  
- Not a claim of real-LLM attack resistance rates.  
- Not a claim that exploratory holdout metrics are final.  
- Not a claim that documentation phase 12G alone is Phase 12G PASS.

---

## Upgrade / handoff notes

Operators must materialize ignored JSONL before full verification. Use short basetemps on Windows. Prefer `--include-redteam-prompts` when full historical redteam tests are required. Preserve blocked and remediation evidence packages as audit history.
