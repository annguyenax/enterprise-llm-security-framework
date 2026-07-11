"""Tests for the deterministic Phase 7 controlled-benchmark runner."""
import json
from pathlib import Path

import pytest

from app.services.evaluation_runner import (
    EvaluationCaseResult,
    load_prompt_cases,
    run_evaluation,
    summarize_results,
    write_evaluation_reports,
)
from app.services.llm_provider import MockLLMProvider

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "redteam" / "prompts.jsonl"


def _result(
    case_id: str, category: str, expected: str, actual: str
) -> EvaluationCaseResult:
    return EvaluationCaseResult(
        id=case_id,
        category=category,
        expected_decision=expected,
        actual_decision=actual,
        passed=expected == actual,
        target_guard="input_guard",
        matched_rules=[],
        reasons=[],
        risk_score=0.0,
    )


def test_redteam_jsonl_loads_all_40_cases():
    cases = load_prompt_cases(PROMPTS)
    assert len(cases) == 40
    assert len({case["id"] for case in cases}) == 40


def test_loader_rejects_missing_required_fields(tmp_path):
    invalid = tmp_path / "invalid.jsonl"
    invalid.write_text(json.dumps({"id": "BROKEN"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required fields"):
        load_prompt_cases(invalid)


def test_runner_produces_one_result_per_prompt_without_provider_call(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("evaluation must not call an LLM provider")

    monkeypatch.setattr(MockLLMProvider, "generate", fail_if_called)
    results, summary = run_evaluation(PROMPTS)
    assert len(results) == 40
    assert summary.total_cases == 40
    assert summary.passed + summary.failed == 40
    assert 0.0 <= summary.pass_rate <= 1.0
    assert all(result.id and result.category for result in results)
    assert summary.false_positive_count == 0
    assert summary.false_negative_count == 0
    assert summary.failed == 0


def test_false_positive_and_false_negative_definitions():
    results = [
        _result("B-ALLOW", "benign", "allow", "allow"),
        _result("B-LOG", "benign", "allow", "log_only"),
        _result("B-FP", "benign", "allow", "block"),
        _result("A-BLOCK", "attack", "block", "block"),
        _result("A-FN-ALLOW", "attack", "block", "allow"),
        _result("A-FN-LOG", "attack", "sanitize", "log_only"),
    ]
    summary = summarize_results(results)
    assert summary.false_positive_count == 1
    assert summary.false_negative_count == 2
    assert summary.false_positive_rate == pytest.approx(1 / 3)
    assert summary.false_negative_rate == pytest.approx(2 / 3)
    assert summary.attack_success_proxy == summary.false_negative_rate
    assert summary.counts_by_actual_decision["human_review"] == 0


def test_report_files_are_created_and_contain_scope_warning(tmp_path):
    results = [_result("B-1", "benign", "allow", "allow")]
    summary = summarize_results(results)
    json_path, markdown_path = write_evaluation_reports(results, summary, tmp_path)

    assert json_path.exists()
    assert markdown_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["summary"]["total_cases"] == 1
    assert payload["cases"][0]["id"] == "B-1"
    assert "not a real-world rate" in payload["benchmark_scope"]
    assert "not real-world detection rates" in markdown_path.read_text(encoding="utf-8")
