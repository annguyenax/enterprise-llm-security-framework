from __future__ import annotations

import json
from pathlib import Path

from scripts.ci import build_dependency_inventory as inventory


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _codes(report: dict[str, object]) -> set[str]:
    return {finding["code"] for finding in report["findings"]}  # type: ignore[index]


def test_registry_requirements_are_classified_without_network(tmp_path: Path):
    _write(
        tmp_path / "requirements.txt",
        "pinned_pkg==1.2.3\n"
        "bounded_pkg>=2.0,<3.0\n"
        "compatible_pkg~=4.1\n"
        "lower_only>=5\n"
        "bare_pkg\n",
    )
    report = inventory.build_inventory(tmp_path)
    classes = {
        item["canonical_name"]: item["classification"]
        for item in report["requirements"]  # type: ignore[index]
    }
    assert classes == {
        "pinned-pkg": "pinned",
        "bounded-pkg": "bounded",
        "compatible-pkg": "bounded",
        "lower-only": "unbounded",
        "bare-pkg": "unbounded",
    }
    assert report["network_used"] is False
    assert report["installed_environment_inspected"] is False
    assert report["vulnerability_status"] == "NOT_CHECKED"


def test_extras_markers_and_hash_count_are_recorded_safely(tmp_path: Path):
    _write(
        tmp_path / "requirements.txt",
        'uvicorn[standard]>=0.27,<1.0 ; python_version >= "3.11" '
        '--hash=sha256:deadbeef\n',
    )
    report = inventory.build_inventory(tmp_path)
    requirement = report["requirements"][0]  # type: ignore[index]
    assert requirement["canonical_name"] == "uvicorn"
    assert requirement["extras"] == ["standard"]
    assert requirement["marker_present"] is True
    assert requirement["hash_count"] == 1
    assert requirement["classification"] == "bounded"


def test_vcs_url_editable_and_local_sources_are_flagged_and_redacted(tmp_path: Path):
    token = "TOP_SECRET_DEPENDENCY_TOKEN"
    _write(
        tmp_path / "requirements.txt",
        "direct_pkg @ https://user:" + token + "@example.invalid/pkg.whl\n"
        "git+https://github.com/example/project.git#egg=vcs_pkg\n"
        "-e ../local-package\n",
    )
    report = inventory.build_inventory(tmp_path)
    codes = _codes(report)
    assert {
        "direct_url_dependency",
        "credential_in_dependency_source",
        "suspicious_dependency_source",
        "vcs_dependency",
        "editable_dependency",
        "local_path_dependency",
    } <= codes
    encoded = inventory.canonical_json_bytes(report)
    markdown = inventory.render_markdown(report).encode("utf-8")
    assert token.encode("ascii") not in encoded
    assert token.encode("ascii") not in markdown
    assert b"example.invalid/pkg.whl" not in encoded
    assert all(
        item["constraint"] in {"<direct-reference>", "<local-reference>"}
        for item in report["requirements"]  # type: ignore[index]
    )


def test_insecure_and_custom_source_directives_are_flagged_without_url_output(tmp_path: Path):
    private_url = "http://user:password@packages.internal/simple"
    _write(
        tmp_path / "requirements.txt",
        f"--extra-index-url {private_url}\n"
        "--trusted-host packages.internal\n"
        "safe_pkg>=1,<2\n",
    )
    report = inventory.build_inventory(tmp_path)
    assert {"dependency_source_directive", "prohibited_source_directive"} <= _codes(report)
    encoded = inventory.canonical_json_bytes(report)
    assert private_url.encode("utf-8") not in encoded
    assert b"password" not in encoded


def test_duplicate_and_conflicting_exact_pins_are_detected(tmp_path: Path):
    _write(tmp_path / "requirements.txt", "demo==1.0\n-r requirements-dev.txt\n")
    _write(tmp_path / "requirements-dev.txt", "Demo==2.0\n")
    report = inventory.build_inventory(tmp_path)
    assert report["summary"]["duplicate_group_count"] == 1  # type: ignore[index]
    assert report["summary"]["conflict_group_count"] == 1  # type: ignore[index]
    assert report["conflicts"][0]["kind"] == "incompatible_exact_pins"  # type: ignore[index]
    assert set(report["declared_files"]) == {"requirements.txt", "requirements-dev.txt"}


def test_non_identical_duplicate_constraints_are_reported_conservatively(tmp_path: Path):
    _write(tmp_path / "requirements.txt", "demo>=1,<3\nDemo>=2,<3\n")
    report = inventory.build_inventory(tmp_path)
    assert report["conflicts"][0]["kind"] == "non_identical_constraints"  # type: ignore[index]
    assert report["conflict_detection_scope"].startswith("EXACT_PINS")


def test_pyproject_dependencies_are_inspected_when_declared(tmp_path: Path):
    _write(
        tmp_path / "pyproject.toml",
        "[project]\n"
        'name = "synthetic"\n'
        'dependencies = ["alpha>=1,<2"]\n\n'
        "[project.optional-dependencies]\n"
        'test = ["pytest==8.0.0"]\n',
    )
    report = inventory.build_inventory(tmp_path)
    assert {item["canonical_name"] for item in report["requirements"]} == {  # type: ignore[index]
        "alpha",
        "pytest",
    }
    assert report["declared_files"] == ["pyproject.toml"]


def test_output_is_canonical_deterministic_and_content_free(tmp_path: Path):
    _write(tmp_path / "requirements.txt", "beta>=2,<3\nalpha==1\n")
    first = inventory.build_inventory(tmp_path)
    second = inventory.build_inventory(tmp_path)
    first_bytes = inventory.canonical_json_bytes(first)
    assert first == second
    assert first_bytes == inventory.canonical_json_bytes(json.loads(first_bytes))
    assert first_bytes.endswith(b"\n")
    assert b"D:\\" not in first_bytes
    assert first["content_free"] is True
    assert first["vulnerability_status"] == "NOT_CHECKED"
    markdown = inventory.render_markdown(first)
    assert "does not claim that dependencies are vulnerability-free" in markdown


def test_unsafe_include_fails_closed_without_exposing_target(tmp_path: Path):
    sentinel = "PRIVATE_REQUIREMENTS_SENTINEL"
    _write(tmp_path / "requirements.txt", f"-r ../{sentinel}.txt\n")
    report = inventory.build_inventory(tmp_path)
    assert "unsafe_dependency_include" in _codes(report)
    assert sentinel.encode("ascii") not in inventory.canonical_json_bytes(report)