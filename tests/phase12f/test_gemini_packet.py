from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from scripts.phase12f.common import EvidenceToolError
from scripts.phase12f.prepare_gemini_packet import (
    CHECKSUMS_FILENAME,
    MANIFEST_FILENAME,
    SIZES_FILENAME,
    ZIP_FILENAME,
    prepare_packet,
)
from tests.phase12f.conftest import FAIL_GATE, rule, write_json


def _packet_source(tmp_path: Path) -> Path:
    source = tmp_path / "aggregates"
    write_json(
        source / "analysis.json",
        {
            "schema_version": 1,
            "split": "holdout",
            "summary": {"matched": 8, "total": 8},
        },
    )
    (source / "analysis.csv").write_text(
        "config_id,matched,total\nC0_all_on,8,8\n",
        encoding="utf-8",
        newline="\n",
    )
    (source / "summary.md").write_text(
        "# Aggregate Summary\n\nSynthetic aggregate only.\n",
        encoding="utf-8",
        newline="\n",
    )
    return source


def _packet_rules() -> list[dict]:
    return [
        rule(
            "analysis_json",
            "analysis.json",
            packet_class="aggregate_json",
        ),
        rule(
            "analysis_csv",
            "analysis.csv",
            packet_class="aggregate_csv",
        ),
        rule(
            "analysis_summary",
            "summary.md",
            packet_class="aggregate_markdown",
        ),
    ]


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def test_closure_running_is_refused(
    tmp_path: Path,
    make_allowlist,
    make_closure,
):
    source = _packet_source(tmp_path)
    closure = make_closure(state="RUNNING")
    allowlist = make_allowlist(_packet_rules())

    with pytest.raises(EvidenceToolError, match="closure_running"):
        prepare_packet(closure, allowlist, {"evidence": source}, tmp_path / "packet")


def test_closure_fail_is_refused(
    tmp_path: Path,
    make_allowlist,
    make_closure,
):
    source = _packet_source(tmp_path)
    closure = make_closure(state="COMPLETE", gate=FAIL_GATE)
    allowlist = make_allowlist(_packet_rules())

    with pytest.raises(EvidenceToolError, match="closure_failed"):
        prepare_packet(closure, allowlist, {"evidence": source}, tmp_path / "packet")


def test_missing_closure_report_is_refused(
    tmp_path: Path,
    make_allowlist,
    make_closure,
):
    source = _packet_source(tmp_path)
    closure = make_closure()
    (closure / "FINAL_CLOSURE_AUDIT.md").unlink()
    allowlist = make_allowlist(_packet_rules())

    with pytest.raises(EvidenceToolError, match="closure_missing"):
        prepare_packet(closure, allowlist, {"evidence": source}, tmp_path / "packet")


def test_ambiguous_closure_report_is_refused(
    tmp_path: Path,
    make_allowlist,
    make_closure,
):
    source = _packet_source(tmp_path)
    closure = make_closure()
    nested = closure / "duplicate"
    nested.mkdir()
    (nested / "FINAL_CLOSURE_AUDIT.md").write_text(
        "# Duplicate\n",
        encoding="utf-8",
    )
    allowlist = make_allowlist(_packet_rules())

    with pytest.raises(EvidenceToolError, match="closure_ambiguous"):
        prepare_packet(closure, allowlist, {"evidence": source}, tmp_path / "packet")


def test_closure_pass_builds_exact_sanitized_packet(
    tmp_path: Path,
    make_allowlist,
    make_closure,
):
    source = _packet_source(tmp_path)
    (source / "result.json").write_text('{"raw":"not copied"}', encoding="utf-8")
    (source / "holdout.jsonl").write_text('{"case":"not copied"}\n', encoding="utf-8")
    (source / ".env").write_text("TOKEN=not-copied\n", encoding="utf-8")
    (source / "retrieval.sqlite3").write_bytes(b"not copied")
    (source / "credentials.json").write_text('{"secret":"not copied"}', encoding="utf-8")
    git_dir = source / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\n", encoding="utf-8")
    closure = make_closure()
    allowlist = make_allowlist(_packet_rules())
    output = tmp_path / "packet"
    source_before = {
        path.relative_to(source).as_posix(): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file()
    }
    closure_before = {
        path.relative_to(closure).as_posix(): path.read_bytes()
        for path in closure.rglob("*")
        if path.is_file()
    }

    result = prepare_packet(closure, allowlist, {"evidence": source}, output)

    assert result["artifact_count"] == 3
    assert sorted(path.name for path in output.iterdir()) == sorted(
        [
            CHECKSUMS_FILENAME,
            SIZES_FILENAME,
            MANIFEST_FILENAME,
            ZIP_FILENAME,
        ]
    )
    with zipfile.ZipFile(output / ZIP_FILENAME) as archive:
        names = archive.namelist()
        assert names == sorted(
            [
                CHECKSUMS_FILENAME,
                SIZES_FILENAME,
                MANIFEST_FILENAME,
                "artifacts/analysis_csv/analysis.csv",
                "artifacts/analysis_json/analysis.json",
                "artifacts/analysis_summary/summary.md",
                "closure/CLOSURE_FINDINGS.json",
                "closure/FINAL_CLOSURE_AUDIT.md",
                "closure/STATUS.json",
            ]
        )
        assert not any(name.endswith("result.json") for name in names)
        assert not any(name.endswith(".jsonl") for name in names)
        manifest = json.loads(archive.read(MANIFEST_FILENAME))
    excluded = {
        item["class"]: item["count"]
        for item in manifest["excluded_artifact_classes"]
    }
    assert excluded == {
        "benchmark_jsonl": 1,
        "credential": 1,
        "database": 1,
        "environment_file": 1,
        "git_data": 1,
        "result_record": 1,
    }
    assert manifest["content_controls"]["result_json_included"] is False
    assert manifest["content_controls"]["jsonl_included"] is False
    assert source_before == {
        path.relative_to(source).as_posix(): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file()
    }
    assert closure_before == {
        path.relative_to(closure).as_posix(): path.read_bytes()
        for path in closure.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize(
    ("name", "packet_class", "expected_category"),
    [
        ("result.json", "aggregate_json", "result_record"),
        ("holdout.jsonl", "aggregate_json", "benchmark_jsonl"),
        ("credentials.json", "aggregate_json", "credential"),
    ],
)
def test_prohibited_class_cannot_be_explicitly_allowlisted(
    tmp_path: Path,
    make_allowlist,
    make_closure,
    name: str,
    packet_class: str,
    expected_category: str,
):
    source = tmp_path / "aggregates"
    source.mkdir()
    (source / name).write_text("{}\n", encoding="utf-8")
    closure = make_closure()
    allowlist = make_allowlist(
        [rule("unsafe", name, packet_class=packet_class)]
    )

    with pytest.raises(EvidenceToolError, match=expected_category):
        prepare_packet(closure, allowlist, {"evidence": source}, tmp_path / "packet")


def test_packet_creation_is_deterministic(
    tmp_path: Path,
    make_allowlist,
    make_closure,
):
    source = _packet_source(tmp_path)
    closure = make_closure()
    allowlist = make_allowlist(_packet_rules())
    first = tmp_path / "packet-one"
    second = tmp_path / "packet-two"

    one = prepare_packet(closure, allowlist, {"evidence": source}, first)
    two = prepare_packet(closure, allowlist, {"evidence": source}, second)

    assert one["zip_sha256"] == two["zip_sha256"]
    assert (first / ZIP_FILENAME).read_bytes() == (second / ZIP_FILENAME).read_bytes()
    assert (first / MANIFEST_FILENAME).read_bytes() == (second / MANIFEST_FILENAME).read_bytes()
    assert (first / CHECKSUMS_FILENAME).read_bytes() == (second / CHECKSUMS_FILENAME).read_bytes()


def test_packet_output_reuse_is_refused(
    tmp_path: Path,
    make_allowlist,
    make_closure,
):
    source = _packet_source(tmp_path)
    closure = make_closure()
    allowlist = make_allowlist(_packet_rules())
    output = tmp_path / "packet"
    prepare_packet(closure, allowlist, {"evidence": source}, output)
    original_zip = (output / ZIP_FILENAME).read_bytes()

    with pytest.raises(EvidenceToolError, match="output_reuse"):
        prepare_packet(closure, allowlist, {"evidence": source}, output)
    assert (output / ZIP_FILENAME).read_bytes() == original_zip


def test_standard_checksum_file_verifies_every_listed_entry(
    tmp_path: Path,
    make_allowlist,
    make_closure,
):
    source = _packet_source(tmp_path)
    closure = make_closure()
    allowlist = make_allowlist(_packet_rules())
    output = tmp_path / "packet"
    prepare_packet(closure, allowlist, {"evidence": source}, output)

    with zipfile.ZipFile(output / ZIP_FILENAME) as archive:
        checksum_text = archive.read(CHECKSUMS_FILENAME).decode("ascii")
        names = set(archive.namelist())
        for line in checksum_text.splitlines():
            digest, name = line.split("  ", 1)
            assert name in names
            assert digest == _sha(archive.read(name))
        assert CHECKSUMS_FILENAME not in {
            line.split("  ", 1)[1]
            for line in checksum_text.splitlines()
        }
    external_checksums = (output / CHECKSUMS_FILENAME).read_text(encoding="ascii")
    assert {
        line.split("  ", 1)[1]
        for line in external_checksums.splitlines()
    } == {MANIFEST_FILENAME, SIZES_FILENAME, ZIP_FILENAME}
    for line in external_checksums.splitlines():
        digest, name = line.split("  ", 1)
        assert digest == _sha((output / name).read_bytes())
