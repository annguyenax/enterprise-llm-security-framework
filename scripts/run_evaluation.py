"""Run the controlled synthetic benchmark and write reproducible reports."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.evaluation_runner import (
    run_comparison,
    run_evaluation,
    write_comparison_reports,
    write_evaluation_reports,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--comparison",
        action="store_true",
        help="Generate the always-allow baseline vs guarded comparison reports.",
    )
    args = parser.parse_args()
    source = ROOT / "redteam" / "prompts.jsonl"
    output = ROOT / "reports" / "evaluation"
    if args.comparison:
        baseline_results, baseline, guarded_results, guarded = run_comparison(source)
        json_path, markdown_path = write_comparison_reports(
            baseline_results,
            baseline,
            guarded_results,
            guarded,
            output,
            "redteam/prompts.jsonl",
        )
        print("Controlled synthetic baseline vs guarded comparison")
        print(
            f"Baseline: {baseline.passed}/{baseline.total_cases} passed, "
            f"false negatives={baseline.false_negative_count}, "
            f"attack success proxy={baseline.attack_success_proxy:.4f}"
        )
        print(
            f"Guarded: {guarded.passed}/{guarded.total_cases} passed, "
            f"false negatives={guarded.false_negative_count}, "
            f"attack success proxy={guarded.attack_success_proxy:.4f}"
        )
        print(f"JSON report: {json_path}")
        print(f"Markdown report: {markdown_path}")
        print("Baseline is an always-allow decision baseline, not a real LLM quality baseline.")
        return 0

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
