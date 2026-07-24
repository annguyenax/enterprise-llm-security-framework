# Demo Runbook (10–15 minutes)

**Safe mode:** offline, Mock Provider, **no holdout execution**  
**Recommended SHA for live demo:** `409e5f3e0770d1bf908d217481994dac3e786c76` (or tagged release derived from it)

---

## 1. Goals

Examiners should leave understanding:

1. Lab guardrail gateway around RAG.  
2. Frozen synthetic evaluation design.  
3. Why holdout is isolated and why exploratory holdout ≠ final PASS.  
4. How Phase 12F fixes release reproducibility (materialize + no-clobber).  
5. How claims are suppressed (mock, synthetic, L2 latency, no ABR/macro/F1/p-values).

---

## 2. Pre-demo (T−30)

- [ ] Clean checkout of demo SHA  
- [ ] `.venv` works  
- [ ] Materialized FINAL artifacts if needed; `freeze_v2_benchmark.py verify` OK  
- [ ] Optional: `--include-redteam-prompts` if showing full release readiness  
- [ ] Architecture diagram ready  
- [ ] Fallback slides if disk is slow  

---

## 3. Minute plan

| Time | Action | Spoken line |
|---|---|---|
| 0–1 | Title + identity | “Academic PoC guardrail proxy for RAG—not a production product.” |
| 1–3 | Architecture diagram | “Guards wrap retrieval and provider I/O under fixed C0–C7 profiles.” |
| 3–5 | `git rev-parse HEAD` | “Everything is bound to an exact commit.” |
| 5–7 | `freeze_v2_benchmark.py verify` | “Benchmark identity is SHA-256, not ‘files look right’.” |
| 7–9 | Materializer `--help` or dry-run summary | “Ignored JSONL is materialized under a manifest; no clobber.” |
| 9–11 | `verify_phase.ps1 -ReleaseReadiness` excerpt or saved transcript | “Release readiness is byte-level + focused tests—not a live attack campaign.” |
| 11–13 | Governance slide | “Exploratory holdout is diagnostic only; not Phase 12E.4 PASS.” |
| 13–15 | Buffer / questions | See `09_DEFENSE_QA.md` |

---

## 4. Safe commands

```powershell
git rev-parse HEAD
git status --short
.\.venv\Scripts\python.exe scripts\freeze_v2_benchmark.py verify
.\.venv\Scripts\python.exe scripts\materialize_v2_frozen_artifacts.py --help
.\scripts\verify_phase.ps1 -ReleaseReadiness -BaseTemp D:\t\rr
```

**Do not run holdout** in the demo.

---

## 5. Fallback (offline / missing JSONL / slow disk)

1. Architecture + claims matrix slides only.  
2. Show pre-saved freeze-verify transcript labeled historical.  
3. Show GuardProfile / C0–C7 registry in code browser.  
4. Explain materializer and packet tools conceptually.  
5. Explicitly skip live pytest if time fails.

---

## 6. Anti-patterns

- Opening holdout JSONL content.  
- Quoting exploratory holdout rates as final.  
- Installing packages live.  
- Claiming production readiness.  
- Claiming Gemini ran local tests.
