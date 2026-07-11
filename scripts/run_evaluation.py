"""Run the controlled synthetic benchmark and write reproducible reports."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.evaluation_runner import run_evaluation, write_evaluation_reports


def main() -> int:
    source = ROOT / "redteam" / "prompts.jsonl"
    output = ROOT / "reports" / "evaluation"
    results, summary = run_evaluation(source)
    json_path, markdown_path = write_evaluation_reports(
        results, summary, output, "redteam/prompts.jsonl"
    )
    print("Controlled synthetic benchmark evaluation")
    print(f"Cases: {summary.total_cases}")
    print(f"Passed: {summary.passed}")
    print(f"Failed: {summary.failed}")
    print(f"Pass rate: {summary.pass_rate:.4f}")
    print(f"False positives: {summary.false_positive_count}")
    print(f"False negatives: {summary.false_negative_count}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")
    print("Scope: controlled synthetic benchmark only; not a real-world rate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
