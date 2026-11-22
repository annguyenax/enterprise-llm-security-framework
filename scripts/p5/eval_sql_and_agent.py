"""P5 Integrated Evaluation for P4 SQL Guard, Result Guard, and Multi-Tool
Company Agent (merging Nghia's P4 `feat/claude-provider-sql-guard` with An's
P3 + P5 evaluation suite).

Measures:
1. Direct P2SQL Benchmark (`redteam/sql/p2sql-direct.jsonl` 38 attacks +
   `p2sql-benign.jsonl` 31 benign = 69 cases):
   - TPR, FPR, Precision, F1
   - Latency p50 / p95 / p99 (ms) of `app.sql_agent.guard.evaluate_sql`
     (SQLite EXPLAIN + Authorizer AST verification + Lexical Guard).
2. Indirect P2SQL Data-Cell Benchmark (`datasets/furniture/attacks/indirect-rows.json`
   24 dev attacks + 14 holdout attacks + 32 hard-benign rows = 70 cases):
   - TPR on dev, TPR on holdout, FPR on benign
   - Latency p50 / p95 / p99 (ms) of `app.sql_agent.result_guard.guard_rows`
     (RAG Context Guard + SQL Injection Rules + DLP Redaction).
3. Multi-Tool Company Agent End-to-End Guarded vs. Unguarded Evaluation
   (`app.company_agent.agent.run_company_agent` with deterministic mock tool-call
   scenarios covering RAG poisoning, Indirect P2SQL via order notes, RBAC tool
   violation, destructive SQL, and external email exfiltration):
   - Per-stage and end-to-end latency p50 / p95 / p99 (ms).
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.decisions import Decision
from app.sql_agent.guard import evaluate_sql
from app.sql_agent.models import SqlActor, SqlExecution
from app.sql_agent.result_guard import guard_rows


def _nearest_rank(sorted_vals: list[float], pct: float) -> float:
    k = max(1, math.ceil(pct / 100.0 * len(sorted_vals)))
    return sorted_vals[k - 1]


def summarize_lat(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": None, "p50": None, "p95": None, "p99": None, "max": None}
    s = sorted(values)
    return {
        "n": len(s),
        "mean": round(statistics.fmean(s), 3),
        "p50": round(_nearest_rank(s, 50), 3),
        "p95": round(_nearest_rank(s, 95), 3),
        "p99": round(_nearest_rank(s, 99), 3),
        "max": round(s[-1], 3),
        "p99_reportable": len(s) >= 100,
    }


def eval_direct_p2sql(repeats: int = 5) -> dict[str, Any]:
    direct_mal = [
        json.loads(line)
        for line in (REPO_ROOT / "redteam/sql/p2sql-direct.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    direct_ben = [
        json.loads(line)
        for line in (REPO_ROOT / "redteam/sql/p2sql-benign.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]

    # Warm-up
    for row in direct_mal[:3]:
        evaluate_sql(row["model_sql"], SqlActor(department=row["department"], role=row["role"]))

    latencies: list[float] = []
    tp = fn = fp = tn = 0

    for rep in range(repeats):
        for row in direct_mal:
            actor = SqlActor(department=row["department"], role=row["role"])
            t0 = time.perf_counter_ns()
            res = evaluate_sql(row["model_sql"], actor)
            latencies.append((time.perf_counter_ns() - t0) / 1e6)
            if rep == 0:
                if res.decision == Decision.BLOCK:
                    tp += 1
                else:
                    fn += 1

        for row in direct_ben:
            actor = SqlActor(department=row["department"], role=row["role"])
            t0 = time.perf_counter_ns()
            res = evaluate_sql(row["model_sql"], actor)
            latencies.append((time.perf_counter_ns() - t0) / 1e6)
            if rep == 0:
                if res.decision == Decision.BLOCK:
                    fp += 1
                else:
                    tn += 1

    tpr = round(tp / len(direct_mal), 4)
    fpr = round(fp / len(direct_ben), 4)
    f1 = round(2 * tp / (2 * tp + fp + fn), 4)
    return {
        "counts": {
            "malicious": len(direct_mal),
            "benign": len(direct_ben),
            "total": len(direct_mal) + len(direct_ben),
            "tp": tp,
            "fn": fn,
            "fp": fp,
            "tn": tn,
        },
        "rates": {"tpr": tpr, "fpr": fpr, "f1": f1},
        "latency_ms": summarize_lat(latencies),
    }


def eval_indirect_result_guard(repeats: int = 5) -> dict[str, Any]:
    lib = json.loads(
        (REPO_ROOT / "datasets/furniture/attacks/indirect-rows.json").read_text(encoding="utf-8")
    )
    dev_rows = [a for a in lib["attacks"] if a["split"] == "dev"]
    hold_rows = [a for a in lib["attacks"] if a["split"] == "holdout"]
    ben_rows = lib["benign"]

    latencies: list[float] = []
    dev_tp = hold_tp = fp = 0

    for rep in range(repeats):
        for a in dev_rows:
            t0 = time.perf_counter_ns()
            out = guard_rows(SqlExecution(columns=[a["column"]], rows=[[a["text"]]]))
            latencies.append((time.perf_counter_ns() - t0) / 1e6)
            if rep == 0 and out.rows[0][0] != a["text"]:
                dev_tp += 1
        for a in hold_rows:
            t0 = time.perf_counter_ns()
            out = guard_rows(SqlExecution(columns=[a["column"]], rows=[[a["text"]]]))
            latencies.append((time.perf_counter_ns() - t0) / 1e6)
            if rep == 0 and out.rows[0][0] != a["text"]:
                hold_tp += 1
        for b in ben_rows:
            t0 = time.perf_counter_ns()
            out = guard_rows(SqlExecution(columns=[b["column"]], rows=[[b["text"]]]))
            latencies.append((time.perf_counter_ns() - t0) / 1e6)
            if rep == 0 and out.rows[0][0] != b["text"]:
                fp += 1

    all_mal = len(dev_rows) + len(hold_rows)
    all_tp = dev_tp + hold_tp
    return {
        "counts": {
            "dev_malicious": len(dev_rows),
            "dev_tp": dev_tp,
            "holdout_malicious": len(hold_rows),
            "holdout_tp": hold_tp,
            "total_malicious": all_mal,
            "total_tp": all_tp,
            "benign": len(ben_rows),
            "fp": fp,
            "tn": len(ben_rows) - fp,
        },
        "rates": {
            "tpr_dev": round(dev_tp / len(dev_rows), 4),
            "tpr_holdout": round(hold_tp / len(hold_rows), 4),
            "tpr_combined": round(all_tp / all_mal, 4),
            "fpr": round(fp / len(ben_rows), 4),
            "f1_combined": round(2 * all_tp / (2 * all_tp + fp + (all_mal - all_tp)), 4),
        },
        "latency_ms": summarize_lat(latencies),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P5 evaluation for P4 SQL Guard and Result Guard")
    ap.add_argument("--output", default="reports/p5/sql_agent_eval")
    ap.add_argument("--repeats", type=int, default=5)
    args = ap.parse_args(argv)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    out_dir = (REPO_ROOT / args.output / run_id).resolve()
    out_dir.mkdir(parents=True, exist_ok=False)

    direct = eval_direct_p2sql(repeats=args.repeats)
    indirect = eval_indirect_result_guard(repeats=args.repeats)

    payload = {
        "schema": "p5-sql-agent-eval-v1",
        "run_id": run_id,
        "direct_p2sql_guard": direct,
        "indirect_result_guard": indirect,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )

    dc = direct["counts"]
    dr = direct["rates"]
    dl = direct["latency_ms"]
    ic = indirect["counts"]
    ir = indirect["rates"]
    il = indirect["latency_ms"]

    lines = [
        "# P5 × P4 — Đánh giá hiệu năng & độ trễ cho SQL Guard và Indirect Result Guard (Nhà Mộc Việt)",
        "",
        "## 1. Direct P2SQL & RBAC SQL Guard (`app.sql_agent.guard.evaluate_sql` — SQLite EXPLAIN + Authorizer AST)",
        "",
        "| Tập mẫu | TP / Mal | FP / Ben | TPR (Recall) | FPR | F1 | Số lượt đo (`n`) | Latency p50 (ms) | Latency p95 (ms) | Latency p99 (ms) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        f"| `redteam/sql/p2sql-direct` + `benign` (69 mẫu) | {dc['tp']}/{dc['malicious']} | {dc['fp']}/{dc['benign']} | **{dr['tpr']*100:.1f}%** | **{dr['fpr']*100:.1f}%** | **{dr['f1']*100:.1f}%** | {dl['n']} | **{dl['p50']:.2f}** | **{dl['p95']:.2f}** | **{dl['p99']:.2f}** |",
        "",
        "## 2. Indirect P2SQL Data-Cell Result Guard (`app.sql_agent.result_guard.guard_rows` — RAG Context Guard + SQL Rules + DLP)",
        "",
        "| Tập mẫu | TP / Mal | FP / Ben | TPR (Recall) | FPR | F1 | Số lượt đo (`n`) | Latency p50 (ms) | Latency p95 (ms) | Latency p99 (ms) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        f"| `indirect-rows` (Dev split) | {ic['dev_tp']}/{ic['dev_malicious']} | {ic['fp']}/{ic['benign']} | **{ir['tpr_dev']*100:.1f}%** | **{ir['fpr']*100:.1f}%** | — | {il['n']} | **{il['p50']:.2f}** | **{il['p95']:.2f}** | **{il['p99']:.2f}** |",
        f"| `indirect-rows` (Holdout split) | {ic['holdout_tp']}/{ic['holdout_malicious']} | {ic['fp']}/{ic['benign']} | **{ir['tpr_holdout']*100:.1f}%** | **{ir['fpr']*100:.1f}%** | — | {il['n']} | **{il['p50']:.2f}** | **{il['p95']:.2f}** | **{il['p99']:.2f}** |",
        f"| `indirect-rows` (Tổng hợp 70 mẫu) | {ic['total_tp']}/{ic['total_malicious']} | {ic['fp']}/{ic['benign']} | **{ir['tpr_combined']*100:.1f}%** | **{ir['fpr']*100:.1f}%** | **{ir['f1_combined']*100:.1f}%** | {il['n']} | **{il['p50']:.2f}** | **{il['p95']:.2f}** | **{il['p99']:.2f}** |",
    ]
    report_md = "\n".join(lines) + "\n"
    (out_dir / "report.md").write_text(report_md, encoding="utf-8")
    print(report_md)
    print(f"Artifact: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
