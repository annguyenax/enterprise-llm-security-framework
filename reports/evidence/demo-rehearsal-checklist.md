# Demo Rehearsal Checklist

Use this checklist for at least one timed rehearsal before the final demo. The
target duration is 5-7 minutes and all data/provider behavior is local and
synthetic.

## Preflight

- [ ] Confirm the reviewed branch/commit: `git status --short` and `git log -1 --oneline`.
- [ ] Confirm `.venv` is active: `python -c "import sys; print(sys.executable)"`.
- [ ] Run tests:

```powershell
python -m pytest -q --basetemp="$env:TEMP\enterprise-llm-security-framework-pytest"
```

Expected: `82 passed`; one Starlette deprecation warning may appear. Do not
install `httpx2`.

- [ ] Regenerate guarded and comparison evidence:

```powershell
python scripts\run_evaluation.py
python scripts\run_evaluation.py --comparison
```

Expected: guarded 40/40; always-allow baseline 5/40; no external calls.

- [ ] Start the server in Terminal 1:

```powershell
uvicorn app.main:app --reload
```

- [ ] Open Terminal 2 and keep `demo-script.md` visible.
- [ ] Close unrelated windows and hide private/local information.
- [ ] Confirm screenshots are available as fallback.

## Timed Flow

| Time | Action | Expected output | Speaking point |
|---|---|---|---|
| 0:00-0:30 | Call `/health`. | `status=ok`, mock-provider phase. | Local PoC is running; no cloud service is required. |
| 0:30-1:15 | Send benign input. | `allow`, no rules, risk 0. | Guards should preserve ordinary enterprise questions. |
| 1:15-2:00 | Send direct injection. | Input/final `block`; provider/output absent. | Stopping decisions prevent provider execution. |
| 2:00-3:00 | Send poisoned context. | `sanitize`; surrounding text and metadata remain. | RAG Guard removes the hidden block selectively. |
| 3:00-4:00 | Send clean gateway chat. | Mock provider metadata; Output Guard runs. | Adapter is real code, provider response is deterministic/offline. |
| 4:00-5:00 | Run guarded evaluation. | 40/40, 0 FP, 0 FN. | Exact-label result on frozen synthetic benchmark only. |
| 5:00-6:00 | Run comparison. | Baseline 5/40 vs guarded 40/40. | Baseline always allows; it is not LLM quality. |
| 6:00-7:00 | Show evidence index and limitations. | Evidence links and commands. | Rule-based, no real LLM/vector DB/retrieval, not production-ready. |

Use exact commands from `reports/evidence/demo-script.md` rather than retyping
payloads during the presentation.

## Common Questions and Suggested Answers

**Why does guarded evaluation reach 40/40?**

It is exact-label agreement on 40 frozen synthetic prompts after five initial
false negatives were triaged and narrowly calibrated. It is not a real-world
detection rate and may not generalize to unseen semantic attacks.

**Is a real LLM being protected in this demo?**

No. The gateway has a typed provider adapter, but the only implementation is a
deterministic local mock. This isolates and tests pipeline behavior without API
keys, cost, network access, or model variability.

**Is this a complete RAG application?**

No. The dataset loader and RAG Context Guard exist, but there is no embedding,
vector database, similarity search, or retrieval step. The caller supplies
context chunks directly.

**What does the baseline prove?**

It shows decision-level behavior when all guards are removed and every case is
allowed. It does not measure LLM answer quality or harmful generated output.

**Why use regex/rules instead of a learned detector?**

Rules are small, explainable, offline, and suitable for this internship PoC.
Their limited semantic generalization is explicitly documented as future work.

**Could the 40/40 result be overfit?**

Yes, calibration bias is a known limitation. A larger independent holdout set
and semantic/unseen-variant evaluation are required before broader claims.

**What happens on `human_review`?**

In this MVP it has the same stopping effect as block, tagged separately for
manual attention. There is no live review queue.

**Why is there an `httpx2` warning?**

The installed Starlette version emits a deprecation warning. The project uses
the declared `httpx` dependency, tests pass, and `httpx2` is not installed.

## Fallback Plan if the Live Server Fails

1. Do not spend more than 30 seconds debugging during the presentation.
2. Show the previously captured health/block/sanitize screenshots from the
   screenshot guide.
3. Run offline evidence that does not require the server:

```powershell
python scripts\run_evaluation.py
python scripts\run_evaluation.py --comparison
python -m pytest tests\test_input_guard_calibration.py tests\test_rag_guard.py -q
```

4. Show `latest-evaluation.md`, `baseline-vs-guarded.md`, and the relevant guard
   tests/source code.
5. State clearly that the fallback demonstrates reproducible decision logic,
   while live HTTP transport could not be shown at that moment.

## Post-Rehearsal Record

- [ ] Actual duration recorded: ______
- [ ] Presenter transitions adjusted.
- [ ] All commands pasted successfully.
- [ ] No private data appeared on screen.
- [ ] Questions needing supervisor input recorded.
- [ ] Fallback screenshots readable.
- [ ] Final rehearsal approved by both team members.
