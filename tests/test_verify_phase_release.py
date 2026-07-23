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
    wanted = ["Test-PathLengthFailure", "Test-SymlinkCapability"]
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
