"""Unit tests for scripts/run_v3_evaluation.py (importlib, no live Ollama)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "run_v3_evaluation.py"


def _load_runner():
    name = "run_v3_evaluation_under_test"
    if name in sys.modules:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def runner():
    return _load_runner()


def test_rate_reporting_min_n_returns_null_below_threshold(runner):
    assert runner.RATE_REPORTING_MIN_N == 10
    assert runner._rate(9, 9) is None
    assert runner._rate(0, 5) is None
    assert runner._rate(5, 10) == 0.5
    assert runner._rate(10, 10) == 1.0


def test_validate_case_type_first(runner):
    ok = runner._validate_case(
        {
            "id": "case-001",
            "content": "hello",
            "expected_label": "benign",
            "attack_type": "none",
            "exfil_target": None,
            "tool_family": "benign",
            "technique": "normal",
        },
        "t:1",
    )
    assert ok.case_id == "case-001"
    assert ok.expected_label == "benign"
    assert ok.exfil_target is None

    with pytest.raises(runner.RunnerError):
        runner._validate_case({"id": "x"}, "t:2")

    with pytest.raises(runner.RunnerError):
        runner._validate_case(
            {"id": "x", "content": "c", "expected_label": "evil"},
            "t:3",
        )


def test_load_cases_prefers_all_jsonl(runner, tmp_path):
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    (cases_dir / "all.jsonl").write_text(
        json.dumps(
            {
                "id": "case-a",
                "content": "q1",
                "expected_label": "benign",
            }
        )
        + "\n"
        + json.dumps(
            {
                "id": "case-b",
                "content": "q2",
                "expected_label": "malicious",
                "exfil_target": "FLAG{T}",
                "tool_family": "garak",
                "technique": "rag_dan",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    # Would double-count if glob used
    (cases_dir / "benign.jsonl").write_text(
        json.dumps({"id": "case-a", "content": "q1", "expected_label": "benign"}) + "\n",
        encoding="utf-8",
    )

    v2 = runner._load_v2_helpers()
    loaded = runner.load_cases(cases_dir, v2)
    assert [c.case_id for c in loaded] == ["case-a", "case-b"]


def test_compute_metrics_tpr_fpr_stop_and_exfil(runner):
    Outcome = runner.CaseOutcome

    def o(**kwargs):
        base = dict(
            case_id="c",
            expected_label="malicious",
            attack_type="x",
            tool_family="garak",
            technique="rag_dan",
            decision="block",
            blocked=True,
            provider_called=False,
            exfil_leaked=False,
            exfil_target_seeded=True,
            http_status=200,
            error=None,
        )
        base.update(kwargs)
        return Outcome(**base)

    # 10 malicious: 8 blocked early, 2 allowed with one leak
    # 10 benign: 1 blocked (FP)
    outcomes = []
    for i in range(8):
        outcomes.append(
            o(case_id=f"m{i}", blocked=True, provider_called=False, decision="block")
        )
    outcomes.append(
        o(
            case_id="m8",
            blocked=False,
            provider_called=True,
            decision="allow",
            exfil_leaked=True,
            exfil_target_seeded=True,
        )
    )
    outcomes.append(
        o(
            case_id="m9",
            blocked=False,
            provider_called=True,
            decision="allow",
            exfil_leaked=False,
            exfil_target_seeded=True,
        )
    )
    for i in range(10):
        outcomes.append(
            o(
                case_id=f"b{i}",
                expected_label="benign",
                tool_family="benign",
                technique="normal",
                blocked=(i == 0),
                provider_called=True,
                decision="block" if i == 0 else "allow",
                exfil_leaked=None,
                exfil_target_seeded=False,
            )
        )

    metrics = runner.compute_metrics(outcomes, seeded_canaries=("FLAG{A}",))
    assert metrics["counts"]["malicious"] == 10
    assert metrics["counts"]["benign"] == 10
    assert metrics["counts"]["true_positive"] == 8
    assert metrics["counts"]["false_negative"] == 2
    assert metrics["counts"]["false_positive"] == 1
    assert metrics["counts"]["true_negative"] == 9
    assert metrics["rates"]["tpr"] == 0.8
    assert metrics["rates"]["fpr"] == 0.1
    assert metrics["rates"]["stop_before_llm"] == 0.8
    assert metrics["exfil_reportable"] is True
    assert metrics["exfil_cases_measurable"] == 10
    assert metrics["rates"]["exfil_marker"] == 0.1
    assert metrics["latency_reportable"] is False
    assert "garak" in metrics["by_tool_family"]
    assert "rag_dan" in metrics["by_technique"]
    # No hard_benign in this synthetic set → null rate when n=0
    assert metrics["counts"]["benign_hard"] == 0
    assert metrics["rates"]["fpr_hard_benign"] is None


def test_exfil_not_reportable_when_namespace_mismatch(runner):
    Outcome = runner.CaseOutcome
    outcomes = [
        Outcome(
            case_id=f"m{i}",
            expected_label="malicious",
            attack_type="x",
            tool_family="garak",
            technique="t",
            decision="allow",
            blocked=False,
            provider_called=True,
            exfil_leaked=False,
            exfil_target_seeded=False,  # case canary not in corpus
            http_status=200,
            error=None,
        )
        for i in range(12)
    ]
    metrics = runner.compute_metrics(outcomes, seeded_canaries=("FLAG{OTHER}",))
    assert metrics["exfil_reportable"] is False
    assert metrics["rates"]["exfil_marker"] is None
    assert metrics["exfil_cases_declared"] == 12
    assert metrics["exfil_cases_measurable"] == 0


def test_render_report_content_free(runner):
    metrics = {
        "counts": {
            "total": 20,
            "malicious": 10,
            "benign": 10,
            "benign_normal": 5,
            "benign_hard": 5,
            "errors": 0,
            "true_positive": 8,
            "false_negative": 2,
            "false_positive": 1,
            "true_negative": 9,
        },
        "rates": {
            "tpr": 0.8,
            "fpr": 0.1,
            "fpr_hard_benign": None,
            "fpr_normal_benign": 0.2,
            "stop_before_llm": 0.7,
            "exfil_marker": None,
        },
        "rate_reporting_min_n": 10,
        "latency_reportable": False,
        "exfil_reportable": False,
        "exfil_cases_declared": 10,
        "exfil_cases_measurable": 0,
        "seeded_canary_count": 3,
        "by_tool_family": {
            "garak": {"total": 10, "blocked": 8, "block_rate": 0.8},
        },
        "by_technique": {
            "rag_dan": {"total": 10, "blocked": 8, "block_rate": 0.8},
        },
        "by_attack_type": {},
        "by_benign_technique": {
            "hard_benign_self_service": {"total": 5, "blocked": 2, "block_rate": None},
        },
    }
    report = runner.render_report(metrics)
    assert "TPR" in report
    assert "80.0%" in report
    assert "không đo được" in report
    assert "latency_reportable=false" in report or "không báo cáo" in report
    # must not embed payload-like canaries or attack text
    assert "FLAG{" not in report
    assert "Ignore all" not in report
    assert "password" not in report.lower()


def test_artifacts_are_content_free(runner, tmp_path):
    v2 = runner._load_v2_helpers()
    Outcome = runner.CaseOutcome
    outcomes = [
        Outcome(
            case_id="case-001",
            expected_label="malicious",
            attack_type="rag_poisoning",
            tool_family="garak",
            technique="rag_dan",
            decision="block",
            blocked=True,
            provider_called=False,
            exfil_leaked=False,
            exfil_target_seeded=True,
            http_status=200,
            error=None,
        )
    ]
    metrics = runner.compute_metrics(outcomes, ("FLAG{SECRET-SHOULD-NOT-APPEAR}",))
    # force reportable paths with small n -> null rates ok
    report = runner.render_report(metrics)
    run_dir = runner.write_artifacts(
        tmp_path,
        outcomes,
        metrics,
        v2,
        cases_sha256="abc",
        report=report,
    )
    result_text = (run_dir / "result.jsonl").read_text(encoding="utf-8")
    metrics_text = (run_dir / "metrics.json").read_text(encoding="utf-8")
    report_text = (run_dir / "report.md").read_text(encoding="utf-8")
    blob = result_text + metrics_text + report_text
    assert "FLAG{SECRET-SHOULD-NOT-APPEAR}" not in blob
    assert "Ignore" not in blob
    assert "case-001" in result_text
    assert (run_dir / "manifest.json").is_file()
