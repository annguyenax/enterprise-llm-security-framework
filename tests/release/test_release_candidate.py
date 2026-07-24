"""Phase 12G release builder + verifier + policy + snapshot tests. Synthetic only."""
from __future__ import annotations

import json
import os
import subprocess
import unittest.mock as mock
import zipfile
from pathlib import Path

import pytest


def _build(builder, repo, out, **kw):
    return builder.build_release_candidate(repo_root=repo, output_dir=out, **kw)


def _commit(git, msg="change"):
    git("add", "-A"); git("commit", "-q", "-m", msg)


# =========================================================================== #
# Clean build + verify (production paths)
# =========================================================================== #
def test_clean_build_and_verify_pass(builder, verifier, synthetic_repo, tmp_path):
    s = _build(builder, synthetic_repo, tmp_path / "out")
    assert s["ok"] is True and s["policy_id"] == "phase12g-test-policy-v2"
    report = verifier.verify_release_candidate(Path(s["zip_path"]))
    assert report["status"] == "PASS", report
    with zipfile.ZipFile(s["zip_path"]) as z:
        names = set(z.namelist())
    assert {"release-manifest.json", "SHA256SUMS.txt", "FILE_SIZES.json"} <= names
    assert "repo/release/release-allowlist.json" in names
    assert "repo/.env.example" in names


def test_policy_sha_recorded_in_manifest(builder, synthetic_repo, tmp_path, common):
    s = _build(builder, synthetic_repo, tmp_path / "out")
    with zipfile.ZipFile(s["zip_path"]) as z:
        manifest = json.loads(z.read("release-manifest.json"))
        policy_bytes = z.read("repo/release/release-allowlist.json")
    assert manifest["policy_sha256"] == common.sha256_bytes(policy_bytes)
    assert manifest["policy_sha256"] == s["policy_sha256"]
    assert manifest["policy_schema_version"] == 2


def test_changed_policy_changes_release_identity(builder, synthetic_repo, tmp_path, git):
    a = _build(builder, synthetic_repo, tmp_path / "a")["zip_sha256"]
    pol = json.loads((synthetic_repo / "release/release-allowlist.json").read_text())
    pol["prohibited"]["env"]["allow_exceptions"] = [".env.sample", ".env.example", ".env.template"]
    (synthetic_repo / "release/release-allowlist.json").write_text(json.dumps(pol, indent=2), encoding="utf-8")
    _commit(git, "policy tweak")
    b = _build(builder, synthetic_repo, tmp_path / "b")["zip_sha256"]
    assert a != b


# =========================================================================== #
# Policy enforcement
# =========================================================================== #
def test_malformed_policy_rejected(builder, synthetic_repo, tmp_path, git):
    (synthetic_repo / "release/release-allowlist.json").write_text("{not json", encoding="utf-8")
    _commit(git, "break policy")
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert exc.value.code == "malformed_json"


def test_missing_required_policy_class_rejected(builder, synthetic_repo, tmp_path, git):
    pol = json.loads((synthetic_repo / "release/release-allowlist.json").read_text())
    del pol["prohibited"]["extensions"]
    (synthetic_repo / "release/release-allowlist.json").write_text(json.dumps(pol), encoding="utf-8")
    _commit(git, "drop class")
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert exc.value.code == "policy_missing"


def test_unknown_policy_key_rejected(builder, synthetic_repo, tmp_path, git):
    pol = json.loads((synthetic_repo / "release/release-allowlist.json").read_text())
    pol["surprise"] = 1
    (synthetic_repo / "release/release-allowlist.json").write_text(json.dumps(pol), encoding="utf-8")
    _commit(git, "unknown key")
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert exc.value.code == "policy_unknown_key"


def test_conflicting_classification_rejected(builder, synthetic_repo, tmp_path, git):
    pol = json.loads((synthetic_repo / "release/release-allowlist.json").read_text())
    pol["prohibited"]["exact_names"].append(".env.example")
    (synthetic_repo / "release/release-allowlist.json").write_text(json.dumps(pol), encoding="utf-8")
    _commit(git, "conflict")
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert exc.value.code == "policy_conflict"


def test_missing_required_present_file_rejected(builder, synthetic_repo, tmp_path, git):
    pol = json.loads((synthetic_repo / "release/release-allowlist.json").read_text())
    pol["required_present"].append("does/not/exist.json")
    (synthetic_repo / "release/release-allowlist.json").write_text(json.dumps(pol), encoding="utf-8")
    _commit(git, "require missing")
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert exc.value.code == "policy_required_missing"


def test_prohibited_tracked_file_rejected_by_policy(builder, synthetic_repo, tmp_path, git):
    (synthetic_repo / "server.pem").write_text("key\n", encoding="utf-8")
    git("add", "-f", "server.pem"); _commit(git, "add pem")
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert exc.value.code == "prohibited_artifact"


def test_cli_cannot_broaden_policy(builder, synthetic_repo, tmp_path):
    (synthetic_repo / "extra.db").write_bytes(b"x")  # untracked generated
    gen = tmp_path / "gen.json"
    gen.write_text(json.dumps({"schema_version": 1, "files": [
        {"path": "extra.db", "sha256": "0" * 64, "size_bytes": 1}]}), encoding="utf-8")
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, tmp_path / "out", generated_allowlist=gen)
    assert exc.value.code == "prohibited_artifact"


def test_ignored_jsonl_excluded(builder, synthetic_repo, tmp_path):
    (synthetic_repo / "cases.jsonl").write_text('{"c":1}\n', encoding="utf-8")  # ignored
    s = _build(builder, synthetic_repo, tmp_path / "out")
    with zipfile.ZipFile(s["zip_path"]) as z:
        assert not any(n.endswith(".jsonl") for n in z.namelist())


# =========================================================================== #
# Snapshot integrity
# =========================================================================== #
def test_zip_bytes_are_the_hashed_bytes(builder, synthetic_repo, tmp_path):
    import hashlib
    s = _build(builder, synthetic_repo, tmp_path / "out")
    with zipfile.ZipFile(s["zip_path"]) as z:
        manifest = json.loads(z.read("release-manifest.json"))
        for item in manifest["files"]:
            data = z.read(item["archive_path"])
            assert hashlib.sha256(data).hexdigest() == item["sha256"]
            assert len(data) == item["size_bytes"]


def test_clean_tree_rechecked_after_snapshot(builder, synthetic_repo, tmp_path, monkeypatch, common):
    real_snapshot = common.read_snapshot_bytes
    state = {"done": False}

    def mutating(path):
        data = real_snapshot(path)
        if not state["done"] and path.name == "README.md":
            state["done"] = True
            (synthetic_repo / "README.md").write_text("MUTATED DURING SNAPSHOT\n", encoding="utf-8")
        return data

    monkeypatch.setattr(builder, "read_snapshot_bytes", mutating)
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert exc.value.code == "source_changed"
    subprocess.run(["git", "-C", str(synthetic_repo), "checkout", "--", "README.md"], capture_output=True)


def test_mutation_size_change_fails_closed(common, tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"12345")
    real_stat = Path.stat

    def fake_stat(self, *a, **k):
        if self == p:
            class S:
                st_size = 999999
            return S()
        return real_stat(self, *a, **k)

    with mock.patch.object(Path, "stat", fake_stat):
        with pytest.raises(common.ReleaseError) as exc:
            common.read_snapshot_bytes(p)
    assert exc.value.code == "source_changed"


# =========================================================================== #
# Fail-closed build refusals
# =========================================================================== #
def test_dirty_tree_refused(builder, synthetic_repo, tmp_path):
    (synthetic_repo / "README.md").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert exc.value.code == "dirty_tree"


def test_existing_output_refused(builder, synthetic_repo, tmp_path):
    out = tmp_path / "out"; out.mkdir()
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, out)
    assert exc.value.code == "output_reuse"


def test_tracked_jsonl_refused(builder, synthetic_repo, tmp_path, git):
    (synthetic_repo / "records.jsonl").write_text('{"x":1}\n', encoding="utf-8")
    git("add", "-f", "records.jsonl"); _commit(git, "jsonl")
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert exc.value.code == "tracked_jsonl"


def test_symlink_tracked_file_rejected(builder, synthetic_repo, tmp_path, git):
    real = synthetic_repo / "real.txt"; real.write_text("real\n", encoding="utf-8")
    link = synthetic_repo / "link.txt"
    try:
        os.symlink(real, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted on this host")
    git("add", "-A"); _commit(git, "symlink")
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert exc.value.code == "symlink_rejected"


# =========================================================================== #
# Verifier completeness (repackage the ZIP to inject defects)
# =========================================================================== #
def _repackage(zip_src: Path, zip_dst: Path, mutate):
    with zipfile.ZipFile(zip_src) as z:
        items = {i.filename: z.read(i.filename) for i in z.infolist()}
    mutate(items)
    with zipfile.ZipFile(zip_dst, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(items):
            z.writestr(name, items[name])


@pytest.fixture()
def built_zip(builder, synthetic_repo, tmp_path):
    return Path(_build(builder, synthetic_repo, tmp_path / "out")["zip_path"])


def test_verify_pass(verifier, built_zip):
    assert verifier.verify_release_candidate(built_zip)["status"] == "PASS"


@pytest.mark.parametrize("control", ["release-manifest.json", "SHA256SUMS.txt", "FILE_SIZES.json"])
def test_verify_missing_control_rejected(verifier, built_zip, tmp_path, control):
    dst = tmp_path / "m.zip"
    _repackage(built_zip, dst, lambda it: it.pop(control))
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL"
    assert any(f["code"] == "missing_control_file" for f in r["findings"])


def test_verify_omitted_checksum_entry_rejected(verifier, built_zip, tmp_path):
    def mut(it):
        lines = it["SHA256SUMS.txt"].decode().splitlines()
        it["SHA256SUMS.txt"] = ("\n".join(lines[1:]) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "checksums_set_mismatch" for f in r["findings"])


def test_verify_extra_checksum_entry_rejected(verifier, built_zip, tmp_path):
    def mut(it):
        it["SHA256SUMS.txt"] += (("0" * 64) + "  repo/ghost.txt\n").encode()
    dst = tmp_path / "z.zip"; _repackage(built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "checksums_set_mismatch" for f in r["findings"])


def test_verify_omitted_size_entry_rejected(verifier, built_zip, tmp_path):
    def mut(it):
        sizes = json.loads(it["FILE_SIZES.json"])
        sizes["files"].pop(next(iter(sizes["files"])))
        it["FILE_SIZES.json"] = (json.dumps(sizes) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "sizes_set_mismatch" for f in r["findings"])


def test_verify_malformed_checksum_spacing_rejected(verifier, built_zip, tmp_path):
    def mut(it):
        lines = it["SHA256SUMS.txt"].decode().splitlines()
        lines[0] = lines[0].replace("  ", " ", 1)
        it["SHA256SUMS.txt"] = ("\n".join(lines) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "checksums_format" for f in r["findings"])


def test_verify_duplicate_json_key_rejected(verifier, built_zip, tmp_path):
    def mut(it):
        it["release-manifest.json"] = b'{"schema_version":2,"schema_version":2}'
    dst = tmp_path / "z.zip"; _repackage(built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "duplicate_json_key" for f in r["findings"])


def test_verify_manifest_hash_mismatch_rejected(verifier, built_zip, tmp_path):
    def mut(it):
        it["repo/README.md"] = b"TAMPERED\n"
    dst = tmp_path / "z.zip"; _repackage(built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL"
    assert any(f["code"] in {"changed_file", "manifest_payload_mismatch",
                             "sizes_set_mismatch", "checksums_set_mismatch"} for f in r["findings"])


def test_verify_unexpected_payload_entry_rejected(verifier, built_zip, tmp_path):
    def mut(it):
        it["repo/surprise.txt"] = b"extra\n"
    dst = tmp_path / "z.zip"; _repackage(built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL"
    assert any(f["code"] in {"manifest_payload_mismatch", "sizes_set_mismatch", "checksums_set_mismatch"}
               for f in r["findings"])


def test_verify_unexpected_control_entry_rejected(verifier, built_zip, tmp_path):
    def mut(it):
        it["EXTRA_CONTROL.txt"] = b"nope\n"
    dst = tmp_path / "z.zip"; _repackage(built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "unexpected_entry" for f in r["findings"])


def test_verify_jsonl_entry_rejected(verifier, built_zip, tmp_path):
    def mut(it):
        it["repo/records.jsonl"] = b'{"x":1}\n'
    dst = tmp_path / "z.zip"; _repackage(built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL"
    assert any(f["code"] in {"jsonl_present", "prohibited_present", "manifest_payload_mismatch",
                             "sizes_set_mismatch", "checksums_set_mismatch"} for f in r["findings"])


def test_verify_not_verifiable_is_not_pass(verifier, tmp_path):
    import hashlib
    manifest = {"schema_version": 2, "repo_head": "a" * 40, "base_sha": None,
                "policy_sha256": "b" * 64, "policy_schema_version": 2, "files": []}
    mbytes = (json.dumps(manifest) + "\n").encode()
    files = {"release-manifest.json": mbytes}
    files["FILE_SIZES.json"] = (json.dumps({"schema_version": 1, "files": {
        "release-manifest.json": len(mbytes)}}) + "\n").encode()
    sums = {n: hashlib.sha256(files[n]).hexdigest() for n in files}
    files["SHA256SUMS.txt"] = "".join(f"{sums[n]}  {n}\n" for n in sorted(sums)).encode()
    z = tmp_path / "empty.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for n in sorted(files):
            zf.writestr(n, files[n])
    r = verifier.verify_release_candidate(z)
    assert r["status"] == "NOT_VERIFIABLE" and r["passed"] is False


def test_verify_does_not_modify_zip(verifier, built_zip):
    before = built_zip.read_bytes()
    verifier.verify_release_candidate(built_zip)
    assert built_zip.read_bytes() == before
