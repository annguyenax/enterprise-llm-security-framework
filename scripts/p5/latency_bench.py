"""P5-W1: per-stage latency benchmark for the guarded chat path.

Answers the thesis reviewer's point 4 ("thiếu đo latency"): p50/p95/p99 for
every guard stage and for the whole request, with the Semantic Judge on and
off, against the same v3 case set used for TPR/FPR.

How it measures (no application code is modified)
-------------------------------------------------
The app is driven in-process through FastAPI's TestClient exactly like
`scripts/run_v3_evaluation.py`, hitting `POST /v1/conversations/{id}/messages`.
Before the first request, the functions that make up each stage are wrapped
with `time.perf_counter_ns()` timers *at the module attribute the caller looks
them up from* (e.g. `app.services.gateway.evaluate_input`). A stage that is
not reached on a request (because an earlier guard stopped it) is recorded as
absent, never as 0 ms, so stage percentiles are computed only over requests
that actually executed that stage.

Stages
------
- history_screen      app.workspace.routes.screen_history
- retrieval           app.workspace.store.retrieve
- input_guard         app.services.gateway.evaluate_input        (regex rules)
- semantic_input      app.guards.semantic_guard.evaluate_input_semantic
  - semantic_judge_llm   ..._evaluate_with_llm (nested inside semantic_*; the
                         Ollama call; only when SEMANTIC_GUARD_USE_LLM=1 and
                         provider != mock)
- rag_context_guard   app.services.gateway.evaluate_rag_context
- provider            BaseLLMProvider.generate (the LLM answer itself)
- output_guard        app.services.gateway.evaluate_output
- semantic_output     app.guards.semantic_guard.evaluate_output_semantic
- guard_overhead      derived: sum of the guard stages above (history_screen,
                      input_guard, semantic_input, rag_context_guard,
                      output_guard, semantic_output) for that request
- e2e                 wall time of the HTTP call as seen by the client

Percentiles use the nearest-rank method on the raw sample. p99 is flagged
`p99_reportable=false` when a stage has fewer than 100 samples, because
nearest-rank p99 of < 100 points is just the maximum.

Honesty rules
-------------
- Numbers are lab-scale on one machine; the summary records CPU, Python,
  git commit/dirty flag, provider, model and judge settings next to them.
- No payload or answer text is written to any artifact; only case ids,
  labels, decisions and timings.

Run (mock provider, judge off -- pure guard cost):
    .venv\\Scripts\\python.exe scripts/p5/latency_bench.py --label mock-judge-off

Run (Ollama provider, judge on):
    set LLM_PROVIDER=ollama & set SEMANTIC_GUARD_USE_LLM=1
    .venv\\Scripts\\python.exe scripts/p5/latency_bench.py --label ollama-judge-on
"""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

GUARD_STAGES = (
    "history_screen",
    "input_guard",
    "semantic_input",
    "rag_context_guard",
    "output_guard",
    "semantic_output",
)
ALL_STAGES = GUARD_STAGES + ("retrieval", "provider", "semantic_judge_llm")
BLOCKING = frozenset({"block", "human_review"})
P99_MIN_N = 100

# --- per-request timing context -------------------------------------------

class _RequestContext:
    """Process-global, not thread-local: TestClient executes sync endpoints
    in a worker thread, so a thread-local set by the client thread would be
    invisible to the guards. Requests are issued strictly one at a time, so a
    single shared slot is unambiguous; a lock guards the accumulation."""

    def __init__(self) -> None:
        self.stages: dict[str, int] | None = None
        self.lock = threading.Lock()


_ctx = _RequestContext()


def _record(stage: str, elapsed_ns: int) -> None:
    with _ctx.lock:
        bucket = _ctx.stages
        if bucket is None:
            return
        bucket[stage] = bucket.get(stage, 0) + elapsed_ns


def _timed(stage: str, fn: Callable) -> Callable:
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter_ns()
        try:
            return fn(*args, **kwargs)
        finally:
            _record(stage, time.perf_counter_ns() - t0)

    wrapper.__wrapped__ = fn  # type: ignore[attr-defined]
    return wrapper


def install_timers() -> None:
    """Wrap stage functions at the attribute their callers resolve."""
    from app.guards import semantic_guard
    from app.services import gateway
    from app.services import llm_provider
    from app.workspace import routes, store

    routes.screen_history = _timed("history_screen", routes.screen_history)
    store.retrieve = _timed("retrieval", store.retrieve)
    gateway.evaluate_input = _timed("input_guard", gateway.evaluate_input)
    gateway.evaluate_rag_context = _timed("rag_context_guard", gateway.evaluate_rag_context)
    gateway.evaluate_output = _timed("output_guard", gateway.evaluate_output)
    # run_chat imports these two inside the function body on every call, so
    # patching the module attribute is what the import statement will see.
    semantic_guard.evaluate_input_semantic = _timed(
        "semantic_input", semantic_guard.evaluate_input_semantic
    )
    semantic_guard.evaluate_output_semantic = _timed(
        "semantic_output", semantic_guard.evaluate_output_semantic
    )
    semantic_guard._evaluate_with_llm = _timed(
        "semantic_judge_llm", semantic_guard._evaluate_with_llm
    )

    # Force-enable the Ollama judge even when LLM_PROVIDER=mock if requested via
    # SEMANTIC_GUARD_FORCE_LLM=1, so we can isolate Semantic Judge latency from
    # main provider generation latency.
    orig_llm_enabled = semantic_guard._llm_enabled

    def patched_llm_enabled() -> bool:
        if os.getenv("SEMANTIC_GUARD_FORCE_LLM", "0").strip().lower() in {"1", "true", "yes", "on"}:
            return True
        return orig_llm_enabled()

    semantic_guard._llm_enabled = patched_llm_enabled

    original_factory = gateway.get_llm_provider

    def timed_factory(*args, **kwargs):
        provider = original_factory(*args, **kwargs)
        if not getattr(provider, "_p5_timed", False):
            provider.generate = _timed("provider", provider.generate)
            provider._p5_timed = True
        return provider

    gateway.get_llm_provider = timed_factory
    _ = llm_provider  # imported to make sure the module is loaded before patching


# --- harness ---------------------------------------------------------------


def build_client(db_path: Path, username: str, password: str):
    os.environ["WORKSPACE_DB_PATH"] = str(db_path)
    os.environ["WORKSPACE_DOCUMENT_ROOT"] = str(db_path.parent / "_docs")
    os.environ["ENABLE_AUDIT_LOG"] = "false"

    from fastapi.testclient import TestClient

    from app.main import app
    from app.workspace import store

    if Path(store.DB_PATH) != db_path:
        raise SystemExit("store imported before env set; refusing to run against real DB")
    store.initialize()
    auth = store.authenticate(username, password)
    if auth is None:
        raise SystemExit(f"cannot authenticate {username}")
    token, _actor = auth
    # Enter the client's context once: a bare TestClient spins up a fresh
    # event-loop portal per request, which on Windows exhausts socket buffers
    # (WinError 10055) after a few thousand requests and adds per-request
    # setup noise to e2e timings.
    client = TestClient(app)
    client.__enter__()
    return client, {"Authorization": f"Bearer {token}"}


def seed_enterprise_kb() -> None:
    """Run scripts/seed_enterprise_knowledge_base.py against the bench DB.

    The env vars set in `build_client` already point `app.workspace.store`
    at the throwaway database, so this never touches the real workspace.
    """
    import contextlib
    import importlib.util
    import io

    path = REPO_ROOT / "scripts" / "seed_enterprise_knowledge_base.py"
    spec = importlib.util.spec_from_file_location("p5_seed_kb", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    saved = sys.argv
    sys.argv = [str(path)]
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            rc = module.main()
    finally:
        sys.argv = saved
    if rc not in (0, None):
        raise SystemExit(f"KB seeding failed with rc={rc}")


def load_cases(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    rows.sort(key=lambda r: r["id"])
    return rows


def run_one(client, headers, case: dict[str, Any], endpoint: str) -> dict[str, Any]:
    conv = client.post("/v1/conversations", headers=headers, json={"title": f"p5-{case['id']}"})
    conv.raise_for_status()
    cid = conv.json()["id"]

    _ctx.stages = {}
    t0 = time.perf_counter_ns()
    resp = client.post(
        f"/v1/conversations/{cid}/{endpoint}", headers=headers, json={"content": case["content"]}
    )
    e2e_ns = time.perf_counter_ns() - t0
    stages = _ctx.stages
    _ctx.stages = None

    decision = "error"
    provider_called = False
    if resp.status_code == 200:
        body = resp.json()
        decision = (body.get("assistant_message") or {}).get("decision") or "unknown"
        provider_called = bool(body.get("provider_name"))

    stage_ms = {k: v / 1e6 for k, v in stages.items()}
    guard_ms = sum(stage_ms[s] for s in GUARD_STAGES if s in stage_ms)
    return {
        "case_id": case["id"],
        "expected_label": case["expected_label"],
        "decision": decision,
        "blocked": decision in BLOCKING,
        "provider_called": provider_called,
        "http_status": resp.status_code,
        "e2e_ms": e2e_ns / 1e6,
        "guard_overhead_ms": guard_ms,
        "stages_ms": stage_ms,
    }


# --- statistics ------------------------------------------------------------


def _nearest_rank(sorted_vals: list[float], pct: float) -> float:
    k = max(1, math.ceil(pct / 100.0 * len(sorted_vals)))
    return sorted_vals[k - 1]


def summarize(values: list[float]) -> dict[str, Any] | None:
    if not values:
        return None
    s = sorted(values)
    return {
        "n": len(s),
        "mean": round(statistics.fmean(s), 4),
        "p50": round(_nearest_rank(s, 50), 4),
        "p95": round(_nearest_rank(s, 95), 4),
        "p99": round(_nearest_rank(s, 99), 4),
        "max": round(s[-1], 4),
        "p99_reportable": len(s) >= P99_MIN_N,
    }


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def stage_table(subset: list[dict[str, Any]]) -> dict[str, Any]:
        table: dict[str, Any] = {}
        for stage in ALL_STAGES:
            vals = [r["stages_ms"][stage] for r in subset if stage in r["stages_ms"]]
            table[stage] = summarize(vals)
        table["guard_overhead"] = summarize([r["guard_overhead_ms"] for r in subset])
        table["e2e"] = summarize([r["e2e_ms"] for r in subset])
        return table

    ok = [r for r in rows if r["http_status"] == 200]
    return {
        "all": stage_table(ok),
        "stopped_before_provider": stage_table([r for r in ok if not r["provider_called"]]),
        "reached_provider": stage_table([r for r in ok if r["provider_called"]]),
        "counts": {
            "requests": len(rows),
            "errors": len(rows) - len(ok),
            "reached_provider": sum(1 for r in ok if r["provider_called"]),
        },
    }


def environment() -> dict[str, Any]:
    def git(*args: str) -> str:
        try:
            out = subprocess.run(
                ["git", "-c", "safe.directory=*", *args], cwd=REPO_ROOT,
                capture_output=True, text=True, timeout=10,
            )
            return out.stdout.strip()
        except Exception:
            return ""

    from app.core.config import settings

    return {
        "git_commit": git("rev-parse", "HEAD") or "unknown",
        "git_worktree_dirty": bool(git("status", "--porcelain")),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "llm_provider": settings.llm_provider,
        "llm_model_name": settings.llm_model_name,
        "semantic_guard_use_llm": os.getenv("SEMANTIC_GUARD_USE_LLM", "0"),
        "semantic_guard_model": os.getenv("SEMANTIC_GUARD_MODEL", "") or settings.llm_model_name,
        "semantic_guard_timeout_s": os.getenv("SEMANTIC_GUARD_TIMEOUT_SECONDS", "5.0"),
    }


def render_md(label: str, summary: dict[str, Any], env: dict[str, Any]) -> str:
    def fmt(cell: dict[str, Any] | None, key: str) -> str:
        if cell is None:
            return "—"
        if key == "p99" and not cell["p99_reportable"]:
            return f"({cell[key]:.2f})"
        return f"{cell[key]:.2f}"

    lines = [
        f"# P5 latency — {label}",
        "",
        f"Provider `{env['llm_provider']}` / model `{env['llm_model_name']}`; "
        f"Semantic Judge LLM = `{env['semantic_guard_use_llm']}`; commit `{env['git_commit'][:8]}`"
        f"{' (dirty)' if env['git_worktree_dirty'] else ''}; {env['processor']} ({env['cpu_count']} logical CPU).",
        "",
    ]
    for scope, title in (
        ("all", "Tất cả request"),
        ("stopped_before_provider", "Request bị chặn trước LLM"),
        ("reached_provider", "Request đi tới LLM"),
    ):
        table = summary[scope]
        lines += [
            f"## {title}",
            "",
            "| Stage | n | mean ms | p50 ms | p95 ms | p99 ms | max ms |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for stage in ("e2e", "guard_overhead") + ALL_STAGES:
            cell = table.get(stage)
            if cell is None:
                continue
            lines.append(
                f"| {stage} | {cell['n']} | {fmt(cell, 'mean')} | {fmt(cell, 'p50')} | "
                f"{fmt(cell, 'p95')} | {fmt(cell, 'p99')} | {fmt(cell, 'max')} |"
            )
        lines.append("")
    lines += [
        "p99 trong ngoặc = n < 100, nearest-rank p99 chỉ là max, không dùng làm số báo cáo.",
        "`guard_overhead` = tổng các stage guard (không gồm retrieval và provider).",
        "`semantic_judge_llm` lồng bên trong `semantic_input`/`semantic_output`.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cases", default="datasets/v3/cases/all.jsonl")
    ap.add_argument("--output", default="reports/p5/latency")
    ap.add_argument("--label", required=True, help="e.g. mock-judge-off")
    ap.add_argument("--repeats", type=int, default=3, help="passes over the case set")
    ap.add_argument("--warmup", type=int, default=20, help="untimed warm-up requests")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--endpoint", choices=("messages", "messages_unguarded"), default="messages")
    ap.add_argument("--username", default="it.user1")
    ap.add_argument("--password", default="ITUser1#2026")
    ap.add_argument(
        "--seed-kb", action=argparse.BooleanOptionalAction, default=True,
        help="seed datasets/enterprise-kb-full into the throwaway bench DB so retrieval "
             "and the RAG context guard actually run (default on)",
    )
    args = ap.parse_args(argv)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    out_dir = (REPO_ROOT / args.output / f"{run_id}-{args.label}").resolve()
    out_dir.mkdir(parents=True, exist_ok=False)
    db_path = out_dir / "_bench-workspace.db"

    client, headers = build_client(db_path, args.username, args.password)
    if args.seed_kb:
        seed_enterprise_kb()
    install_timers()

    cases = load_cases(REPO_ROOT / args.cases)
    if args.limit:
        cases = cases[: args.limit]

    for case in cases[: args.warmup]:
        run_one(client, headers, case, args.endpoint)

    rows: list[dict[str, Any]] = []
    for rep in range(args.repeats):
        for case in cases:
            row = run_one(client, headers, case, args.endpoint)
            row["repeat"] = rep
            rows.append(row)

    env = environment()
    summary = build_summary(rows)
    meta = {
        "schema": "p5-latency-v1",
        "run_id": run_id,
        "label": args.label,
        "endpoint": args.endpoint,
        "cases_file": args.cases,
        "case_count": len(cases),
        "repeats": args.repeats,
        "warmup": args.warmup,
        "percentile_method": "nearest-rank",
        "environment": env,
        "summary": summary,
    }
    with (out_dir / "latency.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    report = render_md(args.label, summary, env)
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    try:
        db_path.unlink()
    except OSError:
        pass
    print(report)
    print(f"Artifact: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
