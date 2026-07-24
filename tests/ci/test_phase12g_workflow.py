from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "phase12g-release-gates.yml"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _run_blocks(text: str) -> str:
    lines = text.splitlines()
    collected: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if not stripped.startswith("run:"):
            index += 1
            continue
        collected.append(stripped.removeprefix("run:").strip())
        index += 1
        while index < len(lines):
            candidate = lines[index]
            candidate_stripped = candidate.lstrip()
            candidate_indent = len(candidate) - len(candidate_stripped)
            if candidate_stripped and candidate_indent <= indent:
                break
            collected.append(candidate_stripped)
            index += 1
    return "\n".join(collected)


def test_workflow_has_windows_ubuntu_and_supported_python_matrix():
    text = _text()
    assert "ubuntu-latest" in text
    assert "windows-latest" in text
    assert 'python-version: "3.11"' in text
    assert "PROJECT_PLAN" not in text


def test_workflow_uses_least_privilege_and_non_persistent_checkout():
    text = _text()
    lowered = text.lower()
    assert text.count("contents: read") >= 2
    assert "persist-credentials: false" in text
    assert "pull_request_target" not in text
    assert "permissions: write" not in lowered
    assert "contents: write" not in lowered
    assert "id-token: write" not in lowered
    assert "secrets." not in lowered


def test_workflow_has_explicit_job_and_step_timeouts():
    text = _text()
    assert "timeout-minutes: 25" in text
    assert text.count("timeout-minutes:") >= 5


def test_dependency_install_and_cache_are_bound_to_declared_file():
    text = _text()
    commands = _run_blocks(text)
    assert "cache: pip" in text
    assert "cache-dependency-path: requirements.txt" in text
    assert "pip install --disable-pip-version-check -r requirements.txt" in commands
    assert "pip install -e" not in commands
    assert "pip install git+" not in commands


def test_workflow_runs_policy_inventory_compile_and_synthetic_tests():
    text = _text()
    commands = _run_blocks(text)
    assert "compileall -q app scripts" in commands
    assert "scripts/ci/check_repository_policy.py" in commands
    assert "--require-clean-tree" in commands
    assert "scripts/ci/build_dependency_inventory.py" in commands
    assert "tests/ci" in commands
    assert "tests/test_v2_release_artifacts.py" in commands
    assert "tests/phase12f" in commands
    assert "-p no:cacheprovider" in commands
    assert "--basetemp=" in commands


def test_workflow_has_no_evaluation_or_private_materialization_command():
    commands = _run_blocks(_text()).casefold()
    prohibited_commands = (
        "run_v2_evaluation.py",
        "analyze_v2_results.py",
        "--split validation",
        "--split holdout",
        "freeze_v2_benchmark.py verify",
        "materialize_v2_frozen_artifacts.py",
        "build_v2_benchmark.py",
    )
    for command in prohibited_commands:
        assert command not in commands


def test_private_artifact_limitation_and_fail_closed_scope_are_disclosed():
    text = _text().casefold()
    assert "public ci deliberately has no access" in text
    assert "does not download, reconstruct" in text
    assert "does not reproduce the full private-artifact test suite" in text
    assert "missing private source fails closed" in text
    assert "temporary synthetic bytes only" in text


def test_public_ci_does_not_fabricate_repository_datasets():
    commands = _run_blocks(_text()).casefold()
    assert "datasets/v2/cases" not in commands
    assert "datasets/v2/labels" not in commands
    assert "redteam/prompts.jsonl" not in commands
    assert "copy-item" not in commands
    assert "curl " not in commands
    assert "wget " not in commands


def test_archived_artifacts_are_only_content_free_gate_reports():
    text = _text()
    upload_section = text.split("- name: Archive content-free gate reports", 1)[1]
    assert "phase12g-policy.json" in upload_section
    assert "phase12g-policy.md" in upload_section
    assert "phase12g-dependencies.json" in upload_section
    assert "phase12g-dependencies.md" in upload_section
    for prohibited in ("*.jsonl", "result.json", "analysis.json", "audit.log", "pytest.xml"):
        assert prohibited not in upload_section


def test_workflow_is_structurally_stable_and_has_no_tabs():
    text = _text()
    assert text.startswith("name: Phase 12G Public Release Gates\n")
    assert "\non:\n" in text
    assert "\njobs:\n" in text
    assert "\n  public-release-gates:\n" in text
    assert "strategy:" in text
    assert "matrix:" in text
    assert "\t" not in text
    assert text.endswith("\n")