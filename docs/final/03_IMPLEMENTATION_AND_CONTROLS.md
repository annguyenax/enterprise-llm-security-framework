# Implementation and Controls

**Identities:** implementation base `93ad09d…` · Phase 12F HEAD `409e5f3…`  
**Rule:** document only what exists on the integration lineage; no invented modules.

---

## 1. Major components (as implemented)

| Area | Role |
|---|---|
| Application pipeline | Orchestrates guard stages around RAG and provider calls |
| GuardProfile | Boolean profile of which guards are active; C0–C7 registry |
| RAG query service | Lexical retrieval; temporary SQLite corpus from frozen documents |
| LLM provider interface | Abstraction over providers; evaluation uses **mock** |
| Evaluation runner (`scripts/run_v2_evaluation.py`) | Ordinary development/validation; separate holdout path |
| Result analyzer (`scripts/analyze_v2_results.py`) | Matrix analysis + claims_control; separate holdout analysis CLI |
| Benchmark freeze (`scripts/freeze_v2_benchmark.py`) | FINAL manifest verify (byte SHA-256/size) |
| Benchmark build/validate scripts | Hygiene / determinism; **not** holdout preclaim |
| Phase verify (`scripts/verify_phase.ps1`) | Focused/full; `-ReleaseReadiness` for release byte-level checks |
| Materializer (`scripts/materialize_v2_frozen_artifacts.py`) | Manifest-driven materialize of ignored FINAL artifacts; opt-in redteam group |
| Evidence tools (`scripts/phase12f/*`) | Inventory build/verify; Gemini packet after real closure PASS |
| Redteam fixture manifest (`redteam/prompts-manifest.json`) | Tracks identity of ignored `redteam/prompts.jsonl` |

---

## 2. Control classes (conceptual)

Without inventing product names beyond GuardProfile fields:

1. **Input-side controls** — enabled/disabled per profile (e.g. ablation C1 removes input-side protection in the matrix).  
2. **Provenance / context-related controls** — related ablations exist in C0–C7.  
3. **Output / DLP-related controls** — related ablations exist in C0–C7.  
4. **Safety limits** — retrieval/query/timeout/top-k style limits validated for holdout before claim.  
5. **Evaluation integrity controls** — split isolation, authorization, capability, no-overwrite publish, content-free projection, forbidden artifact content scanning.

Exact boolean field names follow `CONFIG_REGISTRY` / GuardProfile on the HEAD; thesis tables should cite the registry rather than paraphrasing inventively.

---

## 3. C0–C7 registry

Eight fixed configurations with stable **config hashes**. Holdout authorization must list all eight in canonical order with matching hashes. Ordinary evaluation may select subsets via `--config` (holdout forbids subset selection).

---

## 4. Mock Provider

Deterministic offline provider used for authorized evaluation. It is a **control for experimental fairness**, not a security control against real models.

---

## 5. Holdout gate (implementation properties)

- External canonical JSON authorization (exact schema, issuer, purpose, mock provider, FINAL manifest SHA, contracts).  
- Fail-closed parse and identity preclaim.  
- Atomic attempt-root claim; start receipt before authorized load.  
- Capability minted only inside verifier closure (procedural).  
- Per-config atomic result publication; partial matrices preserved, not fabricated.  
- Holdout analyzer requires eight complete configs and independent receipt/authorization checks.

---

## 6. Phase 12F materialization controls

- Read FINAL manifest metadata only (path/size/sha256).  
- No `json.loads` on `*.jsonl` artifacts.  
- Reject absolute paths, `..`, symlink/reparse components.  
- Verify source hash/size before copy; verify after.  
- Reuse byte-identical targets; refuse mismatch without force.  
- Publish via **`os.link` no-clobber** (Correction V1); race → re-verify or fail closed.  
- Opt-in `--include-redteam-prompts` with separate one-file allowlist; default does not broaden v2 allowlist.

---

## 7. Evidence packet controls

- Explicit allowlists; required / optional / prohibited classes.  
- Packet builder refuses assembly without COMPLETE closure + PASS gate string.  
- Excludes result.json / JSONL and sensitive key patterns from sanitised packets.  
- Deterministic ZIP; refuse output-directory reuse.

---

## 8. What is not implemented (do not claim)

- Dense vector retrieval stack.  
- Online multi-tenant policy admin UI.  
- Cryptographic remote attestation of evaluation hosts.  
- Automatic holdout authorization by CI.  
- Production SOC integrations.
