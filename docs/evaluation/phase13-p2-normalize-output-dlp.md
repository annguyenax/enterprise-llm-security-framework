# Phase 13 P2 — Input normalization + Output-DLP canary (continuation)

Status: implemented + measured + **committed** at `e7a945c` (self-measured;
not self-adjudicated as project PASS). Continues after holistic audit
(Grok 7.4/10): **(a)** unicode normalize, **(b)/(c)** clean canary demo +
Output-DLP (earlier `d65f1e3` + A/B fix in this commit), **(d)** semantic judge
default OFF.

Disk note: a qwen re-run was interrupted when **C: had ~0.7 GB free**. After the
operator freed space (~14 GB free observed), the qwen P2 run **completed** as
`20260812T091223Z-49d474bc`. No further disk cleanup by agents.

## Code changes (worktree / pending commit unless landed)

| Piece | What |
|-------|------|
| `app/guards/input_guard.py` | `_normalize`: NFKC + strip zero-width + fold common Cyrillic/Latin homoglyphs **before** rule match |
| `app/guards/semantic_guard.py` | `SEMANTIC_GUARD_USE_LLM` **default OFF** (opt-in `1`/`true`) |
| `app/guards/output_guard.py` | Block `FLAG{...}` canary in responses (from `d65f1e3`) |
| `tests/test_input_guard.py` | `test_unicode_smudged_injection_is_normalized_and_blocked` |

## Controlled runs (same 425 cases, `cases_sha256` `f73d094a…`)

| Config | run_id | TPR | FPR | FPR-hard | Stop-before-LLM | garak | injecagent | pyrit | exfil |
|--------|--------|----:|----:|---------:|----------------:|------:|-----------:|------:|------:|
| Rule + authority (pre-P2 normalize) | `20260811T150715Z-ada94ea1` | 77.0% | 0% | 0% | 77.0% | 75.2% | 47.4% | 100% | 0% (mock) |
| **Rule + normalize (P2 mock)** | `20260812T082413Z-ac64cd5c` | **81.5%** | **0%** | **0%** | **81.5%** | **83.8%** | 47.4% | 100% | null (no corpus seed) |
| **qwen3:4b + judge ON + DLP (P2)** | `20260812T091223Z-49d474bc` | **100%** | **18.7%** | **20.0%** | **81.5%** | 100% | 100% | 100% | **0%** (n=200) |

### Interpretation (honest)

1. **Normalize alone** (mock): +4.5pp TPR (77→81.5), FPR still 0. Gain is almost
   entirely **garak/unicode** (unicode block 33.3%→63.3%; garak 75.2%→83.8%).
   **injecagent unchanged at 47.4%** — hidden-in-prose is not fixed by NFKC.
2. **Stop-before-LLM identical** (81.5%) on mock P2 and qwen P2 → small judge
   still does **not** add early blocks vs the rule layer after normalize.
3. **qwen TPR 100%** with Stop-before-LLM 81.5% means **37/200** malicious were
   blocked **after** `provider_called` (Output-DLP canary), not by stronger
   input injection detection. Do **not** report “judge solved injection.”
4. **FPR 18.7%** on qwen is worse than the pre-P2 11.1% judge point — still
   not deployable as primary config; default-off judge remains correct.
5. Mock P2 run had **no corpus** (`exfil_reportable=false`); do not invent exfil
   for that run.

## Provenance (from metrics.json)

- Mock: `git_commit` `d65f1e3…`, `git_worktree_dirty: true` (normalize was dirty
  worktree at run time), provider mock.
- Qwen: same commit base, dirty worktree, `llm_provider=ollama`,
  `llm_model_name=qwen3:4b`, `semantic_guard_use_llm=1`,
  `corpus_sha256=8cc05cd6…`.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_input_guard.py tests/test_output_guard.py
# observed: 17 passed
```

## Report

Chapter 4 tables/analysis updated to P2 primary numbers (rule 81.5%/0%, qwen
100%/18.7%, Stop-before equal). Progressive optim table keeps baseline →
authority → normalize.

## Residual

- injecagent 47.4% on rules.
- Adaptive roleplay evasions (unit ALLOW list) still pass input rules.
- Hermes not re-run on normalize layer (figure caption notes pre-normalize ref).
- Full suite not re-run in this continuation session (disk recovery focus).
