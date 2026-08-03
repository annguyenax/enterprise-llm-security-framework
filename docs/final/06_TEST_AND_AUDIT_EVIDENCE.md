# Test and Audit Evidence

**Phase 12F HEAD:** `409e5f3e0770d1bf908d217481994dac3e786c76`  
**Rule:** distinguish *recorded* evidence from *independently re-run* evidence.

---

## 1. Recorded mechanical evidence (Phase 12F)

Source class: **integration / remediation / correction packages and STATUS files** (not re-executed in Phase 12G docs).

| Gate | Recorded result |
|---|---|
| Full suite after Correction V1 | **1011 passed, 0 failed, 4 skipped**, 1 warning |
| Skip class | Host capability / gating (symlink ×3, venv-gated full-release ×1) |
| Warning | Pre-existing Starlette/`httpx` deprecation; `httpx2` not installed |
| Release readiness | **PASS** (frozen 9/9; auxiliary redteam 1/1 when provisioned; symlink SKIP-CAPABILITY) |
| Focused release/materializer tests | PASS with disclosed double-run on one correction focused command (both green) |

**Interpretation:** These results support **integration integrity and release tooling**, not new security-effectiveness AOMR tables.

---

## 2. Recorded cross-review / audit evidence

| Review | Verdict | Notes |
|---|---|---|
| Claude R2 | PASS | Operational/no-clobber and related scope |
| Codex R2 | PASS | Evidence tools / sanitization / closure gating |
| Grok R2 | PASS | Operational review of Correction V1 |
| Gemini final audit | PASS | Methodology/claims style final audit record |
| Critical findings | None reported | — |
| Major findings | None reported | — |

**Provenance:** auditor verdicts are **reported by external/prior audit packages**. Phase 12G documentation **does not re-run** those audits and does **not** claim Gemini executed local pytest or materialization workflows.

---

## 3. Independently re-run in this documentation phase

| Action | Status |
|---|---|
| Full pytest 1011 | **Not re-run** (NOT_VERIFIABLE here) |
| Release readiness | **Not re-run** |
| Holdout / validation / analyzer | **Not run** |
| Raw holdout inspection | **Not done** |

---

## 4. Disclosed process deviation (Correction V1)

Focused tests for the no-clobber correction were **inadvertently executed twice** because a report directory was missing for the first `tee` target. Both runs passed identically (84 passed, 3 skipped in the correction package narrative). This was **disclosed**, not a silent retry of a **failed** command.

---

## 5. Historical evaluation evidence (not Phase 12F)

| Set | Classification |
|---|---|
| Development C0–C7 smoke on candidate | Diagnostic |
| Validation (12E.3 closure) | Historical closed; not reopened by 12F |
| Phase 12E.4 holdout one-shot | **POST-EXECUTION EXPLORATORY / DIAGNOSTIC EVIDENCE ONLY** |

Do not convert exploratory holdout numbers into final results tables.

---

## 6. How to cite evidence in the thesis

1. Quote live command output for any **new** verification on the defense machine.  
2. When citing Phase 12F figures, label them **recorded Phase 12F evidence** with package path / commit.  
3. Never mix “1011 tests passed” into “guards block X% of attacks.”
