"""Phase 12F tests for scripts/materialize_v2_frozen_artifacts.py.

Every fixture is synthetic. No test reads, copies, parses or enumerates the real
frozen benchmark artifacts, and no test executes development, validation,
holdout or analysis.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mat():
    return _load_module("v2_materialize_mod", "materialize_v2_frozen_artifacts.py")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_manifest(bench_dir: Path, entries: list[dict], status: str = "final") -> Path:
    manifests = bench_dir / "manifests"
    manifests.mkdir(parents=True, exist_ok=True)
    manifest = {
        "benchmark_version": "v2",
        "file_count": len(entries),
        "files": entries,
        "manifest_status": status,
        "manifest_version": 1,
    }
    path = manifests / "benchmark-v2-manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return path


@pytest.fixture()
def synthetic_repos(tmp_path):
    """Build a synthetic source repo (with artifacts) and an empty target repo.

    Artifacts are tiny synthetic byte blobs, never real benchmark content.
    """
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    source_bench = source_root / "datasets" / "v2"
    target_bench = target_root / "datasets" / "v2"
    (source_bench / "cases").mkdir(parents=True)
    (source_bench / "labels").mkdir(parents=True)
    target_bench.mkdir(parents=True)

    blobs = {
        "cases/alpha.jsonl": b'{"synthetic": "alpha"}\n{"synthetic": "a2"}\n',
        "cases/beta.jsonl": b'{"synthetic": "beta"}\n',
        "labels/alpha.jsonl": b'{"label": 1}\n',
        "small.json": b"{}",
    }
    entries = []
    for rel, data in blobs.items():
        p = source_bench / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        entries.append({"path": rel, "sha256": _sha(data), "size_bytes": len(data)})

    # Manifest lives in the TARGET repo (it is the tracked authority).
    _write_manifest(target_bench, entries)
    return {
        "mod_source_root": source_root,
        "target_root": target_root,
        "source_bench": source_bench,
        "target_bench": target_bench,
        "entries": entries,
        "blobs": blobs,
    }


# --------------------------------------------------------------------------- #
# Successful atomic materialization
# --------------------------------------------------------------------------- #
def test_successful_materialization_copies_all_artifacts(mat, synthetic_repos):
    r = synthetic_repos
    summary = mat.materialize_frozen_artifacts(
        source_root=r["mod_source_root"], target_root=r["target_root"]
    )
    assert summary["ok"] is True
    assert summary["counts"]["materialized"] == 4
    assert summary["counts"]["reused"] == 0
    for rel, data in r["blobs"].items():
        target = r["target_bench"] / rel
        assert target.exists(), rel
        assert target.read_bytes() == data


def test_output_is_content_free(mat, synthetic_repos):
    """The summary must carry only identities/actions, never record bytes."""
    r = synthetic_repos
    summary = mat.materialize_frozen_artifacts(
        source_root=r["mod_source_root"], target_root=r["target_root"]
    )
    blob = json.dumps(summary)
    for data in r["blobs"].values():
        # No artifact payload substring should appear in the summary.
        text = data.decode("utf-8")
        for line in text.splitlines():
            if line.strip():
                assert line not in blob
    for f in summary["files"]:
        assert set(f).issubset(
            {"path", "action", "sha256", "size_bytes", "expected_sha256", "expected_size_bytes"}
        )


# --------------------------------------------------------------------------- #
# Dry run
# --------------------------------------------------------------------------- #
def test_dry_run_writes_nothing(mat, synthetic_repos):
    r = synthetic_repos
    summary = mat.materialize_frozen_artifacts(
        source_root=r["mod_source_root"], target_root=r["target_root"], dry_run=True
    )
    assert summary["dry_run"] is True
    assert summary["counts"]["would_materialize"] == 4
    assert summary["counts"]["materialized"] == 0
    for rel in r["blobs"]:
        assert not (r["target_bench"] / rel).exists(), rel


# --------------------------------------------------------------------------- #
# Matching target reuse
# --------------------------------------------------------------------------- #
def test_matching_existing_target_is_reused_not_rewritten(mat, synthetic_repos):
    r = synthetic_repos
    # Pre-place one byte-identical target and capture its mtime_ns.
    rel = "cases/alpha.jsonl"
    target = r["target_bench"] / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(r["blobs"][rel])
    before_stat = target.stat()

    summary = mat.materialize_frozen_artifacts(
        source_root=r["mod_source_root"], target_root=r["target_root"]
    )
    assert summary["counts"]["reused"] == 1
    assert summary["counts"]["materialized"] == 3
    after = next(f for f in summary["files"] if f["path"] == rel)
    assert after["action"] == "reused"
    # File was not rewritten.
    assert target.stat().st_mtime_ns == before_stat.st_mtime_ns


# --------------------------------------------------------------------------- #
# Target mismatch refusal (fail closed, no overwrite)
# --------------------------------------------------------------------------- #
def test_mismatching_existing_target_is_not_overwritten(mat, synthetic_repos):
    r = synthetic_repos
    rel = "cases/alpha.jsonl"
    target = r["target_bench"] / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    tampered = b'{"synthetic": "TAMPERED"}\n'
    target.write_bytes(tampered)

    with pytest.raises(mat.MaterializationError) as exc:
        mat.materialize_frozen_artifacts(
            source_root=r["mod_source_root"], target_root=r["target_root"]
        )
    assert exc.value.code == "target_mismatch"
    # The tampered target is preserved, never overwritten.
    assert target.read_bytes() == tampered


# --------------------------------------------------------------------------- #
# Source hash mismatch
# --------------------------------------------------------------------------- #
def test_source_hash_mismatch_fails_closed(mat, synthetic_repos):
    r = synthetic_repos
    # Corrupt a source artifact so its bytes no longer match the manifest hash,
    # keeping the same byte length so the size check passes and the hash check
    # is what fires.
    rel = "cases/alpha.jsonl"
    src = r["source_bench"] / rel
    original = src.read_bytes()
    corrupted = bytearray(original)
    corrupted[0] ^= 0xFF
    src.write_bytes(bytes(corrupted))

    with pytest.raises(mat.MaterializationError) as exc:
        mat.materialize_frozen_artifacts(
            source_root=r["mod_source_root"], target_root=r["target_root"]
        )
    assert exc.value.code == "source_hash_mismatch"
    assert not (r["target_bench"] / rel).exists()


def test_source_size_mismatch_fails_closed(mat, synthetic_repos):
    r = synthetic_repos
    rel = "cases/beta.jsonl"
    src = r["source_bench"] / rel
    src.write_bytes(src.read_bytes() + b"extra\n")
    with pytest.raises(mat.MaterializationError) as exc:
        mat.materialize_frozen_artifacts(
            source_root=r["mod_source_root"], target_root=r["target_root"]
        )
    assert exc.value.code == "source_size_mismatch"


# --------------------------------------------------------------------------- #
# Missing artifact
# --------------------------------------------------------------------------- #
def test_missing_source_artifact_fails_closed(mat, synthetic_repos):
    r = synthetic_repos
    (r["source_bench"] / "cases/alpha.jsonl").unlink()
    with pytest.raises(mat.MaterializationError) as exc:
        mat.materialize_frozen_artifacts(
            source_root=r["mod_source_root"], target_root=r["target_root"]
        )
    assert exc.value.code == "source_missing"


# --------------------------------------------------------------------------- #
# Exact manifest allowlist / extra-selected rejection
# --------------------------------------------------------------------------- #
def test_extra_selected_path_rejected(mat, synthetic_repos):
    r = synthetic_repos
    with pytest.raises(mat.MaterializationError) as exc:
        mat.materialize_frozen_artifacts(
            source_root=r["mod_source_root"],
            target_root=r["target_root"],
            only_paths=["cases/alpha.jsonl", "cases/not-in-manifest.jsonl"],
        )
    assert exc.value.code == "extra_selected"


def test_only_paths_subset_materializes_allowlisted_only(mat, synthetic_repos):
    r = synthetic_repos
    summary = mat.materialize_frozen_artifacts(
        source_root=r["mod_source_root"], target_root=r["target_root"],
        only_paths=["cases/alpha.jsonl"],
    )
    assert summary["counts"]["materialized"] == 1
    assert summary["counts"]["skipped_not_selected"] == 3
    assert (r["target_bench"] / "cases/alpha.jsonl").exists()
    assert not (r["target_bench"] / "cases/beta.jsonl").exists()


# --------------------------------------------------------------------------- #
# Path traversal / escape refusal
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", ["../escape.jsonl", "cases/../../escape.jsonl", "/abs/escape.jsonl"])
def test_manifest_path_traversal_rejected(mat, synthetic_repos, bad):
    r = synthetic_repos
    entries = list(r["entries"]) + [{"path": bad, "sha256": _sha(b"x"), "size_bytes": 1}]
    _write_manifest(r["target_bench"], entries)
    with pytest.raises(mat.MaterializationError) as exc:
        mat.materialize_frozen_artifacts(
            source_root=r["mod_source_root"], target_root=r["target_root"]
        )
    assert exc.value.code in {"path_traversal", "path_absolute", "path_shape"}


# --------------------------------------------------------------------------- #
# Symlink / reparse rejection (where testable)
# --------------------------------------------------------------------------- #
def test_symlinked_source_artifact_rejected(mat, synthetic_repos):
    r = synthetic_repos
    rel = "cases/alpha.jsonl"
    src = r["source_bench"] / rel
    real = r["source_bench"] / "cases" / "_real_alpha.bin"
    real.write_bytes(r["blobs"][rel])
    src.unlink()
    try:
        os.symlink(real, src)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted on this host")
    with pytest.raises(mat.MaterializationError) as exc:
        mat.materialize_frozen_artifacts(
            source_root=r["mod_source_root"], target_root=r["target_root"]
        )
    assert exc.value.code == "symlink_rejected"


# --------------------------------------------------------------------------- #
# Manifest status / structure guards
# --------------------------------------------------------------------------- #
def test_non_final_manifest_rejected(mat, synthetic_repos):
    r = synthetic_repos
    _write_manifest(r["target_bench"], r["entries"], status="candidate")
    with pytest.raises(mat.MaterializationError) as exc:
        mat.materialize_frozen_artifacts(
            source_root=r["mod_source_root"], target_root=r["target_root"]
        )
    assert exc.value.code == "manifest_not_final"


def test_duplicate_manifest_path_rejected(mat, synthetic_repos):
    r = synthetic_repos
    dup = r["entries"][0]
    _write_manifest(r["target_bench"], list(r["entries"]) + [dict(dup)])
    with pytest.raises(mat.MaterializationError) as exc:
        mat.materialize_frozen_artifacts(
            source_root=r["mod_source_root"], target_root=r["target_root"]
        )
    assert exc.value.code in {"manifest_duplicate", "manifest_count"}


def test_bool_size_rejected(mat, synthetic_repos):
    r = synthetic_repos
    entries = list(r["entries"])
    entries[0] = dict(entries[0], size_bytes=True)  # bool is a subclass of int
    _write_manifest(r["target_bench"], entries)
    with pytest.raises(mat.MaterializationError) as exc:
        mat.materialize_frozen_artifacts(
            source_root=r["mod_source_root"], target_root=r["target_root"]
        )
    assert exc.value.code == "manifest_size"


# --------------------------------------------------------------------------- #
# CLI surface + summary file
# --------------------------------------------------------------------------- #
def test_cli_main_writes_summary(mat, synthetic_repos, tmp_path):
    r = synthetic_repos
    out = tmp_path / "summary.json"
    rc = mat.main([
        "--source-root", str(r["mod_source_root"]),
        "--target-root", str(r["target_root"]),
        "--summary-out", str(out),
    ])
    assert rc == 0
    summary = json.loads(out.read_text(encoding="utf-8"))
    assert summary["ok"] is True
    assert summary["counts"]["materialized"] == 4


def test_cli_main_reports_error_code_on_failure(mat, synthetic_repos, tmp_path):
    r = synthetic_repos
    (r["source_bench"] / "cases/alpha.jsonl").unlink()
    out = tmp_path / "err.json"
    rc = mat.main([
        "--source-root", str(r["mod_source_root"]),
        "--target-root", str(r["target_root"]),
        "--summary-out", str(out),
    ])
    assert rc == 1
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert payload["error_code"] == "source_missing"


# ===========================================================================
# Phase 12F remediation — governed redteam auxiliary fixture group
# ===========================================================================
REDTEAM_BLOB = b'{"synthetic_redteam": "prompt-1"}\n{"synthetic_redteam": "prompt-2"}\n'


def _write_redteam_manifest(target_root, entries, status="final",
                            artifact_class="release_test_fixture"):
    d = target_root / "redteam"
    d.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "manifest_status": status,
        "artifact_class": artifact_class,
        "files": entries,
    }
    path = d / "prompts-manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return path


@pytest.fixture()
def redteam_repos(synthetic_repos):
    """Extend the synthetic repos with a governed redteam fixture + manifest."""
    r = synthetic_repos
    src_redteam = r["mod_source_root"] / "redteam"
    src_redteam.mkdir(parents=True, exist_ok=True)
    (src_redteam / "prompts.jsonl").write_bytes(REDTEAM_BLOB)
    entry = {"path": "redteam/prompts.jsonl", "sha256": _sha(REDTEAM_BLOB),
             "size_bytes": len(REDTEAM_BLOB)}
    _write_redteam_manifest(r["target_root"], [entry])
    r["redteam_blob"] = REDTEAM_BLOB
    r["redteam_entry"] = entry
    return r


def test_redteam_success_materializes_both_groups(mat, redteam_repos):
    r = redteam_repos
    summary = mat.materialize(
        source_root=r["mod_source_root"], target_root=r["target_root"],
        include_redteam_prompts=True,
    )
    assert summary["ok"] is True
    assert set(summary["groups"]) == {"benchmark_v2", "redteam_prompts"}
    rt = summary["groups"]["redteam_prompts"]
    assert rt["artifact_class"] == "release_test_fixture"
    assert rt["counts"]["materialized"] == 1
    target = r["target_root"] / "redteam" / "prompts.jsonl"
    assert target.read_bytes() == r["redteam_blob"]


def test_redteam_dry_run_writes_nothing(mat, redteam_repos):
    r = redteam_repos
    summary = mat.materialize(
        source_root=r["mod_source_root"], target_root=r["target_root"],
        include_redteam_prompts=True, dry_run=True,
    )
    rt = summary["groups"]["redteam_prompts"]
    assert rt["counts"]["would_materialize"] == 1
    assert rt["counts"]["materialized"] == 0
    assert not (r["target_root"] / "redteam" / "prompts.jsonl").exists()


def test_redteam_matching_target_is_reused(mat, redteam_repos):
    r = redteam_repos
    target = r["target_root"] / "redteam" / "prompts.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(r["redteam_blob"])
    before = target.stat().st_mtime_ns
    summary = mat.materialize(
        source_root=r["mod_source_root"], target_root=r["target_root"],
        include_redteam_prompts=True,
    )
    rt = summary["groups"]["redteam_prompts"]
    assert rt["counts"]["reused"] == 1
    assert target.stat().st_mtime_ns == before


def test_redteam_source_hash_mismatch(mat, redteam_repos):
    r = redteam_repos
    src = r["mod_source_root"] / "redteam" / "prompts.jsonl"
    corrupted = bytearray(src.read_bytes())
    corrupted[0] ^= 0xFF
    src.write_bytes(bytes(corrupted))
    with pytest.raises(mat.MaterializationError) as exc:
        mat.materialize(source_root=r["mod_source_root"], target_root=r["target_root"],
                        include_redteam_prompts=True)
    assert exc.value.code == "source_hash_mismatch"


def test_redteam_target_mismatch_not_overwritten(mat, redteam_repos):
    r = redteam_repos
    target = r["target_root"] / "redteam" / "prompts.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    tampered = b'{"synthetic_redteam": "TAMPERED"}\n'
    target.write_bytes(tampered)
    with pytest.raises(mat.MaterializationError) as exc:
        mat.materialize(source_root=r["mod_source_root"], target_root=r["target_root"],
                        include_redteam_prompts=True)
    assert exc.value.code == "target_mismatch"
    assert target.read_bytes() == tampered


def test_redteam_extra_manifest_entry_rejected(mat, redteam_repos):
    r = redteam_repos
    extra = {"path": "redteam/extra.jsonl", "sha256": _sha(b"x"), "size_bytes": 1}
    _write_redteam_manifest(r["target_root"], [r["redteam_entry"], extra])
    with pytest.raises(mat.MaterializationError) as exc:
        mat.materialize(source_root=r["mod_source_root"], target_root=r["target_root"],
                        include_redteam_prompts=True)
    assert exc.value.code == "manifest_unexpected_paths"


def test_redteam_wrong_path_rejected(mat, redteam_repos):
    r = redteam_repos
    wrong = {"path": "redteam/other.jsonl", "sha256": _sha(b"x"), "size_bytes": 1}
    _write_redteam_manifest(r["target_root"], [wrong])
    with pytest.raises(mat.MaterializationError) as exc:
        mat.materialize(source_root=r["mod_source_root"], target_root=r["target_root"],
                        include_redteam_prompts=True)
    assert exc.value.code == "manifest_unexpected_paths"


def test_redteam_missing_manifest_rejected(mat, redteam_repos):
    r = redteam_repos
    (r["target_root"] / "redteam" / "prompts-manifest.json").unlink()
    with pytest.raises(mat.MaterializationError) as exc:
        mat.materialize(source_root=r["mod_source_root"], target_root=r["target_root"],
                        include_redteam_prompts=True)
    assert exc.value.code == "manifest_missing"


def test_redteam_non_final_manifest_rejected(mat, redteam_repos):
    r = redteam_repos
    _write_redteam_manifest(r["target_root"], [r["redteam_entry"]], status="candidate")
    with pytest.raises(mat.MaterializationError) as exc:
        mat.materialize(source_root=r["mod_source_root"], target_root=r["target_root"],
                        include_redteam_prompts=True)
    assert exc.value.code == "manifest_not_final"


def test_redteam_wrong_artifact_class_rejected(mat, redteam_repos):
    r = redteam_repos
    _write_redteam_manifest(r["target_root"], [r["redteam_entry"]], artifact_class="something_else")
    with pytest.raises(mat.MaterializationError) as exc:
        mat.materialize(source_root=r["mod_source_root"], target_root=r["target_root"],
                        include_redteam_prompts=True)
    assert exc.value.code == "manifest_artifact_class"


def test_redteam_symlink_source_rejected(mat, redteam_repos):
    r = redteam_repos
    src = r["mod_source_root"] / "redteam" / "prompts.jsonl"
    real = r["mod_source_root"] / "redteam" / "_real.bin"
    real.write_bytes(r["redteam_blob"])
    src.unlink()
    try:
        os.symlink(real, src)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted on this host")
    with pytest.raises(mat.MaterializationError) as exc:
        mat.materialize(source_root=r["mod_source_root"], target_root=r["target_root"],
                        include_redteam_prompts=True)
    assert exc.value.code == "symlink_rejected"


def test_redteam_output_is_content_free(mat, redteam_repos):
    r = redteam_repos
    summary = mat.materialize(source_root=r["mod_source_root"], target_root=r["target_root"],
                              include_redteam_prompts=True)
    blob = json.dumps(summary)
    for line in r["redteam_blob"].decode("utf-8").splitlines():
        if line.strip():
            assert line not in blob


def test_backward_compat_without_flag_is_benchmark_only(mat, redteam_repos):
    """Default orchestration (flag absent) processes only benchmark_v2."""
    r = redteam_repos
    summary = mat.materialize(source_root=r["mod_source_root"], target_root=r["target_root"])
    assert set(summary["groups"]) == {"benchmark_v2"}
    assert summary["include_redteam_prompts"] is False
    assert not (r["target_root"] / "redteam" / "prompts.jsonl").exists()


def test_backward_compat_cli_default_shape_unchanged(mat, redteam_repos, tmp_path):
    """CLI without --include-redteam-prompts keeps the flat benchmark summary."""
    r = redteam_repos
    out = tmp_path / "s.json"
    rc = mat.main(["--source-root", str(r["mod_source_root"]),
                   "--target-root", str(r["target_root"]), "--summary-out", str(out)])
    assert rc == 0
    summary = json.loads(out.read_text(encoding="utf-8"))
    # Old flat shape: top-level counts/files, no groups.
    assert "counts" in summary and "groups" not in summary
    assert not (r["target_root"] / "redteam" / "prompts.jsonl").exists()


def test_cli_include_redteam_flag_grouped_shape(mat, redteam_repos, tmp_path):
    r = redteam_repos
    out = tmp_path / "s2.json"
    rc = mat.main(["--source-root", str(r["mod_source_root"]),
                   "--target-root", str(r["target_root"]),
                   "--include-redteam-prompts", "--summary-out", str(out)])
    assert rc == 0
    summary = json.loads(out.read_text(encoding="utf-8"))
    assert set(summary["groups"]) == {"benchmark_v2", "redteam_prompts"}
    assert (r["target_root"] / "redteam" / "prompts.jsonl").exists()
