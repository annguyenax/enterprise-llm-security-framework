"""Freeze/manifest tests for the Phase 12D v2 benchmark
(`scripts/freeze_v2_benchmark.py`).

All mutation/tamper tests run against a `tmp_path` COPY of the real
`datasets/v2/` tree (via monkeypatching the freeze module's own path
constants) -- the real, committed artifacts on disk are never modified by
this test file.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
OUT_DIR = ROOT / "datasets" / "v2"
MANIFEST_PATH = OUT_DIR / "manifests" / "benchmark-v2-manifest.json"
ARTIFACT_SUBDIRS = ("corpus", "cases", "labels", "design")
POLICY_FILES = ("contamination-exemptions.json",)


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def freeze_mod():
    return _load_module("v2_freeze_mod", "freeze_v2_benchmark.py")


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


@pytest.fixture()
def tmp_benchmark_dir(tmp_path, freeze_mod, monkeypatch):
    """Copy the real datasets/v2 tree into tmp_path and point the freeze
    module's OUT_DIR/MANIFEST_PATH at the copy, so freeze/verify calls in
    this fixture's scope never touch the real, committed files."""
    dest = tmp_path / "v2"
    shutil.copytree(OUT_DIR, dest)
    monkeypatch.setattr(freeze_mod, "OUT_DIR", dest)
    monkeypatch.setattr(freeze_mod, "MANIFEST_PATH", dest / "manifests" / "benchmark-v2-manifest.json")
    return dest


# ---------------------------------------------------------------------------
# Real, committed manifest correctness
# ---------------------------------------------------------------------------


def test_manifest_exists_and_is_valid_json():
    assert MANIFEST_PATH.exists()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 1
    assert manifest["benchmark_version"] == "v2"
    assert isinstance(manifest["files"], list)
    assert manifest["file_count"] == len(manifest["files"])


def test_manifest_is_explicitly_labeled_candidate():
    """Code X Phase 12D audit, required-fixes item 7: the manifest must
    remain labeled CANDIDATE FREEZE until Code X, Gemini, and Grok all
    pass and a final regeneration occurs after all accepted fixes."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["manifest_status"] == "candidate"


def test_freeze_cli_output_says_candidate(tmp_benchmark_dir, freeze_mod, capsys):
    assert freeze_mod.cmd_freeze() == 0
    captured = capsys.readouterr()
    assert "CANDIDATE" in captured.out


def test_verify_cli_output_says_candidate(tmp_benchmark_dir, freeze_mod, capsys):
    assert freeze_mod.cmd_freeze() == 0
    capsys.readouterr()
    assert freeze_mod.cmd_verify() == 0
    captured = capsys.readouterr()
    assert "CANDIDATE" in captured.out


def test_manifest_sha256_matches_real_files_on_disk():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        path = OUT_DIR / entry["path"]
        assert path.exists(), f"manifest references missing file: {entry['path']}"
        assert _sha256_of(path) == entry["sha256"], f"sha256 mismatch for {entry['path']}"
        assert path.stat().st_size == entry["size_bytes"], f"size mismatch for {entry['path']}"
        assert len(entry["sha256"]) == 64


def test_manifest_covers_exactly_the_real_artifact_files():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest_paths = {e["path"] for e in manifest["files"]}
    actual_paths = set()
    for sub in ARTIFACT_SUBDIRS:
        subdir = OUT_DIR / sub
        for p in subdir.rglob("*"):
            if p.is_file():
                actual_paths.add(p.relative_to(OUT_DIR).as_posix())
    for name in POLICY_FILES:
        path = OUT_DIR / name
        if path.exists():
            actual_paths.add(name)
    assert manifest_paths == actual_paths


def test_manifest_excludes_itself():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest_paths = {e["path"] for e in manifest["files"]}
    assert "manifests/benchmark-v2-manifest.json" not in manifest_paths


def test_manifest_has_no_absolute_or_machine_specific_paths():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        p = entry["path"]
        assert not Path(p).is_absolute(), f"absolute path in manifest: {p}"
        assert ":" not in p, f"drive-letter-shaped path in manifest: {p}"
        assert "\\" not in p, f"non-POSIX separator in manifest path: {p}"
        assert str(ROOT) not in p


def test_manifest_files_sorted_by_path():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    paths = [e["path"] for e in manifest["files"]]
    assert paths == sorted(paths)


def test_manifest_includes_holdout_files_no_special_exemption():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest_paths = {e["path"] for e in manifest["files"]}
    assert "cases/holdout.jsonl" in manifest_paths
    assert "labels/holdout.jsonl" in manifest_paths


def test_manifest_no_timestamp_fields():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    top_level_keys = {k.lower() for e in ([manifest] + manifest["files"]) for k in e}
    for token in ("timestamp", "created_at", "generated_at", "updated_at"):
        assert token not in top_level_keys


def test_committed_tree_verifies_clean(freeze_mod):
    assert freeze_mod.cmd_verify() == 0


# ---------------------------------------------------------------------------
# Freeze/verify round-trip and tamper detection, isolated in tmp_path
# ---------------------------------------------------------------------------


def test_freeze_then_verify_round_trip(tmp_benchmark_dir, freeze_mod):
    assert freeze_mod.cmd_freeze() == 0
    assert freeze_mod.cmd_verify() == 0


def test_verify_fails_without_a_manifest(tmp_path, freeze_mod, monkeypatch):
    dest = tmp_path / "v2_no_manifest"
    shutil.copytree(OUT_DIR, dest)
    (dest / "manifests" / "benchmark-v2-manifest.json").unlink()
    monkeypatch.setattr(freeze_mod, "OUT_DIR", dest)
    monkeypatch.setattr(freeze_mod, "MANIFEST_PATH", dest / "manifests" / "benchmark-v2-manifest.json")
    assert freeze_mod.cmd_verify() == 1


def test_verify_fails_after_content_mutation(tmp_benchmark_dir, freeze_mod, capsys):
    assert freeze_mod.cmd_freeze() == 0
    target = tmp_benchmark_dir / "cases" / "development.jsonl"
    with target.open("a", encoding="utf-8", newline="") as f:
        f.write('{"case_id": "TAMPERED", "split": "development"}\n')

    result = freeze_mod.cmd_verify()
    captured = capsys.readouterr()
    assert result == 1
    assert "cases/development.jsonl" in captured.err
    assert "content changed since freeze" in captured.err or "size changed since freeze" in captured.err


def test_verify_fails_on_missing_frozen_file(tmp_benchmark_dir, freeze_mod, capsys):
    assert freeze_mod.cmd_freeze() == 0
    target = tmp_benchmark_dir / "labels" / "validation.jsonl"
    target.unlink()

    result = freeze_mod.cmd_verify()
    captured = capsys.readouterr()
    assert result == 1
    assert "missing file that was frozen" in captured.err
    assert "labels/validation.jsonl" in captured.err


def test_verify_fails_on_new_unfrozen_file(tmp_benchmark_dir, freeze_mod, capsys):
    assert freeze_mod.cmd_freeze() == 0
    (tmp_benchmark_dir / "corpus" / "extra-unfrozen.jsonl").write_text('{}\n', encoding="utf-8")

    result = freeze_mod.cmd_verify()
    captured = capsys.readouterr()
    assert result == 1
    assert "new, unfrozen file present" in captured.err
    assert "corpus/extra-unfrozen.jsonl" in captured.err


def test_verify_passes_again_after_clean_rebuild_restores_content(tmp_benchmark_dir, freeze_mod, build_mod_for_freeze):
    """Mutating a copy and then deterministically rebuilding it (the same
    generator that produced the frozen original) restores byte-identical
    content, so verify passes again with no drift -- proves the freeze
    manifest is a pure content check, not a "did someone touch it" flag."""
    assert freeze_mod.cmd_freeze() == 0
    target = tmp_benchmark_dir / "cases" / "development.jsonl"
    original = target.read_text(encoding="utf-8", newline="")
    target.write_text(original + '{"case_id": "TAMPERED"}\n', encoding="utf-8", newline="")
    assert freeze_mod.cmd_verify() == 1

    target.write_text(original, encoding="utf-8", newline="")
    assert freeze_mod.cmd_verify() == 0


@pytest.fixture()
def build_mod_for_freeze():
    return _load_module("v2_build_mod_for_freeze", "build_v2_benchmark.py")


def test_holdout_freeze_discipline_no_dev_val_exemption(tmp_benchmark_dir, freeze_mod, capsys):
    """The freeze/verify mechanism applies identically to holdout files as
    to development/validation files -- there is no code path that skips
    hashing or verifying holdout.jsonl, so a holdout mutation is caught
    exactly like any other."""
    assert freeze_mod.cmd_freeze() == 0
    target = tmp_benchmark_dir / "labels" / "holdout.jsonl"
    with target.open("a", encoding="utf-8") as f:
        f.write('{"case_id": "TAMPERED-HOLDOUT"}\n')

    result = freeze_mod.cmd_verify()
    captured = capsys.readouterr()
    assert result == 1
    assert "labels/holdout.jsonl" in captured.err


# ---------------------------------------------------------------------------
# Code X Phase 12D RE-AUDIT: manifest policy-artifact integrity --
# contamination-exemptions.json and the authoring-provenance artifact are
# now inside the frozen candidate manifest's scope.
# ---------------------------------------------------------------------------


def test_manifest_scope_includes_policy_artifacts(freeze_mod):
    """The real, committed manifest must cover contamination-exemptions.json
    and datasets/v2/design/authoring-provenance.jsonl, not only
    corpus/cases/labels."""
    manifest = freeze_mod.build_manifest()
    paths = {e["path"] for e in manifest["files"]}
    assert "contamination-exemptions.json" in paths
    assert "design/authoring-provenance.jsonl" in paths


def test_exemption_file_mutation_fails_verification(tmp_benchmark_dir, freeze_mod, capsys):
    """Required regression #1."""
    assert freeze_mod.cmd_freeze() == 0
    target = tmp_benchmark_dir / "contamination-exemptions.json"
    target.write_text('{"exemptions": [{"scope": "query", "id_a": "a", "id_b": "b", "rationale": "tampered"}]}', encoding="utf-8")

    result = freeze_mod.cmd_verify()
    captured = capsys.readouterr()
    assert result == 1
    assert "contamination-exemptions.json" in captured.err


def test_authoring_provenance_mutation_fails_verification(tmp_benchmark_dir, freeze_mod, capsys):
    """Required regression #2."""
    assert freeze_mod.cmd_freeze() == 0
    target = tmp_benchmark_dir / "design" / "authoring-provenance.jsonl"
    with target.open("a", encoding="utf-8") as f:
        f.write('{"artifact_id": "TAMPERED"}\n')

    result = freeze_mod.cmd_verify()
    captured = capsys.readouterr()
    assert result == 1
    assert "design/authoring-provenance.jsonl" in captured.err


def test_missing_policy_bearing_file_fails_verification(tmp_benchmark_dir, freeze_mod, capsys):
    """Required regression #3."""
    assert freeze_mod.cmd_freeze() == 0
    (tmp_benchmark_dir / "contamination-exemptions.json").unlink()

    result = freeze_mod.cmd_verify()
    captured = capsys.readouterr()
    assert result == 1
    assert "missing file that was frozen: contamination-exemptions.json" in captured.err


@pytest.mark.parametrize(
    "relative_path",
    ["contamination-exemptions.json", "design/authoring-provenance.jsonl"],
)
def test_freeze_refuses_to_create_incomplete_candidate(
    tmp_benchmark_dir, freeze_mod, capsys, relative_path,
):
    """A fresh freeze must not bless a tree missing policy-bearing input."""
    (tmp_benchmark_dir / relative_path).unlink()
    result = freeze_mod.cmd_freeze()
    captured = capsys.readouterr()
    assert result == 1
    assert "required candidate artifact(s) missing" in captured.err
    assert relative_path in captured.err


def test_unexpected_new_policy_bearing_file_fails_verification(tmp_benchmark_dir, freeze_mod, capsys):
    """Required regression #4: a new, unfrozen file inside the frozen
    scope (e.g. an extra design/ artifact) must fail verification."""
    assert freeze_mod.cmd_freeze() == 0
    (tmp_benchmark_dir / "design" / "extra-unfrozen-provenance.jsonl").write_text("{}\n", encoding="utf-8")

    result = freeze_mod.cmd_verify()
    captured = capsys.readouterr()
    assert result == 1
    assert "new, unfrozen file present: design/extra-unfrozen-provenance.jsonl" in captured.err


def test_deterministic_rebuild_restores_candidate_verification_with_policy_artifacts(
    tmp_benchmark_dir, freeze_mod, build_mod_for_freeze,
):
    """Required regression #5: mutating a policy-bearing file and then
    deterministically rebuilding the whole tree (corpus/cases/labels/
    provenance together) restores byte-identical content, so verify
    passes again."""
    assert freeze_mod.cmd_freeze() == 0
    exemptions_path = tmp_benchmark_dir / "contamination-exemptions.json"
    original = exemptions_path.read_text(encoding="utf-8", newline="")
    exemptions_path.write_text('{"exemptions": [{"scope": "query", "id_a": "x", "id_b": "y", "rationale": "temp"}]}', encoding="utf-8", newline="")
    assert freeze_mod.cmd_verify() == 1

    exemptions_path.write_text(original, encoding="utf-8", newline="")
    assert freeze_mod.cmd_verify() == 0
