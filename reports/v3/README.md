# Phase 13 evaluation runs (v3)

Each subdirectory is one immutable run of `scripts/run_v3_evaluation.py`, named
`<UTC timestamp>-<short id>` and containing `manifest.json`, `metrics.json`,
`report.md` and `result.jsonl`.

## Retention policy

Only runs that a document under `docs/` cites by `run_id` are tracked here. They
are the evidence behind every number quoted in the report and in
`docs/evaluation/phase13-v3-firewall-metrics-final.md`, so they must stay
byte-stable and reachable from the repository.

Every other run — exploratory sweeps, interrupted runs, re-runs superseded by a
later configuration — stays on the operator's machine and is **not** tracked. A
number that no tracked run backs is not a reportable number.

## Currently tracked runs

| run_id | Cited for |
|---|---|
| `20260811T084708Z-4ad06cc3` | hermes3:8b contrast run (old 300-case set) |
| `20260811T101139Z-56840d90` | mock baseline, expanded 425-case set |
| `20260811T110937Z-9bb96d4e` | qwen3:4b semantic judge, 425-case set |
| `20260811T135545Z-5127f92f` | authority-rule A/B — before |
| `20260811T135722Z-927553a4` | authority-rule A/B — after |
| `20260811T150539Z-5f1e19a2` | post-A/B verification |
| `20260811T150715Z-ada94ea1` | rule + authority, pre-P2 normalize |
| `20260811T151852Z-c848aeac` | post-A/B verification |
| `20260812T082413Z-ac64cd5c` | P2 mock: + Unicode normalization |
| `20260812T091223Z-49d474bc` | P2 qwen3:4b + judge + output DLP |
| `20260812T134954Z-b0f8fecb` | P2 follow-up run |
| `20260812T142935Z-bfee551a` | canary/exfil measurement run |
| `20260812T144516Z-f946bb7b` | canary/exfil measurement run |

## Adding a run

A new run directory is untracked by default. Track it only when a document
starts citing its `run_id`, and cite the `cases_sha256` / `dataset_sha256` from
its `metrics.json` alongside the figure.
