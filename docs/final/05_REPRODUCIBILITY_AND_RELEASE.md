# Reproducibility and Release

**Phase 12F HEAD:** `409e5f3e0770d1bf908d217481994dac3e786c76`  
**Base:** `93ad09ddea90eb9712e82f3df5beacbd94399b9a`

---

## 1. Reproducibility pillars (available on accepted 12F HEAD)

1. **Exact git SHA** checkout, clean tree.  
2. **Python venv** from `requirements.txt` (never install `httpx2`).  
3. **FINAL manifest byte verify:** `scripts/freeze_v2_benchmark.py verify`.  
4. **Materialize ignored artifacts:**  
   `scripts/materialize_v2_frozen_artifacts.py --source-root … --target-root …`  
   Optional: `--include-redteam-prompts` for v1 redteam fixture.  
5. **Mechanical tests** with **short external basetemp** on Windows.  
6. **Release readiness:** `scripts/verify_phase.ps1 -ReleaseReadiness` (byte-level frozen + auxiliary; no holdout/analyzer).  
7. **Evidence tools:** `scripts/phase12f/build_evidence_inventory.py`, `verify_evidence_inventory.py`, `prepare_gemini_packet.py` (packet requires real closure PASS).

---

## 2. Materialization rules (operator)

| Rule | Behavior |
|---|---|
| Allowlist | Only FINAL manifest paths (plus opt-in redteam group) |
| Parse JSONL records | Never |
| Matching target | Reuse |
| Mismatch target | Fail closed; no force |
| Concurrent race | `os.link` no-clobber; identical → reused_concurrent after re-verify; else fail |
| Dry-run | Writes nothing |
| Manual copy | Not the supported path |

---

## 3. Windows notes

- Prefer short basetemp (e.g. `D:\t\f`) to avoid MAX_PATH failures.  
- Symlink tests may **SKIP-CAPABILITY** if host forbids symlinks.  
- Directory `fsync` residual after receipt/publish is platform-limited.  
- Hard-link support required for materializer no-clobber primitive; unsupported volumes fail closed.

---

## 4. EXPECTED AFTER PHASE 12G INTEGRATION

The following may land from other Phase 12G workstreams. Until integrated, treat as **planned**, not present on this documentation branch:

| Item | Status label |
|---|---|
| Unified CI workflow that injects private sealed artifact bundles | **EXPECTED AFTER PHASE 12G INTEGRATION** (public CI deliberately has no private-data access) |
| Automated release archive job with signed checksums | **EXPECTED AFTER PHASE 12G INTEGRATION** (the release builder emits unsigned `SHA256SUMS.txt`; no signing job yet) |
| One-command fresh-checkout bootstrap | **INTEGRATED** — `scripts/release/bootstrap_fresh_checkout.ps1` (commit-identity + clean-tree check, materializer delegation with `--include-redteam-prompts`, optional `.venv` junction, optional release-readiness) |
| Cross-OS matrix in CI (Linux + Windows) | **INTEGRATED** — `.github/workflows/phase12g-release-gates.yml` runs an `ubuntu-latest` + `windows-latest` matrix (Python 3.11) |

Do **not** document unmerged scripts as if they already exist under `scripts/` on this branch.

---

## 5. Evidence root layout (external to git)

```text
<external>/
  development-or-smoke-roots/     # diagnostic
  holdout-attempt-roots/          # one-shot; never reuse
  authorization-files/            # external; never commit secrets
  auditor-packets/                # sanitised; after real closure PASS
```

---

## 6. What reproducibility does **not** mean

- Re-running exploratory holdout and treating it as final PASS.  
- Reproducing commercial LLM stochastic attack success rates.  
- Guaranteeing identical wall-clock latency.  
- Proving absence of all hostile local filesystem interference (NOT_VERIFIABLE under trusted-maintainer model).
