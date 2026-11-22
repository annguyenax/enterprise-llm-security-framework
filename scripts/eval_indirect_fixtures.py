"""Run the Result Guard over the indirect-injection fixture library and print
per-split counts. Deterministic, offline, no LLM.

This is a guard-only measurement on synthetic fixtures written by the same
author as the rules. Rules were tuned on `dev` only. Treat `holdout` numbers
as a sanity check, not as a reportable detection rate.

Usage:
    python scripts/eval_indirect_fixtures.py [--show-misses]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.sql_agent.models import SqlExecution  # noqa: E402
from app.sql_agent.result_guard import guard_rows  # noqa: E402


def flagged(column: str, text: str) -> bool:
    out = guard_rows(SqlExecution(columns=[column], rows=[[text]]))
    return out.rows[0][0] != text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show-misses", action="store_true")
    args = ap.parse_args(argv)
    lib = json.loads((ROOT / "datasets/furniture/attacks/indirect-rows.json").read_text(encoding="utf-8"))
    for split in ("dev", "holdout"):
        rows = [a for a in lib["attacks"] if a["split"] == split]
        caught = [a for a in rows if flagged(a["column"], a["text"])]
        print(f"{split:8s} attacks flagged: {len(caught)}/{len(rows)}")
        if args.show_misses:
            for a in rows:
                if a not in caught:
                    print(f"   miss {a['id']} {a['attack_type']}")
    ben = lib["benign"]
    fps = [b for b in ben if flagged(b["column"], b["text"])]
    print(f"benign   flagged (false positives): {len(fps)}/{len(ben)}")
    if args.show_misses:
        for b in fps:
            print(f"   fp {b['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
