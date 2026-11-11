"""Launcher for the offline availability suite (11 logic IDs: 5 P + 6 A).

Flow: real preflight (no pytest import needed to start) -> if blocked,
write a blocked report with executed=0 and exit nonzero WITHOUT starting
pytest; otherwise run pytest via subprocess on tests/offline_suite +
tests/provenance_v1, parse --junitxml, and write the report.

All results are mock/in-sample. This launcher never claims realLLM,
holdout, production, or any gate PASS.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import preflight  # noqa: E402  (stdlib-only sibling; never imports pytest)
import report  # noqa: E402

LABEL = "mock/in-sample"


def run_pytest(repo_root: Path, junit_path: Path) -> tuple[int, str]:
    cmd = [sys.executable, "-m", "pytest", "-q",
           "tests/offline_suite", "tests/provenance_v1",
           f"--junitxml={junit_path}", "-p", "no:cacheprovider"]
    proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True,
                          timeout=1200)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the offline availability suite (mock/in-sample).")
    parser.add_argument("--repo-root", default=".",
                        help="Repository root.")
    parser.add_argument("--report", required=True,
                        help="Path to write the JSON suite report.")
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()

    decision = preflight.run_preflight(repo_root)
    if not decision.dispatch:
        payload = report.build_report(
            repo_root=repo_root, preflight=decision.to_dict(),
            collection_started=False,
            collection_detail=f"preflight {decision.status}: "
                              f"{'; '.join(decision.reasons)}")
        Path(args.report).write_text(json.dumps(payload, indent=2) + "\n",
                                     encoding="utf-8")
        print(f"preflight {decision.status}: runner never started; "
              f"executed=0; report -> {args.report}")
        print(f"reasons: {'; '.join(decision.reasons)}")
        return decision.exit_code

    with tempfile.TemporaryDirectory(prefix="shield-003-") as tmp:
        junit_path = Path(tmp) / "results.xml"
        try:
            exit_code, output = run_pytest(repo_root, junit_path)
        except subprocess.TimeoutExpired:
            payload = report.build_report(
                repo_root=repo_root, preflight=decision.to_dict(),
                collection_started=True,
                collection_detail="pytest run timed out after 1200s")
            Path(args.report).write_text(json.dumps(payload, indent=2) + "\n",
                                         encoding="utf-8")
            print(f"pytest run timed out; report -> {args.report}")
            return 5
        print(output)
        try:
            invocations = report.parse_junit(junit_path)
        except Exception as exc:
            payload = report.build_report(
                repo_root=repo_root, preflight=decision.to_dict(),
                collection_started=True,
                collection_detail=f"junit XML unparseable: {exc}")
            Path(args.report).write_text(json.dumps(payload, indent=2) + "\n",
                                         encoding="utf-8")
            print(f"junit XML unparseable ({exc}); report -> {args.report}")
            return 6
        payload = report.build_report(
            repo_root=repo_root, preflight=decision.to_dict(),
            collection_started=True,
            collection_detail=f"pytest exit={exit_code}",
            invocations=invocations, pytest_exit_code=exit_code)
    Path(args.report).write_text(json.dumps(payload, indent=2) + "\n",
                                 encoding="utf-8")
    counts = payload["counts"]
    print(f"verdict={payload['verdict']}: {payload['verdict_reason']}")
    print(f"logic executed={counts['logic_executed']}/11; "
          f"invocations total={counts['invocations_total']} "
          f"(passed={counts['invocations_passed']}, "
          f"failed={counts['invocations_failed']}, "
          f"skipped={counts['invocations_skipped']}, "
          f"xfailed={counts['invocations_xfailed']})")
    print(f"report -> {args.report}")
    return 0 if payload["verdict"] == "complete" else 7


if __name__ == "__main__":
    sys.exit(main())
