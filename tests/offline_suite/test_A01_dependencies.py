"""A01: dependency readiness via simulated preflight doubles (mock/in-sample).

After a ready real environment, A01 simulates preflight import results --
including pytest and fastapi failures -- WITHOUT making the running pytest
disappear. Error -> BLOCKED_DEPS, nonzero exit, no suite dispatch.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_PATH = REPO_ROOT / "scripts" / "offline_suite" / "preflight.py"

REQUIRED_BRANCHES = [
    "pytest_failure",
    "fastapi_failure",
    "httpx_failure",
    "aiohttp_failure",
    "all_ready",
    "syntax_isolated",
    "no_dispatch",
    "isolation_missing",
    "probes_missing",
    "pytest_missing_stops_suite",
    "no_pytest_import",
    "launcher_main_blocker",
]

OK_ISOLATION = {"ok": True, "mechanism": "in-sample double",
                "detail": "simulated ready isolation"}


def load_preflight():
    spec = importlib.util.spec_from_file_location(
        "offline_suite_preflight_doubles", PREFLIGHT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass string annotations need this.
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("module", ["pytest", "fastapi", "httpx", "aiohttp"],
                         ids=["pytest_failure", "fastapi_failure",
                              "httpx_failure", "aiohttp_failure"])
def test_A01_dependencies_simulated_dep_failure_blocks(module):
    preflight = load_preflight()
    decision = preflight.run_preflight(
        REPO_ROOT, simulate_imports={module: ImportError(f"No module named '{module}'")},
        isolation=dict(OK_ISOLATION), missing_paths=())
    assert decision.status == preflight.BLOCKED_DEPS
    assert decision.exit_code != 0
    assert decision.dispatch is False
    assert any(module in reason for reason in decision.reasons)
    # The running pytest is untouched by the simulation.
    assert "pytest" in sys.modules


def test_A01_dependencies_all_ready_dispatches_in_sample():
    preflight = load_preflight()
    decision = preflight.run_preflight(
        REPO_ROOT, simulate_imports={m: None for m in preflight.PROBE_MODULES},
        isolation=dict(OK_ISOLATION), missing_paths=())
    assert decision.status == preflight.READY
    assert decision.exit_code == 0
    assert decision.dispatch is True
    assert all(p.ok for p in decision.probes)


def test_A01_dependencies_syntax_isolated_from_verdict():
    preflight = load_preflight()
    # Syntax success never rescues a dependency failure.
    blocked = preflight.run_preflight(
        REPO_ROOT, simulate_imports={"pytest": ImportError("No module named 'pytest'")},
        isolation=dict(OK_ISOLATION), missing_paths=(), syntax_ok=True)
    assert blocked.status == preflight.BLOCKED_DEPS
    assert blocked.syntax_ok is True
    # A syntax flag on its own dimension never blocks ready dependencies.
    ready = preflight.run_preflight(
        REPO_ROOT, simulate_imports={m: None for m in preflight.PROBE_MODULES},
        isolation=dict(OK_ISOLATION), missing_paths=(), syntax_ok=False)
    assert ready.status == preflight.READY
    assert ready.syntax_ok is False


@pytest.mark.parametrize("kind", ["dep", "isolation", "probes"],
                         ids=["no_dispatch_dep", "no_dispatch_isolation",
                              "no_dispatch_probes"])
def test_A01_dependencies_no_dispatch_when_blocked(kind):
    preflight = load_preflight()
    if kind == "dep":
        decision = preflight.run_preflight(
            REPO_ROOT, simulate_imports={"fastapi": ImportError("No module named 'fastapi'")},
            isolation=dict(OK_ISOLATION), missing_paths=())
    elif kind == "isolation":
        decision = preflight.run_preflight(
            REPO_ROOT, simulate_imports={m: None for m in preflight.PROBE_MODULES},
            isolation={"ok": False, "mechanism": "in-sample double",
                       "detail": "simulated missing netns"},
            missing_paths=())
    else:
        decision = preflight.run_preflight(
            REPO_ROOT, simulate_imports={m: None for m in preflight.PROBE_MODULES},
            isolation=dict(OK_ISOLATION),
            missing_paths=("tests/offline_suite",))
    assert decision.dispatch is False
    assert decision.exit_code != 0


def test_A01_dependencies_isolation_missing_blocks_with_reason():
    preflight = load_preflight()
    decision = preflight.run_preflight(
        REPO_ROOT, simulate_imports={m: None for m in preflight.PROBE_MODULES},
        isolation={"ok": False, "mechanism": "unshare -r -n",
                   "detail": "simulated: 'unshare' not found"},
        missing_paths=())
    assert decision.status == preflight.BLOCKED_ISOLATION
    assert decision.exit_code != 0
    assert decision.dispatch is False
    assert any("unshare" in r for r in decision.reasons)


def test_A01_dependencies_probes_missing_blocks_with_reason():
    preflight = load_preflight()
    decision = preflight.run_preflight(
        REPO_ROOT, simulate_imports={m: None for m in preflight.PROBE_MODULES},
        isolation=dict(OK_ISOLATION),
        missing_paths=("tests/offline_suite",))
    assert decision.status == preflight.BLOCKED_PROBES
    assert decision.exit_code != 0
    assert decision.dispatch is False
    assert any("tests/offline_suite" in r for r in decision.reasons)


def test_A01_dependencies_pytest_missing_stops_suite_not_a01_success():
    """Real preflight with pytest import-blocked: starts, then BLOCKED_DEPS.

    This subprocess proves the launcher starts without pytest and stops
    before the suite; a blocked preflight is NOT a successful A01 run, so
    the test asserts dispatch is False and exit is nonzero.
    """
    code = (
        "import json, sys\n"
        "import importlib.abc\n"
        "class PytestBlocker(importlib.abc.MetaPathFinder):\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name == 'pytest' or name.startswith('pytest.'):\n"
        "            raise ImportError('A01 simulated missing pytest (in-sample double)')\n"
        "        return None\n"
        "sys.meta_path.insert(0, PytestBlocker())\n"
        "sys.path.insert(0, 'scripts/offline_suite')\n"
        "import preflight\n"
        "try:\n"
        "    import pytest\n"
        "except ImportError:\n"
        "    pass\n"
        "else:\n"
        "    print('PYTEST_LEAK'); sys.exit(99)\n"
        "decision = preflight.run_preflight('.')\n"
        "print(json.dumps(decision.to_dict()))\n"
        "sys.exit(decision.exit_code)\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT,
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode != 0, f"blocked preflight must exit nonzero: {proc.stdout[-500:]}"
    assert "PYTEST_LEAK" not in (proc.stdout + proc.stderr)
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["status"] == "BLOCKED_DEPS"
    assert payload["dispatch"] is False
    assert any("pytest" in r for r in payload["reasons"])


@pytest.mark.parametrize("script", ["preflight.py", "launcher.py", "report.py"],
                         ids=["no_pytest_import_preflight",
                              "no_pytest_import_launcher",
                              "no_pytest_import_report"])
def test_A01_dependencies_no_pytest_import_at_load(script):
    """Launcher/scripts must not import pytest at module load time."""
    tree = ast.parse((REPO_ROOT / "scripts" / "offline_suite" / script)
                     .read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Import):
            assert all((a.name or "").split(".")[0] != "pytest"
                       for a in node.names), f"{script} imports pytest at load"
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] != "pytest", (
                f"{script} imports pytest at load")


def test_A01_dependencies_launcher_main_blocker_never_starts_pytest(tmp_path):
    """launcher.main with a preflight blocker exits nonzero, executed=0,
    and run_pytest is never started."""
    scripts = REPO_ROOT / "scripts" / "offline_suite"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import launcher
    import preflight as preflight_mod

    blocked = preflight_mod.PreflightDecision(
        status=preflight_mod.BLOCKED_DEPS, exit_code=2, dispatch=False,
        reasons=("pytest missing (in-sample blocker)",),
    )
    started = {"pytest": False}

    def boom(*_args, **_kwargs):
        started["pytest"] = True
        raise AssertionError("run_pytest must not start after a blocker")

    report_path = tmp_path / "blocked.json"
    with mock.patch.object(launcher.preflight, "run_preflight", return_value=blocked):
        with mock.patch.object(launcher, "run_pytest", side_effect=boom):
            rc = launcher.main(["--repo-root", str(REPO_ROOT),
                                "--report", str(report_path)])
    assert rc != 0
    assert started["pytest"] is False
    assert report_path.is_file()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["verdict"] == "blocked"
    assert payload["executed"] == []
    assert payload["counts"]["logic_executed"] == 0
