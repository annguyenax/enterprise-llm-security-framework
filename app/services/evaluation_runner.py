"""Deterministic, offline evaluation for the synthetic prompt benchmark."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.core.decisions import Decision
from app.guards.input_guard import evaluate_input
from app.guards.output_guard import evaluate_output
from app.guards.rag_guard import evaluate_rag_context
from app.schemas.requests import RAGContextChunk

REQUIRED_FIELDS = {
    "id", "category", "prompt", "expected_behavior",
    "expected_decision", "target_guard", "notes",
}
DECISION_VALUES = tuple(decision.value for decision in Decision)
PROTECTIVE_DECISIONS = {"block", "sanitize", "human_review"}
NON_PROTECTIVE_DECISIONS = {"allow", "log_only"}


@dataclass(frozen=True)
class EvaluationCaseResult:
    id: str
    category: str
    expected_decision: str
    actual_decision: str
    passed: bool
    target_guard: str
    matched_rules: list[str]
    reasons: list[str]
    risk_score: float


@dataclass(frozen=True)
class EvaluationSummary:
    total_cases: int
    passed: int
    failed: int
    pass_rate: float
    counts_by_expected_decision: dict[str, int]
    counts_by_actual_decision: dict[str, int]
    failures_by_category: dict[str, int]
    block_rate: float
    sanitize_rate: float
    human_review_rate: float
    log_only_rate: float
    allow_rate: float
    false_positive_count: int
    false_negative_count: int
    false_positive_rate: float
    false_negative_rate: float
    total_benign_cases: int
    total_attack_cases: int
    attack_success_proxy: float


def load_prompt_cases(path: str | Path) -> list[dict[str, Any]]:
    """Load and validate the frozen JSONL prompt suite."""
    source = Path(path)
    cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    with source.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                case = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc.msg}") from exc
            _validate_case(case, line_number, seen_ids)
            seen_ids.add(case["id"])
            cases.append(case)
    if not cases:
        raise ValueError(f"No evaluation cases found in {source}")
    return cases


def _validate_case(case: Any, line_number: int, seen_ids: set[str]) -> None:
    if not isinstance(case, dict):
        raise ValueError(f"Line {line_number} must contain a JSON object")
    missing = sorted(field for field in REQUIRED_FIELDS if not case.get(field))
    if missing:
        raise ValueError(f"Line {line_number} missing required fields: {', '.join(missing)}")
    if case["id"] in seen_ids:
        raise ValueError(f"Duplicate evaluation id {case['id']!r} on line {line_number}")
    if case["expected_decision"] not in DECISION_VALUES:
        raise ValueError(
            f"Line {line_number} has invalid expected_decision {case['expected_decision']!r}"
        )
    targets = case["target_guard"].split("+")
    valid_targets = {"input_guard", "rag_guard", "output_guard", "gateway"}
    if any(target not in valid_targets for target in targets):
        raise ValueError(f"Line {line_number} has invalid target_guard {case['target_guard']!r}")


def evaluate_cases(cases: list[dict[str, Any]]) -> list[EvaluationCaseResult]:
    """Evaluate cases directly against guards; no provider or network is used."""
    results: list[EvaluationCaseResult] = []
    for case in cases:
        guard_result = _run_target_guard(case)
        actual = guard_result.decision.value
        results.append(EvaluationCaseResult(
            id=case["id"],
            category=case["category"],
            expected_decision=case["expected_decision"],
            actual_decision=actual,
            passed=actual == case["expected_decision"],
            target_guard=case["target_guard"],
            matched_rules=list(guard_result.matched_rules),
            reasons=list(guard_result.reasons),
            risk_score=guard_result.risk_score,
        ))
    return results


def _run_target_guard(case: dict[str, Any]) -> Any:
    targets = set(case["target_guard"].split("+"))
    # Every current gateway and combined prompt case enters through Input Guard.
    # Stopping/decision semantics are therefore measured without invoking the
    # provider. RAG-only and output-only cases remain supported for future suites.
    if "gateway" in targets or "input_guard" in targets:
        return evaluate_input(case["prompt"])
    if "rag_guard" in targets:
        return evaluate_rag_context([
            RAGContextChunk(doc_id=case["id"], text=case["prompt"], metadata={})
        ])
    if "output_guard" in targets:
        return evaluate_output(case["prompt"])
    raise ValueError(f"No supported target guard for {case['id']}")


def summarize_results(results: list[EvaluationCaseResult]) -> EvaluationSummary:
    total = len(results)
    passed = sum(result.passed for result in results)
    expected = Counter(result.expected_decision for result in results)
    actual = Counter(result.actual_decision for result in results)
    failures = Counter(result.category for result in results if not result.passed)
    benign = [result for result in results if result.category == "benign"]
    attacks = [result for result in results if result.category != "benign"]
    false_positives = sum(
        result.expected_decision in {"allow", "log_only"}
        and result.actual_decision in {"block", "human_review"}
        for result in benign
    )
    false_negatives = sum(
        result.expected_decision in PROTECTIVE_DECISIONS
        and result.actual_decision in NON_PROTECTIVE_DECISIONS
        for result in attacks
    )

    return EvaluationSummary(
        total_cases=total,
        passed=passed,
        failed=total - passed,
        pass_rate=_rate(passed, total),
        counts_by_expected_decision=_decision_counts(expected),
        counts_by_actual_decision=_decision_counts(actual),
        failures_by_category=dict(sorted(failures.items())),
        block_rate=_rate(actual["block"], total),
        sanitize_rate=_rate(actual["sanitize"], total),
        human_review_rate=_rate(actual["human_review"], total),
        log_only_rate=_rate(actual["log_only"], total),
        allow_rate=_rate(actual["allow"], total),
        false_positive_count=false_positives,
        false_negative_count=false_negatives,
        false_positive_rate=_rate(false_positives, len(benign)),
        false_negative_rate=_rate(false_negatives, len(attacks)),
        total_benign_cases=len(benign),
        total_attack_cases=len(attacks),
        attack_success_proxy=_rate(false_negatives, len(attacks)),
    )


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _decision_counts(counter: Counter[str]) -> dict[str, int]:
    return {decision: counter[decision] for decision in DECISION_VALUES}


def run_evaluation(path: str | Path) -> tuple[list[EvaluationCaseResult], EvaluationSummary]:
    results = evaluate_cases(load_prompt_cases(path))
    return results, summarize_results(results)


def write_evaluation_reports(
    results: list[EvaluationCaseResult],
    summary: EvaluationSummary,
    output_directory: str | Path,
    source_path: str = "redteam/prompts.jsonl",
) -> tuple[Path, Path]:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "latest-evaluation.json"
    markdown_path = output / "latest-evaluation.md"
    payload = {
        "benchmark_scope": "Controlled synthetic benchmark only; not a real-world rate.",
        "source": source_path,
        "summary": asdict(summary),
        "cases": [asdict(result) for result in results],
    }
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(
        _render_markdown(results, summary, source_path), encoding="utf-8"
    )
    return json_path, markdown_path


def _render_markdown(
    results: list[EvaluationCaseResult], summary: EvaluationSummary, source_path: str
) -> str:
    lines = [
        "# Latest Controlled Benchmark Evaluation", "",
        f"Source: `{source_path}`", "",
        "> These metrics describe only this small synthetic benchmark. They are not real-world detection rates.", "",
        "## Summary", "",
        "| Metric | Value |", "|---|---:|",
        f"| Total cases | {summary.total_cases} |",
        f"| Passed | {summary.passed} |", f"| Failed | {summary.failed} |",
        f"| Pass rate | {summary.pass_rate:.4f} |",
        f"| False positives | {summary.false_positive_count} |",
        f"| False negatives | {summary.false_negative_count} |",
        f"| False positive rate | {summary.false_positive_rate:.4f} |",
        f"| False negative rate | {summary.false_negative_rate:.4f} |",
        f"| Attack success proxy | {summary.attack_success_proxy:.4f} |", "",
        "## Cases", "",
        "| ID | Category | Expected | Actual | Passed |", "|---|---|---|---|---:|",
    ]
    lines.extend(
        f"| {result.id} | {result.category} | {result.expected_decision} | "
        f"{result.actual_decision} | {'yes' if result.passed else 'no'} |"
        for result in results
    )
    lines.extend(["", "## Limitations", "",
        "- Decisions are measured against frozen synthetic prompts and exact expected labels.",
        "- The runner calls guards directly and does not measure model behavior, retrieval quality, latency, or real-world attack outcomes.",
        "- `attack_success_proxy` is a decision-based false-negative proxy, not end-to-end harmful-output ASR.", ""])
    return "\n".join(lines)
