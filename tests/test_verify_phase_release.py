"""Phase 12F tests for the release-readiness mode of scripts/verify_phase.ps1.

These tests invoke PowerShell to exercise the script's observable behavior:
basetemp selection/report, symlink-capability tri-state, and path-length
failure classification. They never run holdout, analyzer, validation or
development, and they use only synthetic inputs.

If PowerShell is unavailable (non-Windows CI), the whole module is skipped.
"""
from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VERIFY_PS1 = ROOT / "scripts" / "verify_phase.ps1"

_POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
pytestmark = pytest.mark.skipif(
    _POWERSHELL is None, reason="PowerShell not available on this host"
)


def _run_ps(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=120,
    )


def _dot_source_helpers() -> str:
    """Dot-source only the helper functions from verify_phase.ps1.

    The script's top-level body needs a venv and repo; to unit-test the pure
    helpers we extract and evaluate just their definitions.
    """
    text = VERIFY_PS1.read_text(encoding="utf-8")
    # Pull each helper function definition by brace matching from its header.
    wanted = ["Test-PathLengthFailure", "Test-SymlinkCapability", "Test-AuxiliaryFixture"]
    blocks = []
    for name in wanted:
        marker = f"function {name}("
        start = text.index(marker)
        depth = 0
        i = text.index("{", start)
        body_start = start
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(text[body_start:i + 1])
                    break
            i += 1
    return "\n".join(blocks)


def test_helpers_are_extractable():
    helpers = _dot_source_helpers()
    assert "function Test-PathLengthFailure" in helpers
    assert "function Test-SymlinkCapability" in helpers


@pytest.mark.parametrize("sample,expected", [
    ("Error: [WinError 3] The system cannot find the path specified", "True"),
    ("OSError: [WinError 206] The filename or extension is too long", "True"),
    ("some MAX_PATH note", "True"),
    ("AssertionError: expected 5 got 4", "False"),
    ("2 failed, 3 passed", "False"),
    ("", "False"),
])
def test_path_length_classification(sample, expected):
    helpers = _dot_source_helpers()
    escaped = sample.replace("'", "''")
    script = helpers + f"\n$r = Test-PathLengthFailure '{escaped}'\nWrite-Output $r\n"
    result = _run_ps(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected, result.stdout


def test_symlink_capability_returns_known_state(tmp_path):
    helpers = _dot_source_helpers()
    root = str(tmp_path).replace("'", "''")
    script = helpers + textwrap.dedent(f"""
        $r = Test-SymlinkCapability '{root}'
        Write-Output $r.State
    """)
    result = _run_ps(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() in {"PASS", "SKIP-CAPABILITY", "FAIL"}


def test_release_mode_reports_basetemp_and_does_not_run_holdout(tmp_path):
    """Full-script release run: must report basetemp and explicitly not run
    holdout/analyzer. Runs against the real worktree (byte-level checks only)."""
    if not (ROOT / ".venv" / "Scripts" / "python.exe").exists():
        pytest.skip("worktree has no .venv; full release run is exercised in integration")
    bt = tmp_path / "bt"
    script = (
        f"& '{VERIFY_PS1}' -ReleaseReadiness -BaseTemp '{bt}'"
    )
    result = _run_ps(script)
    combined = result.stdout + result.stderr
    # Regardless of pass/fail on frozen artifacts (a fresh worktree may lack the
    # ignored jsonl), the mode must report the selected basetemp and its
    # non-actions.
    assert "basetemp_selected" in combined
    assert str(bt) in combined
    assert "holdout: not run" in combined
    assert "analyzer: not run" in combined
    # It must never invoke the runner or analyzer scripts.
    assert "run_v2_evaluation.py" not in combined
    assert "analyze_v2_results.py" not in combined
    # The auxiliary release-fixture check must be present.
    assert "release_auxiliary_artifacts_bytelevel" in combined


# ===========================================================================
# Phase 12F remediation — auxiliary release-fixture byte-level check
# ===========================================================================
import hashlib  # noqa: E402
import json as _json  # noqa: E402

_AUX_BLOB = b'{"synthetic_redteam": "p1"}\n{"synthetic_redteam": "p2"}\n'


def _make_aux(base, *, status="final", path="redteam/prompts.jsonl",
              write_fixture=True, corrupt=False, extra=False):
    """Build a synthetic base dir with a redteam manifest (+ optional fixture)."""
    (base / "redteam").mkdir(parents=True, exist_ok=True)
    entry = {"path": path, "sha256": hashlib.sha256(_AUX_BLOB).hexdigest(),
             "size_bytes": len(_AUX_BLOB)}
    files = [entry]
    if extra:
        files.append({"path": "redteam/extra.jsonl",
                      "sha256": hashlib.sha256(b"x").hexdigest(), "size_bytes": 1})
    manifest = {"schema_version": 1, "manifest_status": status,
                "artifact_class": "release_test_fixture", "files": files}
    mpath = base / "redteam" / "prompts-manifest.json"
    mpath.write_text(_json.dumps(manifest), encoding="utf-8")
    if write_fixture:
        data = bytearray(_AUX_BLOB)
        if corrupt:
            data[0] ^= 0xFF
        (base / "redteam" / "prompts.jsonl").write_bytes(bytes(data))
    return mpath


def _run_aux(base, mpath):
    helpers = _dot_source_helpers()
    b = str(base).replace("'", "''")
    m = str(mpath).replace("'", "''")
    script = helpers + textwrap.dedent(f"""
        $r = Test-AuxiliaryFixture '{m}' '{b}'
        if ($r.Ok) {{ Write-Output "PASS" }} else {{ Write-Output "FAIL" }}
        Write-Output $r.Detail
    """)
    return _run_ps(script)


def test_aux_fixture_pass(tmp_path):
    mpath = _make_aux(tmp_path)
    result = _run_aux(tmp_path, mpath)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0].strip() == "PASS"


def test_aux_fixture_missing_file_fails(tmp_path):
    mpath = _make_aux(tmp_path, write_fixture=False)
    result = _run_aux(tmp_path, mpath)
    assert result.stdout.splitlines()[0].strip() == "FAIL"
    assert "MISSING" in result.stdout


def test_aux_fixture_hash_mismatch_fails(tmp_path):
    mpath = _make_aux(tmp_path, corrupt=True)
    result = _run_aux(tmp_path, mpath)
    assert result.stdout.splitlines()[0].strip() == "FAIL"
    assert "HASH MISMATCH" in result.stdout


def test_aux_fixture_non_final_fails(tmp_path):
    mpath = _make_aux(tmp_path, status="candidate")
    result = _run_aux(tmp_path, mpath)
    assert result.stdout.splitlines()[0].strip() == "FAIL"


def test_aux_fixture_extra_entry_fails(tmp_path):
    mpath = _make_aux(tmp_path, extra=True)
    result = _run_aux(tmp_path, mpath)
    assert result.stdout.splitlines()[0].strip() == "FAIL"


def test_aux_fixture_wrong_path_fails(tmp_path):
    mpath = _make_aux(tmp_path, path="redteam/other.jsonl")
    result = _run_aux(tmp_path, mpath)
    assert result.stdout.splitlines()[0].strip() == "FAIL"


def test_aux_fixture_missing_manifest_fails(tmp_path):
    result = _run_aux(tmp_path, tmp_path / "redteam" / "prompts-manifest.json")
    assert result.stdout.splitlines()[0].strip() == "FAIL"
    assert "not found" in result.stdout
