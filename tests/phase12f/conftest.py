from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest


CANDIDATE = "93ad09ddea90eb9712e82f3df5beacbd94399b9a"
AUTHORIZATION_ID = "11111111-2222-4333-8444-555555555555"
PASS_GATE = "CODEX_PHASE12E4_CLOSURE_AUDIT_PASS"
FAIL_GATE = "CODEX_PHASE12E4_CLOSURE_AUDIT_FAIL"


def write_json(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def rule(
    logical_id: str,
    path: str,
    *,
    root: str = "evidence",
    artifact_class: str = "required",
    metadata_profile: str = "none",
    packet_class: str | None = None,
) -> dict[str, Any]:
    return {
        "logical_id": logical_id,
        "root": root,
        "path": path,
        "class": artifact_class,
        "metadata_profile": metadata_profile,
        "packet_class": packet_class,
    }


@pytest.fixture
def candidate() -> str:
    return CANDIDATE


@pytest.fixture
def make_allowlist(tmp_path: Path) -> Callable[[list[dict[str, Any]], str], Path]:
    def factory(
        artifacts: list[dict[str, Any]],
        name: str = "allowlist.json",
    ) -> Path:
        return write_json(
            tmp_path / name,
            {
                "schema_version": 1,
                "candidate_sha": CANDIDATE,
                "artifacts": artifacts,
            },
        )

    return factory


@pytest.fixture
def make_closure(tmp_path: Path) -> Callable[..., Path]:
    def factory(
        *,
        state: str = "COMPLETE",
        gate: str = PASS_GATE,
        name: str = "closure",
    ) -> Path:
        directory = tmp_path / name
        write_json(
            directory / "STATUS.json",
            {
                "schema_version": 1,
                "candidate_sha": CANDIDATE,
                "state": state,
            },
        )
        write_json(
            directory / "CLOSURE_FINDINGS.json",
            {
                "schema_version": 1,
                "candidate_sha": CANDIDATE,
                "closure_gate": gate,
                "critical": [],
                "major": [],
                "minor": [],
                "advisory": [],
                "not_verifiable": [],
            },
        )
        (directory / "FINAL_CLOSURE_AUDIT.md").write_text(
            "# Synthetic Closure\n\n"
            "## Closure Gate\n\n"
            f"{gate}\n",
            encoding="utf-8",
            newline="\n",
        )
        return directory

    return factory
