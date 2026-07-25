# Maintainer Handoff

**Audience:** project maintainer / thesis supervisor  
**Phase 12F accepted HEAD:** `409e5f3e0770d1bf908d217481994dac3e786c76`  
**Implementation base often cited:** `93ad09ddea90eb9712e82f3df5beacbd94399b9a`

---

## 1. Exact current identity (record at handoff)

| Field | Value to fill at handoff time |
|---|---|
| Primary repo path | `________________` |
| Integration worktree (if used) | e.g. `D:\p12f-integration` |
| Documentation worktree | `D:\p12g-grok` (this package) |
| `git rev-parse HEAD` (integration) | should be `409e5f3…` or a documented descendant |
| Clean status | yes / no |

---

## 2. Required worktrees / packages to preserve

| Path / package | Why keep |
|---|---|
| Integration worktree at `409e5f3…` | Accepted Phase 12F HEAD |
| `phase12f-integration-93ad09d` | **Blocked** integration report (history) |
| `phase12f-integration-remediation-487ed81` | Remediation evidence |
| `phase12f-cross-review-correction-8dbf254` | Correction V1 evidence |
| `phase12f-final-cross-review-8dbf254` | Round 1 cross-review |
| `phase12f-final-cross-review-r2-409e5f3` | Round 2 cross-review |
| Phase 12E.4 exploratory holdout attempt root (if retained) | Historical; label diagnostic only |
| External authorizations | Never commit secrets; hash registry |

**Never delete** blocked reports to “clean history.” Transparency is part of the grade of the process.

---

## 3. Release candidate procedure (checklist)

1. Checkout intended release SHA; confirm clean.  
2. Materialize FINAL artifacts (+ optional redteam).  
3. `freeze_v2_benchmark.py verify`.  
4. `verify_phase.ps1 -ReleaseReadiness` with short basetemp.  
5. Full pytest with short basetemp; record live numbers.  
6. Build sanitised auditor packet **only after** real closure PASS (if using packet tool).  
7. Run claims matrix review against thesis PDF.  
8. Archive code + docs + sealed artifact bundle hashes.  
9. Tag only after maintainer sign-off.

### 3a. Actual release tooling commands (build + verify)

Before step 6, build and independently verify the deterministic release
candidate with the integrated CLIs (see also `docs/final/05` §4a).

The Phase 12G release tooling is integrated on this branch. The builder writes
exactly `<OUTPUT_DIR>\release-candidate.zip` (no sibling `<OUTPUT_DIR>.zip`),
classifies every tracked path under the disjoint closed-world policy, verifies a
staged ZIP, then publishes the exact verified bytes with an atomic no-clobber
hard link. Old candidate directories are historical and must not be overwritten.

```powershell
# Build (disjoint closed-world policy-enforced, content-free, verify-before-publish)
python scripts\release\build_release_candidate.py `
  --repo-root <REPO> --output-dir <OUTPUT_DIR> `
  [--expected-head <SHA>] [--expected-branch <BRANCH>] [--base-sha <SHA>] `
  [--generated-allowlist <JSON>] [--summary-out <JSON>]

# Independently verify the built candidate (PASS / FAIL / NOT_VERIFIABLE).
# --expected-policy-file is MANDATORY for a PASS result (an external trusted policy
# file); without it the result is NOT_VERIFIABLE. Supply --expected-generated-file
# only when the candidate contains generated payloads.
python scripts\release\verify_release_candidate.py --zip <OUTPUT_DIR>\release-candidate.zip `
  --expected-policy-file release\release-allowlist.json `
  [--expected-policy-id <ID>] [--expected-head <SHA>] [--expected-generated-file <DECL_JSON>]
```

---

## 4. Audit procedure

| Audit | Owner | Input | Output |
|---|---|---|---|
| Technical/security | Independent technical auditor | Clean SHA + code | PASS/FAIL findings |
| Methodology/claims | Gemini or equivalent | Sanitised packet + claims matrix | PASS/FAIL |
| Mechanical | Scripts only | Live commands | Counts |
| Maintainer adjudication | Human only | Risks + evidence classes | Authorize / do not authorize |

Gemini does **not** replace local pytest.

---

## 5. Final tagging checklist

- [ ] Exact SHA recorded  
- [ ] Full suite live numbers attached  
- [ ] Release readiness PASS on release machine  
- [ ] Claims matrix signed  
- [ ] Exploratory holdout still labeled diagnostic if mentioned  
- [ ] No secrets in tag tree  
- [ ] Archive SHA-256 stored offline  

---

## 6. Items that must never be deleted

1. Blocked integration report package.  
2. Burned holdout attempt roots (if any).  
3. FINAL benchmark freeze identity.  
4. Cross-review STATUS/SHA256SUMS packages.  
5. Authorization SHA registry entries.  

---

## 7. Holdout policy reminder

Only the maintainer may issue `holdout_authorized: true`.  
Do not use inactive drafts.  
Do not reuse attempt roots.  
Do not promote exploratory Phase 12E.4 to final PASS without a methodologically allowed new evaluation.

---

## 8. Phase 12G documentation package

This `docs/final/**` set is the Grok primary handoff. Peer packages (if any) integrate separately. **No Phase 12G PASS is claimed by documentation alone.**
