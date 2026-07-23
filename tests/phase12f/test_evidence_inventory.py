from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scripts.phase12f import common
from scripts.phase12f.build_evidence_inventory import (
    build_inventory,
    write_inventory,
)
from scripts.phase12f.common import (
    EvidenceToolError,
    canonical_json_bytes,
    load_allowlist,
    write_incomplete_marker,
)
from tests.phase12f.conftest import CANDIDATE, rule, write_json


def _status(path: Path) -> None:
    write_json(
        path,
        {
            "schema_version": 1,
            "candidate_sha": CANDIDATE,
            "state": "COMPLETE",
        },
    )


def test_successful_inventory_is_canonical_and_does_not_parse_result(
    tmp_path: Path,
    make_allowlist,
):
    evidence = tmp_path / "evidence"
    _status(evidence / "STATUS.json")
    (evidence / "notes.md").write_text("aggregate evidence\n", encoding="utf-8")
    (evidence / "result.json").write_bytes(b"{not-json")
    allowlist = make_allowlist(
        [
            rule(
                "closure_status",
                "STATUS.json",
                metadata_profile="closure_status",
            ),
            rule("notes", "notes.md"),
            rule("opaque_result", "result.json"),
            rule(
                "optional_table",
                "table.csv",
                artifact_class="optional",
            ),
            rule(
                "credential",
                "secret.pem",
                artifact_class="prohibited",
            ),
        ]
    )
    output = tmp_path / "inventory-output"
    source_before = {
        path.relative_to(evidence).as_posix(): path.read_bytes()
        for path in evidence.rglob("*")
        if path.is_file()
    }

    inventory = write_inventory(
        allowlist,
        {"evidence": evidence},
        output,
    )

    raw = (output / "evidence-inventory.json").read_bytes()
    assert raw == canonical_json_bytes(json.loads(raw))
    assert inventory["artifact_count"] == 3
    assert inventory["absent_optional_artifacts"] == ["optional_table"]
    assert inventory["prohibited_artifacts_verified_absent"] == ["credential"]
    assert all("source_path" not in item for item in inventory["artifacts"])
    assert str(evidence) not in raw.decode("utf-8")
    result = next(item for item in inventory["artifacts"] if item["logical_id"] == "opaque_result")
    assert result["safe_metadata"] == {}
    assert source_before == {
        path.relative_to(evidence).as_posix(): path.read_bytes()
        for path in evidence.rglob("*")
        if path.is_file()
    }


def test_unexpected_file_is_rejected(tmp_path: Path, make_allowlist):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "allowed.txt").write_text("ok", encoding="utf-8")
    (evidence / "extra.txt").write_text("unexpected", encoding="utf-8")
    allowlist = make_allowlist([rule("allowed", "allowed.txt")])

    with pytest.raises(EvidenceToolError, match="unexpected_artifact"):
        build_inventory(allowlist, {"evidence": evidence})


def test_duplicate_logical_artifact_is_rejected(make_allowlist):
    allowlist = make_allowlist(
        [
            rule("duplicate", "one.txt"),
            rule("duplicate", "two.txt"),
        ]
    )
    with pytest.raises(EvidenceToolError, match="duplicate_logical_artifact"):
        load_allowlist(allowlist)


def test_duplicate_physical_artifact_is_rejected(tmp_path: Path, make_allowlist):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    first = evidence / "first.txt"
    second = evidence / "second.txt"
    first.write_text("same inode", encoding="utf-8")
    os.link(first, second)
    allowlist = make_allowlist(
        [
            rule("first", "first.txt"),
            rule("second", "second.txt"),
        ]
    )
    with pytest.raises(EvidenceToolError, match="duplicate_logical_artifact"):
        build_inventory(allowlist, {"evidence": evidence})


def test_path_traversal_rule_is_rejected(make_allowlist):
    allowlist = make_allowlist([rule("escape", "../outside.txt")])
    with pytest.raises(EvidenceToolError, match="path_escape"):
        load_allowlist(allowlist)


def test_symlink_input_is_rejected(
    tmp_path: Path,
    make_allowlist,
    monkeypatch: pytest.MonkeyPatch,
):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    target = tmp_path / "target.txt"
    target.write_text("target", encoding="utf-8")
    link = evidence / "link.txt"
    try:
        link.symlink_to(target)
    except OSError:
        link.write_text("simulated link", encoding="utf-8")
        original = common._is_link_or_reparse
        monkeypatch.setattr(
            common,
            "_is_link_or_reparse",
            lambda path: path == link or original(path),
        )
    allowlist = make_allowlist([rule("linked", "link.txt")])

    with pytest.raises(EvidenceToolError, match="symlink_input"):
        build_inventory(allowlist, {"evidence": evidence})


def test_nonempty_output_is_refused(tmp_path: Path, make_allowlist):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "one.txt").write_text("one", encoding="utf-8")
    allowlist = make_allowlist([rule("one", "one.txt")])
    output = tmp_path / "output"
    output.mkdir()
    (output / "foreign.txt").write_text("do not overwrite", encoding="utf-8")

    with pytest.raises(EvidenceToolError, match="output_reuse"):
        write_inventory(allowlist, {"evidence": evidence}, output)
    assert (output / "foreign.txt").read_text(encoding="utf-8") == "do not overwrite"


def test_recognized_incomplete_inventory_state_can_be_replaced(
    tmp_path: Path,
    make_allowlist,
):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "one.txt").write_text("one", encoding="utf-8")
    allowlist = make_allowlist([rule("one", "one.txt")])
    output = tmp_path / "output"
    write_incomplete_marker(output, "phase12f_evidence_inventory")

    write_inventory(allowlist, {"evidence": evidence}, output)

    assert sorted(path.name for path in output.iterdir()) == [
        "evidence-inventory.json",
        "evidence-inventory.md",
    ]
