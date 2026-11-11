"""Real preflight for the offline availability suite (outside the 11 tests).

This module must start WITHOUT importing pytest (or any other probed
dependency) as a hard load-time dependency. Every dependency check goes
through an importlib probe at runtime, so a missing pytest is reported as
BLOCKED_DEPS instead of crashing the launcher import.

Outcomes are mock/in-sample environment readiness only. Preflight says
nothing about real provider availability, and syntax success is recorded
on a separate dimension that never changes the dependency verdict.

No new general health enum or health API lives here: statuses are the
frozen strings READY / BLOCKED_DEPS / BLOCKED_ISOLATION / BLOCKED_PROBES.
"""

from __future__ import annotations

import argparse
import importlib
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

READY = "READY"
BLOCKED_DEPS = "BLOCKED_DEPS"
BLOCKED_ISOLATION = "BLOCKED_ISOLATION"
BLOCKED_PROBES = "BLOCKED_PROBES"

# Frozen probe set: pytest + fastapi + the A02 probe transports.
PROBE_MODULES = ("pytest", "fastapi", "httpx", "aiohttp")

# Test roots that must exist before the suite may dispatch.
REQUIRED_TEST_DIRS = ("tests/offline_suite", "tests/provenance_v1")

LABEL = "mock/in-sample"


@dataclass(frozen=True)
class ProbeOutcome:
    module: str
    ok: bool
    error: str | None = None


@dataclass(frozen=True)
class PreflightDecision:
    status: str
    exit_code: int
    dispatch: bool
    reasons: tuple[str, ...] = ()
    probes: tuple[ProbeOutcome, ...] = ()
    isolation: dict | None = None
    missing_paths: tuple[str, ...] = ()
    # Recorded only; never influences the dependency/isolation verdict.
    syntax_ok: bool | None = None
    label: str = LABEL

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "exit_code": self.exit_code,
            "dispatch": self.dispatch,
            "reasons": list(self.reasons),
            "probes": [
                {"module": p.module, "ok": p.ok, "error": p.error}
                for p in self.probes
            ],
            "isolation": self.isolation,
            "missing_paths": list(self.missing_paths),
            "syntax_ok": self.syntax_ok,
            "label": self.label,
        }


def probe_import(module: str, simulate: dict | None = None) -> ProbeOutcome:
    """Probe one module via importlib. `simulate` maps module -> None (ok)
    or an Exception/str (failure) and is used ONLY by A01 test doubles so
    the running interpreter is never disturbed."""
    if simulate is not None and module in simulate:
        fake = simulate[module]
        if fake is None:
            return ProbeOutcome(module, True, None)
        if isinstance(fake, Exception):
            return ProbeOutcome(module, False, f"{type(fake).__name__}: {fake}")
        return ProbeOutcome(module, False, str(fake))
    try:
        importlib.import_module(module)
    except Exception as exc:  # Missing OR broken import both block.
        return ProbeOutcome(module, False, f"{type(exc).__name__}: {exc}")
    return ProbeOutcome(module, True, None)


def probe_imports(simulate: dict | None = None) -> tuple[ProbeOutcome, ...]:
    return tuple(probe_import(name, simulate) for name in PROBE_MODULES)


def check_isolation() -> dict:
    """Real OS-isolation mechanism check: user-namespace netns via unshare.

    Returns a dict with ok/detail; never downloads anything and never
    touches the network. A02's OS-layer probe depends on this mechanism.
    """
    exe = shutil.which("unshare")
    if exe is None:
        return {"ok": False, "mechanism": "unshare -r -n",
                "detail": "'unshare' not found on PATH; OS-layer netns unavailable"}
    try:
        proc = subprocess.run([exe, "-r", "-n", "true"],
                              capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return {"ok": False, "mechanism": "unshare -r -n",
                "detail": "'unshare -r -n true' timed out after 30s"}
    except OSError as exc:
        return {"ok": False, "mechanism": "unshare -r -n",
                "detail": f"could not execute unshare: {exc}"}
    if proc.returncode != 0:
        return {"ok": False, "mechanism": "unshare -r -n",
                "detail": f"'unshare -r -n true' exited {proc.returncode}: "
                         f"{(proc.stderr or '').strip()[-300:]}"}
    return {"ok": True, "mechanism": "unshare -r -n",
            "detail": "'unshare -r -n true' succeeded without sudo"}


def check_required_paths(repo_root: str | Path) -> tuple[str, ...]:
    root = Path(repo_root)
    return tuple(d for d in REQUIRED_TEST_DIRS if not (root / d).is_dir())


def decide(probes: tuple[ProbeOutcome, ...],
           isolation: dict,
           missing_paths: tuple[str, ...],
           syntax_ok: bool | None = None) -> PreflightDecision:
    """Pure verdict function shared by the real CLI and A01 doubles.

    `syntax_ok` is recorded for the syntax/readiness separation branch but
    NEVER changes the verdict: syntax speaks only about syntax.
    """
    failed = [p for p in probes if not p.ok]
    reasons: list[str] = []
    if failed:
        for p in failed:
            reasons.append(f"dependency '{p.module}' unavailable: {p.error}")
        return PreflightDecision(BLOCKED_DEPS, 2, False, tuple(reasons),
                                 probes, isolation, missing_paths, syntax_ok)
    if not isolation.get("ok", False):
        reasons.append(f"isolation unavailable: {isolation.get('detail', 'unknown')}")
        return PreflightDecision(BLOCKED_ISOLATION, 3, False, tuple(reasons),
                                 probes, isolation, missing_paths, syntax_ok)
    if missing_paths:
        for path in missing_paths:
            reasons.append(f"required probe path missing: {path}")
        return PreflightDecision(BLOCKED_PROBES, 4, False, tuple(reasons),
                                 probes, isolation, missing_paths, syntax_ok)
    return PreflightDecision(READY, 0, True, (), probes, isolation,
                             missing_paths, syntax_ok)


def run_preflight(repo_root: str | Path = ".",
                  simulate_imports: dict | None = None,
                  isolation: dict | None = None,
                  missing_paths: tuple[str, ...] | None = None,
                  syntax_ok: bool | None = None) -> PreflightDecision:
    """Real preflight. Override parameters exist ONLY for A01 doubles;
    the CLI always calls this with real checks (all None except repo_root)."""
    probes = probe_imports(simulate_imports)
    real_isolation = check_isolation() if isolation is None else isolation
    real_missing = check_required_paths(repo_root) if missing_paths is None else missing_paths
    return decide(probes, real_isolation, real_missing, syntax_ok)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline-suite real preflight (outside the 11 logic tests).")
    parser.add_argument("--repo-root", default=".",
                        help="Repository root for required-path checks.")
    parser.add_argument("--json-out", default=None,
                        help="Optional path to write the decision JSON.")
    args = parser.parse_args(argv)
    decision = run_preflight(args.repo_root)
    payload = json.dumps(decision.to_dict(), indent=2)
    print(payload)
    if args.json_out:
        Path(args.json_out).write_text(payload + "\n", encoding="utf-8")
    if decision.status != READY:
        print(f"preflight {decision.status}: suite will NOT start "
              f"({'; '.join(decision.reasons)})", file=sys.stderr)
    return decision.exit_code


if __name__ == "__main__":
    sys.exit(main())
