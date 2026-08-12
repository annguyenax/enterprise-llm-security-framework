# Response to Code X (REVISE) + Gemini (PASS-with-fixes) — 2026-08-12

## Actions taken (implementer; not self-adjudicated)

### Code X P0

| Finding | Action |
|---------|--------|
| Unguarded detector missed `response` field | Fixed `scripts/run_demo_ab_paired.py` → `_extract_unguarded_answer` prefers `response` |
| A/B not “same retrieval, only guards” | Report + script framing: **system-level** A/B (two paths) |
| Quant claims 3/6, 0/6 every time without valid artifact | Replaced Ch4 A/B with numbers from **new** run `20260812T095917Z` only |
| Regression | `tests/test_demo_ab_paired_schema.py` (2 tests) |

### New A/B artifact (automatic, 3 reps, qwen3:4b)

| Metric | Value |
|--------|------:|
| run_id | `20260812T095917Z` |
| unguarded canary leak | **12/18** (3/6, 4/6, 5/6) |
| guarded canary leak | **0/18** |
| guarded blocked | 9/18 |

Paths: `reports/demo-ab/20260812T095917Z/{ab_result.json,manifest.json,transcript_content_free.txt}`  
Manual guide: `reports/demo-ab/README-AB-MANUAL-AND-AUTO.md` (demoBAOCAO-style).

### Code X P1 (partial)

| Finding | Action |
|---------|--------|
| Input Guard 10 → 11 | Ch4 table updated (+ A/B schema 2 tests) |
| Full suite 1526 NOT VERIFIABLE | Claim softened: **1533 collected**; passed only with full log |
| Dirty provenance P2 runs | Still open: normalize not in clean commit; needs maintainer commit + optional re-run |
| `blocked_stage` in result.jsonl | Not implemented this pass (larger runner change) |

### Gemini prose

| Item | Action |
|------|--------|
| FPR 0% scoped to synthetic lab | Strengthened in Ch4 analysis |
| PyRIT 100% template family | Kept/strengthened |
| Stop-before vs Output-DLP | Already in Ch4; kept |
| A/B rewrite | Replaced with artifact-backed table |
| refs.bib Hackett note + PyRIT cite | Done |

### Rebuild

`baocaodot2_fixed.zip` rebuilt from current `bao_cao_latex_dot2/`.

## Still open for re-audit

1. Commit clean tree (normalize + semantic default-off + script/tests/report) so provenance is not dirty-only.  
2. Optional: re-run mock/qwen 425 from that clean commit.  
3. Optional: `blocked_stage` / `matched_rule_ids` in v3 results.  
4. Full-suite log artifact if claiming exact passed count.

## Manual A/B (user)

Follow `reports/demo-ab/README-AB-MANUAL-AND-AUTO.md` §2; save like `demoBAOCAO.txt` with CANARY_LEAK flags.
