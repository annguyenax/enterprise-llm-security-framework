"""Phase 12G bootstrap tests: static safety + behavioral (junction cleanup)."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = ROOT / "scripts" / "release" / "bootstrap_fresh_checkout.ps1"
_POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
pytestmark = pytest.mark.skipif(_POWERSHELL is None, reason="PowerShell not available")


def _run(args):
    return subprocess.run([_POWERSHELL, "-NoProfile", "-NonInteractive",
                           "-ExecutionPolicy", "Bypass", "-File", str(BOOTSTRAP), *args],
                          capture_output=True, text=True, timeout=120)


def _last_json(stdout: str):
    # The script emits exactly one JSON object as its summary.
    text = stdout.strip()
    start = text.index("{")
    return json.loads(text[start:])


# --------------------------------------------------------------------------- #
# Static safety properties
# --------------------------------------------------------------------------- #
def test_bootstrap_no_manual_copy_and_uses_materializer():
    src = BOOTSTRAP.read_text(encoding="utf-8")
    assert "Copy-Item" not in src
    assert "materialize_v2_frozen_artifacts.py" in src
    assert "--include-redteam-prompts" in src


def test_bootstrap_no_evaluation_workflow_invocation():
    src = BOOTSTRAP.read_text(encoding="utf-8")
    assert "run_v2_evaluation.py" not in src
    assert "analyze_v2_results.py" not in src
    # Release readiness is the only verify invocation, and it is flag-gated.
    assert "-ReleaseReadiness" in src


def test_bootstrap_cleans_junction_in_finally():
    src = BOOTSTRAP.read_text(encoding="utf-8")
    assert "finally" in src
    assert "Remove-Item" in src and ".venv" in src


# --------------------------------------------------------------------------- #
# Behavioral: commit mismatch, clean-tree, junction cleanup
# --------------------------------------------------------------------------- #
def _init_repo(path: Path):
    path.mkdir(parents=True)
    def g(*a):
        subprocess.run(["git", "-C", str(path),
                        "-c", "user.email=t@t.invalid", "-c", "user.name=t",
                        "-c", "commit.gpgsign=false", *a], check=True,
                       capture_output=True, text=True)
    g("init", "-q")
    (path / "f.txt").write_text("x\n", encoding="utf-8")
    g("add", "-A"); g("commit", "-q", "-m", "init")
    head = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    return head


def test_bootstrap_refuses_commit_mismatch(tmp_path):
    target = tmp_path / "target"
    _init_repo(target)
    res = _run(["-SourceRepo", str(tmp_path), "-TargetCheckout", str(target),
                "-ExpectedCommit", "0" * 40])
    summary = _last_json(res.stdout)
    assert summary["commit_verified"] is False
    assert summary["ok"] is False
    assert summary["manual_copy_used"] is False


def test_bootstrap_junction_created_then_removed(tmp_path):
    target = tmp_path / "target"
    head = _init_repo(target)
    venv_src = tmp_path / "venvsrc"
    venv_src.mkdir()
    # No materializer script in this synthetic target -> materializer step fails,
    # but the temporary junction must still be created and then removed.
    res = _run(["-SourceRepo", str(tmp_path), "-TargetCheckout", str(target),
                "-ExpectedCommit", head, "-CreateVenvJunction",
                "-VenvSource", str(venv_src)])
    summary = _last_json(res.stdout)
    assert summary["commit_verified"] is True
    assert summary["tree_clean"] is True
    assert summary["junction_created"] is True
    assert summary["junction_removed"] is True
    assert not (target / ".venv").exists()
