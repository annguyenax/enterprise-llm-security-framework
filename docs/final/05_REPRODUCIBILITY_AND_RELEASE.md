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

### 4a. Integrated release tooling (actual CLIs)

The Phase 12G release tooling is integrated in this tree. Derived from
`--help` / source:

```powershell
# Build a deterministic release candidate (policy-enforced, content-free)
python scripts\release\build_release_candidate.py `
  --repo-root <REPO> --output-dir <OUTPUT_DIR> `
  [--expected-head <SHA>] [--expected-branch <BRANCH>] [--base-sha <SHA>] `
  [--generated-allowlist <JSON>] [--summary-out <JSON>]

# Verify a built candidate (PASS / FAIL / NOT_VERIFIABLE)
python scripts\release\verify_release_candidate.py --zip <ZIP> [--output <JSON>]

# Bootstrap a fresh checkout (delegates to the integrated materializer)
powershell -File scripts\release\bootstrap_fresh_checkout.ps1 `
  -SourceRepo <SRC> -TargetCheckout <TGT> -ExpectedCommit <SHA> `
  [-CreateVenvJunction -VenvSource <VENV>] [-ReleaseReadiness -BaseTemp <SHORT>] [-DryRun]
```

The builder writes the ZIP as **`<OUTPUT_DIR>\release-candidate.zip`** (inside
the output directory). It does **not** create a sibling `<OUTPUT_DIR>.zip`.

- **Mandatory external trust anchor.** The verifier returns **PASS only** when an
  external trusted policy file is supplied (`--expected-policy-file`); the
  candidate-embedded policy and manifest identity must equal those trusted bytes,
  which are used for classification. A trusted SHA alone, or no anchor, yields
  **NOT_VERIFIABLE, never PASS** — a candidate cannot self-anchor. When generated
  files are present, PASS also requires an external generated-allowlist anchor.
  The default `verify_release_candidate.py` invocation therefore requires
  `--expected-policy-file`.
- **Content-free failures.** Candidate-controlled names/paths/strings are never
  emitted in failure output; findings carry only stable reason codes,
  `content_free: true`, and safe indices/hashes. No raw values or tracebacks.
- **Disjoint closed-world policy.** Classification is enforced from the tracked
  policy `release/release-allowlist.json` (schema 4), whose `policy_id`, schema
  version and SHA-256 are recorded in the ZIP's `release-manifest.json` and
  re-validated by the verifier. Every tracked path is classified by **counting**
  the inclusion rules it matches: exactly one permitted match includes it and
  records its class + **unique rule ID** + matched form; zero matches, more than
  one match, or a permitted-plus-prohibited match all **fail closed**. The rules
  are **mechanically disjoint** (no two rules can match the same path — the four
  REQUIRED paths are excluded from the broad extension rules), so overlap is
  never hidden by precedence. There is no default-allow branch; an unclassified
  tracked file blocks the release.
- **Snapshot-bound archive safety.** Archives are prohibited by default; an
  allowed archive is inspected from the **exact bound snapshot bytes** that are
  hashed and packaged (names/metadata only — never extracted, never nested
  content). One shared inspector applies identical resource limits in the builder
  and the verifier, and the **verifier independently re-inspects** the packaged
  archive bytes rather than trusting the recorded metadata.
- **Malformed candidates return a structured FAIL.** The verifier converts every
  candidate-controlled parsing failure (including unsupported/encrypted
  compression and outer-ZIP resource exhaustion) into a content-free result and
  never emits a traceback; it enforces an **exact manifest schema at every level**
  (`type(x) is int` so a boolean or float is never accepted where an integer is
  required; canonical `control_coverage`/`zip_policy` values; reconciled counts;
  REQUIRED-path presence; and — when a trusted expected identity is supplied — an
  anchored policy identity) and deterministic ZIP metadata. **NOT_VERIFIABLE is
  never treated as PASS.**
- **Verification occurs before publication.** The builder builds and fully
  verifies the candidate in a same-volume staging directory, requires verifier
  PASS, then publishes the exact verified bytes with an **atomic no-clobber hard
  link** (never `os.replace`, no overwrite, no force), rechecks the published
  hash/size, and verifies the published ZIP again. A pre-publication failure
  leaves no final directory or ZIP. **Old candidate directories are historical
  and are never overwritten.**
- **Vulnerability status is `NOT_CHECKED`** — the dependency inventory queries no
  index or vulnerability service and makes no vulnerability-free claim.
- **Public CI is not equivalent to the private full suite** — the public
  workflow runs synthetic tests only and cannot access the git-ignored private
  benchmark artifacts.

Phase 12E.4 remains **exploratory / diagnostic evidence only**; nothing above
adds an evaluation metric or a security-effectiveness claim.

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
