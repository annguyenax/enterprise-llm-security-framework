"""Synthetic Windows newline regression tests; no benchmark/provider I/O."""
from __future__ import annotations

import builtins
import hashlib
import io
import json
import os
from pathlib import Path

import pytest

from scripts import analyze_v2_results as analyzer
from scripts import run_v2_evaluation as runner
from scripts import v2_validation_ledger as ledger
# Reuse W14's synthetic fixtures and its protected-I/O/network guards unchanged.
from test_w14_dev_val_execution import lab, protected_io, real_request


@pytest.fixture
def windows_newlines(monkeypatch, protected_io):
    """Model CRT text descriptors and default text newlines on every host.

    Underlying descriptors are binary on native Windows too, so the simulator
    translates exactly once. O_BINARY's synthetic POSIX bit is stripped before
    the host syscall. io.open/Path.open binary modes keep their real behavior.
    """
    native_binary = getattr(os, "O_BINARY", 0)
    binary_flag = native_binary or (1 << 29)
    monkeypatch.setattr(os, "O_BINARY", binary_flag, raising=False)
    original_open, original_write, original_close = os.open, os.write, os.close
    text_fds = set()

    def opened(path, flags, *args, **kwargs):
        fd = original_open(path, (flags & ~binary_flag) | native_binary, *args, **kwargs)
        if flags & (os.O_WRONLY | os.O_RDWR) and not flags & binary_flag:
            text_fds.add(fd)
        return fd

    def written(fd, payload):
        disk_bytes = payload.replace(b"\n", b"\r\n") if fd in text_fds else payload
        if original_write(fd, disk_bytes) != len(disk_bytes):
            raise OSError("short write in Windows newline simulator")
        # CRT reports input bytes accepted, not the translated on-disk size.
        return len(payload)

    def closed(fd):
        text_fds.discard(fd)
        return original_close(fd)

    def text_open(original):
        def opened(file, mode="r", buffering=-1, encoding=None, errors=None,
                   newline=None, closefd=True, opener=None):
            if "b" not in mode and any(flag in mode for flag in "wax+") and newline is None:
                newline = "\r\n"
            return original(file, mode, buffering=buffering, encoding=encoding,
                            errors=errors, newline=newline, closefd=closefd, opener=opener)
        return opened

    monkeypatch.setattr(os, "open", opened)
    monkeypatch.setattr(os, "write", written)
    monkeypatch.setattr(os, "close", closed)
    for owner in (builtins, io):
        monkeypatch.setattr(owner, "open", text_open(owner.open))


@pytest.fixture
def synthetic_identity():
    return {
        "campaign_run_id": "SYNTHETIC-W15-01", "execution_branch": "synthetic-kiểm-tra",
        "execution_commit": "a" * 40, "benchmark_manifest_sha256": "b" * 64,
        "provider_behavior_hash": "c" * 64, "runtime_settings_sha256": "d" * 64,
        "freeze_sha256": "e" * 64, "config_hashes": {"C0_all_on": "f" * 64},
        "output_root_sha256": "1" * 64, "benchmark_root_sha256": "2" * 64,
        "case_timeout_seconds": 1.0, "started_at_utc": "2000-01-01T00:00:00Z",
        "validation_ledger_path_sha256": "3" * 64,
    }


def _append_like_796ae25(path, record):
    """The old append stage, including the missing O_BINARY flag."""
    payload = ledger.canonical(record)
    before = path.stat()
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_nlink) != (
                before.st_dev, before.st_ino, before.st_size, 1):
            raise ledger.ValidationLedgerError("ledger identity changed before append")
        if os.write(fd, payload) != len(payload):
            raise ledger.ValidationLedgerError("incomplete claim append; ledger requires reconciliation")
        os.fsync(fd)
    finally:
        os.close(fd)


def test_796ae25_append_reproduces_crlf_and_strict_reader_failure(
        tmp_path, windows_newlines, synthetic_identity):
    path = tmp_path / "synthetic-old-ledger.jsonl"
    path.touch()
    record = {
        **synthetic_identity, "schema_version": 1, "system": "shield", "split": "validation",
        "benchmark_mode": "dev-val", "provider_id": "ollama", "status": "claimed",
        "attempt": 1, "max_attempts": 3, "previous_sha256": "0" * 64,
    }
    record["record_sha256"] = hashlib.sha256(ledger.canonical(record)).hexdigest()
    _append_like_796ae25(path, record)
    raw = path.read_bytes()
    assert raw == ledger.canonical(record).replace(b"\n", b"\r\n")
    with pytest.raises(ledger.ValidationLedgerError, match="malformed"):
        ledger.read_claims(path)
    # The fixed writer must refuse the old evidence, never normalize/repair it.
    with pytest.raises(ledger.ValidationLedgerError, match="malformed"):
        ledger.claim_validation_slot(path, {**synthetic_identity, "campaign_run_id": "SYNTHETIC-W15-02"})
    assert path.read_bytes() == raw


def test_binary_claims_are_exact_canonical_bytes_under_same_windows_patch(
        tmp_path, windows_newlines, synthetic_identity):
    path = tmp_path / "synthetic-new-ledger.jsonl"
    path.touch()
    records = tuple(ledger.claim_validation_slot(path, {
        **synthetic_identity, "campaign_run_id": f"SYNTHETIC-W15-{index}",
    }) for index in range(1, 4))
    raw = path.read_bytes()
    assert raw == b"".join(ledger.canonical(record) for record in records)
    assert b"\r" not in raw and raw.count(b"\n") == 3
    assert ledger.read_claims(path) == records
    with pytest.raises(ledger.ValidationLedgerError, match="fourth attempt prohibited"):
        ledger.claim_validation_slot(path, {**synthetic_identity, "campaign_run_id": "SYNTHETIC-W15-4"})
    assert path.read_bytes() == raw


def _assert_canonical_json(path):
    raw = path.read_bytes()
    value = json.loads(raw)
    assert raw == ledger.canonical(value)
    assert b"\r" not in raw and raw.endswith(b"\n")
    return value


def test_dev_val_receipt_results_and_analysis_keep_canonical_bytes(
        lab, monkeypatch, windows_newlines):
    """Actual claim/receipt verifiers and publishers; invented worker outcomes."""
    request = real_request(lab, monkeypatch)

    class WorkerDouble:
        def __init__(self, **kwargs):
            assert "dev_val_evidence" in kwargs["init_payload"]

        def execute(self, task, timeout_seconds):
            outcome = runner.ScopeOutcome("allow", "allowed", True, 1, 1, 0, 0, {}, (), 1.0, 2.0)
            return {"kind": "outcome", "outcome": runner._scope_outcome_to_transport(outcome)}

        def close(self):
            pass

    monkeypatch.setattr(runner, "_SpawnCaseWorker", WorkerDouble)
    runs = runner.run_evaluation(request, benchmark_root=lab.data, hooks=lab.hooks)
    receipt_path = request.output_root / "dev-val-start-receipt.json"
    receipt = _assert_canonical_json(receipt_path)
    assert request.validation_ledger.read_bytes() == receipt_path.read_bytes()
    assert ledger.read_claims(request.validation_ledger) == (receipt,)
    capability = runner.verify_existing_dev_val_ollama_claim(
        request, repo_root=runner.ROOT, benchmark_root=lab.data, hooks=lab.hooks)
    assert capability.is_valid() and capability.attempt == 1
    assert len(runs) == 8
    for run in runs:
        _assert_canonical_json(run.result_path)
        manifest = _assert_canonical_json(run.manifest_path)
        assert manifest["result_sha256"] == hashlib.sha256(run.result_path.read_bytes()).hexdigest()
        assert manifest["result_size_bytes"] == run.result_path.stat().st_size
    _assert_canonical_json(lab.data / runner.DEV_VAL_MANIFEST_PATH)
    # The runner reads the approved freeze; it never creates or rewrites it.
    assert runner._sha256_file(request.frozen_config_path) == request.frozen_config_sha256

    analysis_request = analyzer.AnalysisRequest(
        "validation", lab.state.branch, lab.state.commit, lab.tmp / "analysis",
        tuple(run.manifest_path for run in runs), "dev-val", request.campaign_run_id,
        request.validation_ledger, request.frozen_config_path, request.frozen_config_sha256)
    written = analyzer.analyze_results(analysis_request, benchmark_root=lab.data,
        hooks=analyzer.AnalyzerHooks(repository_state_loader=lambda _: lab.state))
    _assert_canonical_json(written.analysis_path)
    analysis_manifest = _assert_canonical_json(written.manifest_path)
    table = written.table_path.read_bytes()
    assert b"\r" not in table and table.endswith(b"\n")
    assert analysis_manifest["table_sha256"] == hashlib.sha256(table).hexdigest()
    assert analysis_manifest["table_size_bytes"] == len(table)
    assert ledger.read_claims(request.validation_ledger) == (receipt,)


def test_ollama_evidence_binary_append_and_runtime_publish(tmp_path, windows_newlines):
    sink = runner._ollama_event_sink(tmp_path)
    metadata = {"synthetic_note": "kiểm tra", "attempt_trace": []}
    events = [{"request_id": "synthetic-request", "event": event}
              for event in ("attempt_start", "attempt_end")]
    for event in events:
        sink(event, metadata)
    expected = [{**event, "request_metadata": {"synthetic_note": "kiểm tra"}} for event in events]
    raw = (tmp_path / "ollama-attempts.jsonl").read_bytes()
    assert raw == b"".join(ledger.canonical(record) for record in expected)
    assert b"\r" not in raw
    runner._write_ollama_runtime(tmp_path, {"expected": {"repeat_count": 1}})
    runtime = _assert_canonical_json(tmp_path / "ollama-runtime.json")
    assert len(runtime["requests"]["synthetic-request"]["attempt_trace"]) == 2


@pytest.mark.parametrize("break_binary", [False, True])
def test_supported_self_check_is_temporary_and_detects_crlf(
        tmp_path, monkeypatch, capsys, windows_newlines, break_binary):
    monkeypatch.setattr(ledger.tempfile, "tempdir", str(tmp_path))
    production_claim = ledger.claim_validation_slot
    paths = []

    def checked_claim(path, identity):
        assert path.parent.parent == tmp_path
        assert path.is_file() and path.read_bytes() == b""
        paths.append(path)
        return production_claim(path, identity)

    monkeypatch.setattr(ledger, "claim_validation_slot", checked_claim)
    if break_binary:
        # Keep the same simulator but make the writer omit its binary flag.
        monkeypatch.setattr(os, "O_BINARY", 0)
    assert ledger.main(["--self-check"]) == (1 if break_binary else 0)
    captured = capsys.readouterr()
    if break_binary:
        assert "FAIL [validation_ledger_self_check]" in captured.err
        assert "canonical LF" in captured.err
    else:
        assert "PASS [validation_ledger_self_check]" in captured.out
    assert len(paths) == 1 and not paths[0].parent.exists()


def test_windows_patch_also_translates_default_text_writers(tmp_path, windows_newlines):
    path = tmp_path / "synthetic-text-canary.json"
    path.write_text('{"synthetic":true}\n', encoding="utf-8")
    assert path.read_bytes() == b'{"synthetic":true}\r\n'
