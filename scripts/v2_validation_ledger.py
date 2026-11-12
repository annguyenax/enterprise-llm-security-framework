"""Append-only Shield validation claims; no benchmark or provider I/O.

The coordinator provisions ONE empty ledger file and retains it across W2/W3
and checkouts. A mkdir lock serializes cooperating processes on Windows/Linux.
A crash may leave a lock or incomplete line: both fail closed, never auto-repair.
This is an operational cap, not protection against the ledger owner's rollback.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping


MAX_VALIDATION_ATTEMPTS = 3
IDENTITY_KEYS = frozenset({
    "campaign_run_id", "execution_branch", "execution_commit", "benchmark_manifest_sha256",
    "provider_behavior_hash", "runtime_settings_sha256", "freeze_sha256", "config_hashes",
    "output_root_sha256", "benchmark_root_sha256", "case_timeout_seconds", "started_at_utc",
    "validation_ledger_path_sha256",
})
RECORD_KEYS = IDENTITY_KEYS | {
    "schema_version", "system", "split", "benchmark_mode", "provider_id", "status",
    "attempt", "max_attempts", "previous_sha256", "record_sha256",
}


class ValidationLedgerError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def checked_path(path: Path) -> Path:
    path = path.absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or getattr(part, "is_junction", lambda: False)():
            raise ValidationLedgerError("ledger references must not traverse links")
    if not path.is_file():
        raise ValidationLedgerError("coordinator must provision an existing regular ledger file")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValidationLedgerError("ledger must be a regular file with one link")
    return path


def read_claims(path: Path) -> tuple[dict[str, Any], ...]:
    path = checked_path(path)
    raw = path.read_bytes()
    records, previous, campaigns = [], "0" * 64, set()
    for index, line in enumerate(raw.splitlines(keepends=True), 1):
        try:
            record = json.loads(line)
            if not isinstance(record, dict) or set(record) != RECORD_KEYS or canonical(record) != line:
                raise ValueError("noncanonical record")
            body = {key: value for key, value in record.items() if key != "record_sha256"}
            digest = hashlib.sha256(canonical(body)).hexdigest()
            if (record["record_sha256"] != digest or record["previous_sha256"] != previous
                    or type(record["attempt"]) is not int or record["attempt"] != index
                    or index > MAX_VALIDATION_ATTEMPTS or record["system"] != "shield"
                    or record["benchmark_mode"] != "dev-val" or record["split"] != "validation"
                    or record["provider_id"] != "ollama" or record["status"] != "claimed"
                    or record["schema_version"] != 1 or record["max_attempts"] != MAX_VALIDATION_ATTEMPTS
                    or not isinstance(record["campaign_run_id"], str)
                    or record["campaign_run_id"] in campaigns):
                raise ValueError("invalid claim chain")
        except (ValueError, TypeError, KeyError) as exc:
            raise ValidationLedgerError("ledger is malformed; manual reconciliation required") from exc
        campaigns.add(record["campaign_run_id"])
        records.append(record)
        previous = digest
    return tuple(records)


def claim_validation_slot(path: Path, identity: Mapping[str, Any]) -> dict[str, Any]:
    if set(identity) != IDENTITY_KEYS:
        raise ValidationLedgerError("validation claim identity is incomplete")
    path = checked_path(path)
    lock = path.with_name(path.name + ".lock")
    try:
        lock.mkdir()
    except OSError as exc:
        raise ValidationLedgerError("ledger is locked; no automatic retry or lock removal") from exc
    try:
        claims = read_claims(path)
        if len(claims) >= MAX_VALIDATION_ATTEMPTS:
            raise ValidationLedgerError("Shield validation cap reached (3/3); fourth attempt prohibited")
        if any(item["campaign_run_id"] == identity["campaign_run_id"] for item in claims):
            raise ValidationLedgerError("campaign already claimed; failed attempts cannot be reused")
        record = {
            **identity, "schema_version": 1, "system": "shield", "split": "validation",
            "benchmark_mode": "dev-val", "provider_id": "ollama", "status": "claimed",
            "attempt": len(claims) + 1, "max_attempts": MAX_VALIDATION_ATTEMPTS,
            "previous_sha256": claims[-1]["record_sha256"] if claims else "0" * 64,
        }
        record["record_sha256"] = hashlib.sha256(canonical(record)).hexdigest()
        payload = canonical(record)
        before = path.stat()
        # Windows CRT text descriptors translate LF even in os.write(bytes).
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | getattr(os, "O_BINARY", 0)
                     | getattr(os, "O_NOFOLLOW", 0))
        try:
            opened = os.fstat(fd)
            if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_nlink) != (
                    before.st_dev, before.st_ino, before.st_size, 1):
                raise ValidationLedgerError("ledger identity changed before append")
            if os.write(fd, payload) != len(payload):
                raise ValidationLedgerError("incomplete claim append; ledger requires reconciliation")
            os.fsync(fd)
        finally:
            os.close(fd)
        return record
    finally:
        lock.rmdir()


def self_check_canonical_io() -> None:
    """Exercise production claim I/O in a disposable ledger, never a campaign.

    No ledger path is accepted. A synthetic claim in a new temporary directory
    cannot consume a campaign's cap. Any byte/read failure propagates; neither
    this check nor the production writer repairs an existing ledger.
    """
    with tempfile.TemporaryDirectory(prefix="shield-ledger-self-check-") as directory:
        path = Path(directory) / "synthetic-ledger.jsonl"
        with path.open("xb"):
            pass
        digest = hashlib.sha256(b"synthetic-ledger-self-check").hexdigest()
        identity = {
            "campaign_run_id": "SYNTHETIC-LEDGER-SELF-CHECK",
            "execution_branch": "synthetic-self-check-kiểm-tra",
            "execution_commit": "0" * 40,
            "benchmark_manifest_sha256": digest,
            "provider_behavior_hash": digest,
            "runtime_settings_sha256": digest,
            "freeze_sha256": digest,
            "config_hashes": {"synthetic": digest},
            "output_root_sha256": digest,
            "benchmark_root_sha256": digest,
            "validation_ledger_path_sha256": digest,
            "case_timeout_seconds": 1.0,
            "started_at_utc": "2000-01-01T00:00:00Z",
        }
        record = claim_validation_slot(path, identity)
        raw = path.read_bytes()
        if raw != canonical(record) or b"\r" in raw:
            raise ValidationLedgerError("self-check ledger bytes differ from canonical LF")
        if read_claims(path) != (record,):
            raise ValidationLedgerError("self-check ledger read-back differs from the claim")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check disposable validation ledger byte I/O")
    parser.add_argument("--self-check", action="store_true", required=True,
                        help="write/read a synthetic temporary ledger; consumes no campaign attempt")
    parser.parse_args(argv)
    try:
        self_check_canonical_io()
    except (OSError, ValidationLedgerError) as exc:
        print(f"FAIL [validation_ledger_self_check]: {exc}", file=sys.stderr)
        return 1
    print("PASS [validation_ledger_self_check]: canonical UTF-8 LF bytes and read_claims verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
