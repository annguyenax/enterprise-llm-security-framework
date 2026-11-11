"""A06: health limits via the 002 provenance-v1 API (mock/in-sample).

Mock with evidence -> is_mock=true, llm_verified=false, every slot
evidenced. Missing evidence -> null/UNKNOWN with a reason; missing key or
wrong llm_verified type -> invalid. is_mock=false never implies
llm_verified=true. NEW-01 (mock + verified=true) and NEW-04 (verified=true
without run-matched realLLM evidence) are invalid. HTTP 200, UI display,
and pycompile are not suite or provider evidence.
"""

from __future__ import annotations

import py_compile
from copy import deepcopy
from dataclasses import replace

import pytest

from app.provenance import (
    SCHEMA_VERSION, SLOT_PATHS, EvidenceSource, unknown_slot, validate_artifact,
)

REQUIRED_BRANCHES = [
    "mock_evidence_valid",
    "each_slot_evidenced",
    "unknown_with_reason_valid",
    "value_without_evidence_invalid",
    "missing_key_invalid",
    "wrong_type_invalid",
    "is_mock_false_not_verified",
    "complete_requires_pytest_exit_zero",
    "junit_error_not_executed",
    "function_name_is_not_a_prefix_match",
    "new01_contradiction",
    "new04_unmatched",
    "new04_structural_positive_insample",
    "http200_not_evidence",
    "pycompile_not_evidence",
]

RUN = "mock-in-sample-run-a06"
EXEC_REF = "mock:offline-a06#execution"
SHA = "ab" * 20


def _slot(value, ref=EXEC_REF, reason=None):
    return {"value": value, "evidence": ref, "reason": reason}


def _mock_claims():
    return {
        "commit_sha": SHA,
        "provider.requested": "mock",
        "provider.effective": "mock",
        "model.requested": "mock-model",
        "model.effective": "mock-model",
        "execution_path": "gateway",
        "storage_backend": "memory",
        "acl_enabled": True,
        "is_mock": True,
        "latency_reportable": False,
        "llm_verified": False,
    }


def mock_artifact_and_sources():
    claims = _mock_claims()
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "run_id": RUN,
        "commit_sha": _slot(claims["commit_sha"]),
        "provider": {"requested": _slot(claims["provider.requested"]),
                     "effective": _slot(claims["provider.effective"])},
        "model": {"requested": _slot(claims["model.requested"]),
                  "effective": _slot(claims["model.effective"])},
        "execution_path": _slot(claims["execution_path"]),
        "storage_backend": _slot(claims["storage_backend"]),
        "acl_enabled": _slot(claims["acl_enabled"]),
        "is_mock": _slot(claims["is_mock"]),
        "latency_reportable": _slot(
            False, reason="Mock/in-sample latency not reportable"),
        "llm_verified": _slot(False),
        "timing": None,
    }
    sources = {EXEC_REF: EvidenceSource(kind="fixture", run_id=RUN,
                                       execution=True, claims=claims)}
    return artifact, sources


def nonmock_artifact_and_sources():
    """is_mock=false base with UNKNOWN verification (in-sample only)."""
    artifact, sources = mock_artifact_and_sources()
    claims = dict(_mock_claims())
    claims.update({"provider.effective": "ollama",
                   "model.effective": "ollama-model", "is_mock": False})
    del claims["llm_verified"]
    artifact["provider"]["effective"] = _slot("ollama")
    artifact["model"]["effective"] = _slot("ollama-model")
    artifact["is_mock"] = _slot(False)
    artifact["latency_reportable"] = unknown_slot(
        "Mock/in-sample reportability unknown")
    artifact["llm_verified"] = unknown_slot(
        "Mock/in-sample verification unknown; is_mock=false proves nothing")
    sources[EXEC_REF] = replace(sources[EXEC_REF], claims=claims)
    return artifact, sources


def _get(artifact, path):
    if "." in path:
        parent, child = path.split(".")
        return artifact[parent][child]
    return artifact[path]


def _put(artifact, path, slot):
    if "." in path:
        parent, child = path.split(".")
        artifact[parent][child] = slot
    else:
        artifact[path] = slot


def test_A06_health_limits_mock_evidence_valid():
    artifact, sources = mock_artifact_and_sources()
    result = validate_artifact(artifact, evidence=sources)
    assert result.valid, [f"{i.path}: {i.message}" for i in result.errors]
    assert artifact["is_mock"]["value"] is True
    assert artifact["llm_verified"]["value"] is False


def test_A06_health_limits_each_slot_evidenced():
    artifact, sources = mock_artifact_and_sources()
    assert validate_artifact(artifact, evidence=sources).valid
    for path in SLOT_PATHS:
        slot = _get(artifact, path)
        assert slot["evidence"], f"slot {path} lacks evidence"


def test_A06_health_limits_unknown_with_reason_valid():
    artifact, sources = nonmock_artifact_and_sources()
    _put(artifact, "commit_sha",
         unknown_slot("Mock/in-sample SHA unknown; no reproducibility claim"))
    _put(artifact, "acl_enabled",
         unknown_slot("Mock/in-sample ACL state unknown"))
    result = validate_artifact(artifact, evidence=sources)
    assert result.valid, [f"{i.path}: {i.message}" for i in result.errors]
    assert _get(artifact, "commit_sha")["value"] is None
    assert _get(artifact, "llm_verified")["value"] is None  # UNKNOWN.


@pytest.mark.parametrize("path", ["commit_sha", "acl_enabled",
                                  "provider.requested"],
                         ids=["value_without_evidence_invalid_sha",
                              "value_without_evidence_invalid_acl",
                              "value_without_evidence_invalid_requested"])
def test_A06_health_limits_value_without_evidence_invalid(path):
    artifact, sources = mock_artifact_and_sources()
    _get(artifact, path)["evidence"] = None  # Claimed value, no evidence.
    assert not validate_artifact(artifact, evidence=sources).valid


def test_A06_health_limits_missing_key_invalid():
    artifact, sources = mock_artifact_and_sources()
    del artifact["llm_verified"]
    result = validate_artifact(artifact, evidence=sources)
    assert not result.valid
    assert any(i.path == "llm_verified" for i in result.errors)


@pytest.mark.parametrize("bad", ["false", 0, 1],
                         ids=["wrong_type_invalid_str",
                              "wrong_type_invalid_zero",
                              "wrong_type_invalid_one"])
def test_A06_health_limits_wrong_type_invalid(bad):
    artifact, sources = mock_artifact_and_sources()
    _put(artifact, "llm_verified", _slot(bad))
    assert not validate_artifact(artifact, evidence=sources).valid


def test_A06_health_limits_is_mock_false_not_verified():
    artifact, sources = nonmock_artifact_and_sources()
    result = validate_artifact(artifact, evidence=sources)
    assert result.valid, [f"{i.path}: {i.message}" for i in result.errors]
    assert artifact["is_mock"]["value"] is False
    assert artifact["llm_verified"]["value"] is None, (
        "is_mock=false must not imply llm_verified=true")


def test_A06_health_limits_new01_contradiction_invalid():
    artifact, sources = mock_artifact_and_sources()
    _put(artifact, "llm_verified", _slot(True))
    sources[EXEC_REF] = replace(
        sources[EXEC_REF], real_llm_response=True,
        claims={**sources[EXEC_REF].claims, "llm_verified": True})
    result = validate_artifact(artifact, evidence=sources)
    assert not result.valid
    assert any("NEW-01" in i.message for i in result.errors)


@pytest.mark.parametrize("case", ["unresolvable", "no_response_flag",
                                  "run_mismatch"],
                         ids=["new04_unmatched_unresolvable",
                              "new04_unmatched_no_response_flag",
                              "new04_unmatched_run_mismatch"])
def test_A06_health_limits_new04_unmatched_invalid(case):
    artifact, sources = nonmock_artifact_and_sources()
    if case == "unresolvable":
        _put(artifact, "llm_verified",
             _slot(True, ref="mock:offline-a06#no-such-source"))
    elif case == "no_response_flag":
        _put(artifact, "llm_verified", _slot(True))
        sources[EXEC_REF] = replace(
            sources[EXEC_REF],
            claims={**sources[EXEC_REF].claims, "llm_verified": True})
    else:
        other = "mock:offline-a06#other-run"
        _put(artifact, "llm_verified", _slot(True, ref=other))
        sources[other] = EvidenceSource(
            kind="fixture", run_id="some-other-run", execution=True,
            real_llm_response=True, claims={"llm_verified": True})
    result = validate_artifact(artifact, evidence=sources)
    assert not result.valid, f"NEW-04 case {case} must be invalid"


def test_A06_health_limits_new04_structural_positive_insample():
    """True + run-matched response attestation validates STRUCTURALLY.

    This is an in-sample fixture check that the validator accepts a fully
    attested shape; it is NOT realLLM proof and claims no real response.
    """
    artifact, sources = nonmock_artifact_and_sources()
    _put(artifact, "llm_verified", _slot(True))
    sources[EXEC_REF] = replace(
        sources[EXEC_REF], real_llm_response=True,
        claims={**sources[EXEC_REF].claims, "llm_verified": True})
    assert artifact["is_mock"]["value"] is False
    assert artifact["provider"]["effective"]["value"] == "ollama"
    result = validate_artifact(artifact, evidence=sources)
    assert result.valid, [f"{i.path}: {i.message}" for i in result.errors]


@pytest.mark.parametrize("ref", ["http-200-ok", "ui-display-shown"],
                         ids=["http200_not_evidence_status",
                              "http200_not_evidence_display"])
def test_A06_health_limits_http200_not_evidence(ref):
    artifact, sources = nonmock_artifact_and_sources()
    _put(artifact, "llm_verified", _slot(True, ref=ref))
    assert not validate_artifact(artifact, evidence=sources).valid, (
        "HTTP status / UI display is not verification evidence")


def test_A06_health_limits_pycompile_not_evidence(tmp_path):
    snippet = tmp_path / "in_sample_snippet.py"
    snippet.write_text("VALUE = 1 + 1\n", encoding="utf-8")
    artifact, sources = nonmock_artifact_and_sources()
    _put(artifact, "llm_verified",
         _slot(True, ref="mock:offline-a06#no-such-source"))
    assert not validate_artifact(artifact, evidence=sources).valid
    assert py_compile.compile(str(snippet), doraise=True)
    assert not validate_artifact(artifact, evidence=sources).valid, (
        "byte-compilation success changes no validation verdict")


def _load_report():
    import importlib
    import sys
    from pathlib import Path
    scripts = Path(__file__).resolve().parents[2] / "scripts" / "offline_suite"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    return importlib.import_module("report")


def test_A06_health_limits_complete_requires_pytest_exit_zero():
    """A complete verdict requires pytest_exit_code == 0 even if all IDs ran."""
    report = _load_report()
    # Invent one passed invocation per logic ID / declared branch so the
    # only remaining gate is the pytest exit code.
    invocations = []
    from pathlib import Path
    repo = Path(__file__).resolve().parents[2]
    declarations = report.collect_branch_declarations(repo)
    for logic_id, info in declarations.items():
        required = info["declared_branches"] or info["test_functions"]
        for branch in required:
            invocations.append({
                "node": f"tests::{logic_id}::{branch}",
                "outcome": "passed",
                "message": "",
                "logic_id": logic_id,
            })
    preflight = {"status": "READY", "dispatch": True, "reasons": []}
    with_nonzero = report.build_report(
        repo_root=repo, preflight=preflight, collection_started=True,
        collection_detail="pytest exit=1", invocations=invocations,
        pytest_exit_code=1)
    assert with_nonzero["verdict"] != "complete"
    assert with_nonzero["collection"]["pytest_exit_code"] == 1
    with_zero = report.build_report(
        repo_root=repo, preflight=preflight, collection_started=True,
        collection_detail="pytest exit=0", invocations=invocations,
        pytest_exit_code=0)
    assert with_zero["verdict"] == "complete", with_zero["verdict_reason"]


def test_A06_health_limits_junit_error_not_executed(tmp_path):
    """Setup/collection <error> is outcome=error and is not an executed body."""
    report = _load_report()
    xml = """<?xml version="1.0" encoding="utf-8"?>
<testsuite tests="2" errors="1" failures="0">
  <testcase classname="tests.offline_suite.test_A03_retrieval_timeout" name="test_A03_retrieval_timeout_ok">
  </testcase>
  <testcase classname="tests.offline_suite.test_A03_retrieval_timeout" name="test_A03_retrieval_timeout_setup">
    <error message="setup failed">fixture error</error>
  </testcase>
</testsuite>
"""
    path = tmp_path / "junit.xml"
    path.write_text(xml, encoding="utf-8")
    invocations = report.parse_junit(path)
    assert {i["outcome"] for i in invocations} == {"passed", "error"}
    err = next(i for i in invocations if i["outcome"] == "error")
    assert "setup" in err["node"]
    # Only passed/failed count as executed bodies for the ID.
    from pathlib import Path
    repo = Path(__file__).resolve().parents[2]
    payload = report.build_report(
        repo_root=repo, preflight={"status": "READY", "dispatch": True},
        collection_started=True, invocations=invocations, pytest_exit_code=1)
    assert payload["counts"]["invocations_errors"] == 1
    assert payload["by_id"]["A03_retrieval_timeout"]["errors"] == 1
    assert payload["by_id"]["A03_retrieval_timeout"]["executed"] is True  # has a passed/failed
    assert payload["verdict"] != "complete"


def test_A06_health_limits_function_name_is_not_a_prefix_match():
    """A passed test_x_extra must not cover an unrun test_x when the file
    declares no REQUIRED_BRANCHES and functions are the required branches."""
    report = _load_report()
    assert report.invocation_covers(
        "tests.offline_suite.test_demo::test_x_extra", "test_x",
        exact_function=True) is False
    assert report.invocation_covers(
        "tests.offline_suite.test_demo::test_x", "test_x",
        exact_function=True) is True
    assert report.invocation_covers(
        "tests.offline_suite.test_demo::test_x[case0]", "test_x",
        exact_function=True) is True
    # Declared branch tags still match as substrings of the node id.
    assert report.invocation_covers(
        "tests.offline_suite.test_A02::test_A02_network_guard_transport_blocked_urlopen",
        "transport_blocked", exact_function=False) is True
