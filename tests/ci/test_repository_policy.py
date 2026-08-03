from __future__ import annotations

import json
from collections.abc import Iterable

import pytest

from scripts.ci import check_repository_policy as policy


BASE_PATHS = (
    "README.md",
    "datasets/v2/manifests/benchmark-v2-manifest.json",
    "redteam/prompts-manifest.json",
)


def _reader(contents: dict[str, bytes] | None = None):
    values = contents or {}

    def read(path: str) -> bytes:
        return values.get(path, b"")

    return read


def _report(
    extra: Iterable[str] = (),
    *,
    contents: dict[str, bytes] | None = None,
    require_clean_tree: bool = False,
    tree_clean: bool | None = None,
):
    return policy.evaluate_policy(
        (*BASE_PATHS, *extra),
        read_bytes=_reader(contents),
        require_clean_tree=require_clean_tree,
        tree_clean=tree_clean,
    )


def _codes(report: dict[str, object]) -> set[str]:
    return {finding["code"] for finding in report["findings"]}  # type: ignore[index]


def test_minimal_safe_tree_passes_without_clean_tree_selection():
    report = _report()
    assert report["status"] == "PASS"
    clean_check = next(item for item in report["checks"] if item["id"] == "clean_worktree")
    assert clean_check["status"] == "NOT_SELECTED"


def test_tracked_jsonl_is_rejected():
    report = _report(("datasets/v2/cases/private.jsonl",))
    assert report["status"] == "FAIL"
    assert "tracked_jsonl" in _codes(report)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (".env", "tracked_environment"),
        ("config/.env.production", "tracked_environment"),
        ("secrets/private.pem", "tracked_credentials"),
        ("secrets/credentials.json", "tracked_credentials"),
        ("data/runtime.sqlite3", "tracked_database"),
        ("pkg/__pycache__/module.pyc", "tracked_generated_output"),
        ("build/output.txt", "tracked_generated_output"),
    ],
)
def test_secret_database_and_generated_paths_are_rejected(path: str, expected: str):
    report = _report((path,))
    assert expected in _codes(report)


def test_safe_environment_template_is_allowed():
    assert _report((".env.example",))["status"] == "PASS"


def test_required_manifests_are_enforced():
    report = policy.evaluate_policy(("README.md",), read_bytes=_reader())
    missing = [item for item in report["findings"] if item["code"] == "required_manifest_missing"]
    assert {item["path"] for item in missing} == set(policy.REQUIRED_MANIFESTS)


def test_release_policy_files_are_required_when_phase12f_is_integrated():
    report = _report(("scripts/phase12f/common.py",))
    assert "release_policy_missing" in _codes(report)
    assert sum(item["code"] == "release_policy_missing" for item in report["findings"]) == len(
        policy.RELEASE_POLICY_FILES
    )


def test_complete_release_policy_set_passes():
    report = _report(("scripts/phase12f/common.py", *policy.RELEASE_POLICY_FILES))
    assert report["status"] == "PASS"


def test_exact_conflict_marker_is_detected_without_content_disclosure():
    marker = ("<" * 7 + " HEAD").encode("ascii")
    secret = b"DO_NOT_DISCLOSE_SENTINEL"
    contents = {"module.py": marker + b"\n" + secret + b"\n"}
    report = _report(("module.py",), contents=contents)
    assert "conflict_marker" in _codes(report)
    json_output = policy.canonical_json_bytes(report)
    markdown_output = policy.render_markdown(report).encode("utf-8")
    assert secret not in json_output
    assert secret not in markdown_output


def test_long_separator_is_not_a_conflict_marker():
    contents = {"notes.md": b"=" * 70 + b"\n"}
    assert _report(("notes.md",), contents=contents)["status"] == "PASS"


def test_case_colliding_paths_are_rejected():
    report = _report(("docs/Policy.md", "docs/policy.md"))
    collision = next(item for item in report["findings"] if item["code"] == "case_collision")
    assert {collision["path"], collision["related_path"]} == {
        "docs/Policy.md",
        "docs/policy.md",
    }


@pytest.mark.parametrize(
    "path",
    [
        "/absolute.txt",
        "C:/absolute.txt",
        "docs/../secret.txt",
        "docs\\portable.txt",
    ],
)
def test_absolute_and_traversal_like_paths_are_rejected(path: str):
    assert "unsafe_tracked_path" in _codes(_report((path,)))


@pytest.mark.parametrize(
    "path",
    [
        "reports/evaluation-v2/result.json",
        "evidence/phase12e4/start.json",
        "external/phase12e4-attempt-1/result-manifest.json",
        "records/start-receipt.json",
    ],
)
def test_phase12e4_evidence_paths_are_rejected(path: str):
    assert "phase12e4_evidence" in _codes(_report((path,)))


def test_clean_tree_gate_is_optional_but_fail_closed_when_selected():
    not_selected = _report(require_clean_tree=False, tree_clean=False)
    selected_dirty = _report(require_clean_tree=True, tree_clean=False)
    selected_clean = _report(require_clean_tree=True, tree_clean=True)
    assert not_selected["status"] == "PASS"
    assert "dirty_worktree" in _codes(selected_dirty)
    assert selected_clean["status"] == "PASS"


def test_json_is_canonical_and_has_no_absolute_repository_path():
    report = _report()
    encoded = policy.canonical_json_bytes(report)
    parsed = json.loads(encoded)
    assert encoded.endswith(b"\n")
    assert encoded == policy.canonical_json_bytes(parsed)
    assert b"D:\\" not in encoded
    assert parsed["claim_boundary"] == "MECHANICAL_REPOSITORY_POLICY_ONLY"