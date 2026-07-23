from __future__ import annotations

from pathlib import Path

from scripts.phase12f.build_evidence_inventory import write_inventory
from scripts.phase12f.verify_evidence_inventory import main, verify_inventory
from tests.phase12f.conftest import AUTHORIZATION_ID, CANDIDATE, rule, write_json


def _create_verifiable_inventory(tmp_path: Path, make_allowlist):
    evidence = tmp_path / "evidence"
    write_json(
        evidence / "authorization.json",
        {
            "execution_commit": CANDIDATE,
            "authorization_id": AUTHORIZATION_ID,
            "attempt": 1,
            "provider_id": "mock",
            "benchmark_manifest_sha256": "a" * 64,
            "holdout_authorized": True,
        },
    )
    write_json(
        evidence / "receipt.json",
        {
            "execution_commit": CANDIDATE,
            "authorization_id": AUTHORIZATION_ID,
            "attempt": 1,
            "provider_id": "mock",
            "status": "claimed",
        },
    )
    (evidence / "aggregate.md").write_text("safe aggregate\n", encoding="utf-8")
    allowlist = make_allowlist(
        [
            rule(
                "authorization",
                "authorization.json",
                metadata_profile="authorization",
            ),
            rule(
                "receipt",
                "receipt.json",
                metadata_profile="receipt",
            ),
            rule("aggregate", "aggregate.md"),
        ]
    )
    output = tmp_path / "inventory"
    write_inventory(allowlist, {"evidence": evidence}, output)
    return evidence, output / "evidence-inventory.json"


def test_verifier_passes_unchanged_evidence(tmp_path: Path, make_allowlist):
    evidence, inventory = _create_verifiable_inventory(tmp_path, make_allowlist)

    report = verify_inventory(inventory, {"evidence": evidence})

    assert report["status"] == "PASS"
    assert report["passed"] is True
    assert report["findings"] == []
    assert report["not_verifiable"] == []
    assert report["checked_artifact_count"] == 3


def test_verifier_detects_altered_evidence(tmp_path: Path, make_allowlist):
    evidence, inventory = _create_verifiable_inventory(tmp_path, make_allowlist)
    (evidence / "aggregate.md").write_text("changed aggregate\n", encoding="utf-8")

    report = verify_inventory(inventory, {"evidence": evidence})

    assert report["status"] == "FAIL"
    assert report["passed"] is False
    assert any(item["category"] == "changed_artifact" for item in report["findings"])


def test_verifier_detects_missing_file(tmp_path: Path, make_allowlist):
    evidence, inventory = _create_verifiable_inventory(tmp_path, make_allowlist)
    (evidence / "receipt.json").unlink()

    report = verify_inventory(inventory, {"evidence": evidence})

    assert report["status"] == "FAIL"
    assert any(item["category"] == "missing_artifact" for item in report["findings"])


def test_verifier_detects_unexpected_file(tmp_path: Path, make_allowlist):
    evidence, inventory = _create_verifiable_inventory(tmp_path, make_allowlist)
    (evidence / "added.txt").write_text("added later", encoding="utf-8")

    report = verify_inventory(inventory, {"evidence": evidence})

    assert report["status"] == "FAIL"
    assert any(item["category"] == "added_artifact" for item in report["findings"])


def test_not_verifiable_is_never_pass(tmp_path: Path, make_allowlist):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "opaque.bin").write_bytes(b"opaque")
    allowlist = make_allowlist([rule("opaque", "opaque.bin")])
    output = tmp_path / "inventory"
    write_inventory(allowlist, {"evidence": evidence}, output)

    report = verify_inventory(
        output / "evidence-inventory.json",
        {"evidence": evidence},
    )

    assert report["status"] == "NOT_VERIFIABLE"
    assert report["passed"] is False
    assert report["findings"] == []
    assert report["not_verifiable"]


def test_verifier_detects_inventory_record_duplication(
    tmp_path: Path,
    make_allowlist,
):
    evidence, inventory_path = _create_verifiable_inventory(tmp_path, make_allowlist)
    import json

    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory["artifacts"].append(dict(inventory["artifacts"][0]))
    inventory["artifact_count"] += 1
    inventory_path.write_text(
        json.dumps(inventory, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    report = verify_inventory(inventory_path, {"evidence": evidence})

    assert report["status"] == "FAIL"
    assert any(
        item["category"] == "duplicate_logical_artifact"
        for item in report["findings"]
    )


def test_verifier_refuses_to_write_findings_inside_evidence_root(
    tmp_path: Path,
    make_allowlist,
):
    evidence, inventory = _create_verifiable_inventory(tmp_path, make_allowlist)
    output = evidence / "verification.json"

    result = main(
        [
            "--inventory",
            str(inventory),
            "--root",
            f"evidence={evidence}",
            "--output",
            str(output),
        ]
    )

    assert result == 1
    assert not output.exists()
