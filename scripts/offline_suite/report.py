"""Future-run reporting for the offline availability suite.

Manifest selects all 11 logic IDs (5 P + 6 A). The report records
selected/executed/skip/xfail per ID and distinguishes the logic-test
count (always 11) from the parameterized invocation count (often > 11).

No pytest import here: the launcher feeds this module parsed results, and
REQUIRED_BRANCHES declarations are read with `ast` (never imported).
A01 and A06 files also declare harness regression branches (launcher.main
blocker, report complete/exit-code, junit error handling). Those branches
are harness checks, not A06 product health-limit behaviour.
"""

from __future__ import annotations

import ast
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

LABEL = "mock/in-sample"

MANIFEST_11 = (
    "P01_metadata_missing",
    "P02_effective_differs",
    "P03_invalid_identity",
    "P04_execution_acl",
    "P05_history_latency",
    "A01_dependencies",
    "A02_network_guard",
    "A03_retrieval_timeout",
    "A04_provider_timeout",
    "A05_acl_fault",
    "A06_health_limits",
)

SPEC_PATH = "docs/specs/PLAN-v5-002-003.md"

# test-file stem (without test_ prefix handling) -> logic ID directory.
LOGIC_TEST_DIRS = ("tests/provenance_v1", "tests/offline_suite")


def logic_id_of(node_name: str) -> str | None:
    """Map a pytest node name to its logic ID by exact-ID substring."""
    for logic_id in MANIFEST_11:
        if logic_id in node_name:
            return logic_id
    return None



def invocation_name(node: str) -> str:
    """Pytest function name from a junit node, without parametrize brackets."""
    name = node.rsplit("::", 1)[-1]
    return name.split("[", 1)[0]


def invocation_covers(node: str, branch: str, *, exact_function: bool) -> bool:
    """Declared branch tags may be substrings of a node id.

    Function-derived branches must match the exact function name so that a
    passed test_x_extra never covers an unrun test_x.
    """
    if exact_function:
        return invocation_name(node) == branch
    return branch in node


def spec_sha256(repo_root: str | Path) -> str | None:
    path = Path(repo_root) / SPEC_PATH
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def read_required_branches(test_file: Path) -> tuple[list[str], list[str]]:
    """Parse REQUIRED_BRANCHES + test function names via ast (no import).

    Returns (declared_branches, test_function_names). Files without the
    declaration yield ([], names); that is recorded, not inferred.
    """
    try:
        tree = ast.parse(test_file.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return [], []
    branches: list[str] = []
    functions: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "REQUIRED_BRANCHES" in targets:
                try:
                    value = ast.literal_eval(node.value)
                except (ValueError, SyntaxError):
                    value = []
                if isinstance(value, list):
                    branches = [b for b in value if isinstance(b, str)]
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                functions.append(node.name)
    return branches, functions


def collect_branch_declarations(repo_root: str | Path) -> dict:
    """Map logic ID -> {declared branches, test file, test functions}."""
    root = Path(repo_root)
    declarations: dict[str, dict] = {}
    for dirname in LOGIC_TEST_DIRS:
        for test_file in sorted((root / dirname).glob("test_*.py")):
            branches, functions = read_required_branches(test_file)
            logic_id = logic_id_of(test_file.name)
            if logic_id is None:
                continue
            declarations[logic_id] = {
                "file": f"{dirname}/{test_file.name}",
                "declared_branches": branches,
                "test_functions": functions,
            }
    return declarations


def parse_junit(xml_path: str | Path) -> list[dict]:
    """Parse pytest --junitxml into invocation records (stdlib only)."""
    tree = ET.parse(xml_path)
    invocations: list[dict] = []
    for case in tree.getroot().iter("testcase"):
        classname = case.get("classname", "")
        name = case.get("name", "")
        node = f"{classname}::{name}"
        outcome = "passed"
        message = ""
        for child in case:
            if child.tag == "skipped":
                message = child.get("message", "")
                blob = f"{child.get('type', '')} {message}".lower()
                outcome = "xfailed" if "xfail" in blob else "skipped"
            elif child.tag == "failure":
                outcome = "failed" if outcome == "passed" else outcome
                message = (child.get("message", "") or "")[:500]
            elif child.tag == "error":
                # Setup/collection errors are not executed test bodies.
                outcome = "error"
                message = (child.get("message", "") or "")[:500]
        invocations.append({"node": node, "outcome": outcome, "message": message,
                            "logic_id": logic_id_of(node)})
    return invocations


def build_report(*, repo_root: str | Path, preflight: dict,
                 collection_started: bool, collection_detail: str = "",
                 invocations: list[dict] | None = None,
                 pytest_exit_code: int | None = None) -> dict:
    """Build the suite report. `selected` is always the manifest list.

    executed counts ONLY IDs whose test body actually ran (>=1 non-skipped
    invocation). Skip/xfail is never a pass: an ID with a skipped/xfailed
    required branch has not completed that ID's acceptance.
    """
    invocations = invocations or []
    declarations = collect_branch_declarations(repo_root)
    by_id: dict[str, dict] = {}
    for logic_id in MANIFEST_11:
        own = [i for i in invocations if i["logic_id"] == logic_id]
        ran = [i for i in own if i["outcome"] in ("passed", "failed")]
        passed = [i for i in own if i["outcome"] == "passed"]
        failed = [i for i in own if i["outcome"] == "failed"]
        skipped = [i for i in own if i["outcome"] == "skipped"]
        xfailed = [i for i in own if i["outcome"] == "xfailed"]
        errors = [i for i in own if i["outcome"] == "error"]
        declared = declarations.get(logic_id, {}).get("declared_branches", [])
        functions = declarations.get(logic_id, {}).get("test_functions", [])
        # If a file declares no REQUIRED_BRANCHES, each test function is a required branch.
        required = declared or functions
        exact_function = not bool(declared)
        branch_map: dict[str, dict] = {}
        for branch in required:
            hits = [i["node"] for i in passed
                    if invocation_covers(i["node"], branch, exact_function=exact_function)]
            branch_map[branch] = {"passed_invocations": hits,
                                  "covered": bool(hits)}
        missing = [b for b in required if not branch_map[b]["covered"]]
        by_id[logic_id] = {
            "selected": True,
            "executed": bool(ran),
            "invocation_count": len(own),
            "passed": len(passed),
            "failed": len(failed),
            "errors": len(errors),
            "skipped": len(skipped),
            "xfailed": len(xfailed),
            "invocations": [i["node"] for i in own],
            "declared_branches": declared,
            "branches": branch_map,
            "missing_branches": missing,
        }
    executed = [i for i in MANIFEST_11 if by_id[i]["executed"]]
    counts = {
        "logic_selected": len(MANIFEST_11),
        "logic_executed": len(executed),
        "invocations_total": len(invocations),
        "invocations_passed": sum(1 for i in invocations if i["outcome"] == "passed"),
        "invocations_failed": sum(1 for i in invocations if i["outcome"] == "failed"),
        "invocations_errors": sum(1 for i in invocations if i["outcome"] == "error"),
        "invocations_skipped": sum(1 for i in invocations if i["outcome"] == "skipped"),
        "invocations_xfailed": sum(1 for i in invocations if i["outcome"] == "xfailed"),
    }
    unmapped = [i["node"] for i in invocations if i["logic_id"] is None]
    if not collection_started:
        verdict, reason = "blocked", (
            f"runner never started ({collection_detail}); executed=0; "
            f"executed=11 is NOT required for this run")
    elif counts["logic_executed"] != 11:
        verdict, reason = "incomplete", (
            f"executed {counts['logic_executed']}/11 logic IDs; complete run "
            f"requires all 11")
    elif pytest_exit_code not in (0, None) or (collection_started and pytest_exit_code is None):
        verdict, reason = "incomplete", (
            f"pytest_exit_code={pytest_exit_code} is required to be 0 for a complete run")
    elif counts["invocations_failed"] or counts["invocations_errors"]:
        verdict, reason = "incomplete", (
            f"{counts['invocations_failed']} failed, {counts['invocations_errors']} "
            f"setup/collection error(s); errors are not executed bodies")
    elif counts["invocations_skipped"] or counts["invocations_xfailed"]:
        verdict, reason = "incomplete", (
            "skip/xfail present; skip/xfail is not a pass and the affected "
            "ID has not completed acceptance")
    elif any(by_id[i]["missing_branches"] for i in MANIFEST_11):
        missing_ids = [i for i in MANIFEST_11 if by_id[i]["missing_branches"]]
        verdict, reason = "incomplete", (
            f"required branches uncovered for {missing_ids}")
    elif unmapped:
        verdict, reason = "incomplete", (
            f"{len(unmapped)} invocation(s) map to no logic ID")
    else:
        verdict, reason = "complete", (
            "all 11 logic IDs executed; every declared required branch has "
            "a passed invocation; no failure, skip, or xfail")
    return {
        "suite": "offline-availability",
        "label": LABEL,
        "result_kind": "mock/in-sample (test doubles only; no real providers)",
        "spec": {"path": SPEC_PATH, "sha256": spec_sha256(repo_root)},
        "manifest": list(MANIFEST_11),
        "preflight": preflight,
        "collection": {"started": collection_started,
                       "detail": collection_detail,
                       "pytest_exit_code": pytest_exit_code},
        "selected": list(MANIFEST_11),
        "executed": executed,
        "counts": counts,
        "by_id": by_id,
        "verdict": verdict,
        "verdict_reason": reason,
    }
