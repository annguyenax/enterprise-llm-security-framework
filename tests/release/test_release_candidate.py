"""Phase 12G closed-world policy + strict verifier + verify-before-publish tests.

Synthetic fixtures only; no real benchmark records. Exercises production builder,
verifier and policy code paths.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import unittest.mock as mock
import zipfile
from pathlib import Path

import pytest

from conftest import valid_policy_obj, write_policy


def _build(builder, repo, out, **kw):
    return builder.build_release_candidate(repo_root=repo, output_dir=out, **kw)


def _commit(git, msg="change"):
    git("add", "-A"); git("commit", "-q", "-m", msg)


def _rebuild_zip(common, items: dict) -> bytes:
    """Deterministic re-zip (matches builder metadata) so only injected defects show."""
    return common.deterministic_zip_bytes(items)


def _repackage(common, zip_src: Path, zip_dst: Path, mutate):
    with zipfile.ZipFile(zip_src) as z:
        items = {i.filename: z.read(i.filename) for i in z.infolist()}
    mutate(items)
    zip_dst.write_bytes(_rebuild_zip(common, items))


# =========================================================================== #
# Baseline build + verify
# =========================================================================== #
def test_clean_build_and_verify_pass(builder, verifier, synthetic_repo, tmp_path):
    s = _build(builder, synthetic_repo, tmp_path / "out")
    assert s["ok"] is True and s["policy_id"] == "phase12g-test-policy-v3"
    assert s["verified_before_publish"] is True and s["published_atomically"] is True
    report = verifier.verify_release_candidate(Path(s["zip_path"]))
    assert report["status"] == "PASS", report
    with zipfile.ZipFile(s["zip_path"]) as z:
        names = set(z.namelist())
    assert {"release-manifest.json", "SHA256SUMS.txt", "FILE_SIZES.json"} <= names
    assert "repo/release/release-allowlist.json" in names
    assert "repo/.env.example" in names


def test_every_tracked_path_has_exactly_one_classification(common, synthetic_repo):
    pol = common.parse_release_policy((synthetic_repo / "release/release-allowlist.json").read_bytes())
    tracked = [x for x in subprocess.run(
        ["git", "-C", str(synthetic_repo), "ls-files", "-z"],
        capture_output=True, text=True).stdout.split("\0") if x]
    classes = {rel: common.classify_tracked_path(rel, pol) for rel in tracked}
    assert all(c in common.INCLUSION_CLASSES for c in classes.values())
    assert classes["release/release-allowlist.json"] == common.CLASS_REQUIRED


def test_manifest_records_policy_schema_and_sha(builder, synthetic_repo, tmp_path, common):
    s = _build(builder, synthetic_repo, tmp_path / "out")
    with zipfile.ZipFile(s["zip_path"]) as z:
        manifest = json.loads(z.read("release-manifest.json"))
        policy_bytes = z.read("repo/release/release-allowlist.json")
    assert manifest["policy"]["sha256"] == common.sha256_bytes(policy_bytes) == s["policy_sha256"]
    assert manifest["policy"]["schema_version"] == 3
    assert manifest["schema_version"] == 3


def test_changed_policy_changes_release_identity(builder, synthetic_repo, tmp_path, git):
    a = _build(builder, synthetic_repo, tmp_path / "a")["zip_sha256"]
    pol = json.loads((synthetic_repo / "release/release-allowlist.json").read_text())
    pol["prohibited"]["env"]["allow_exceptions"] = [".env.sample", ".env.example", ".env.template"]
    (synthetic_repo / "release/release-allowlist.json").write_text(json.dumps(pol, indent=2), encoding="utf-8")
    _commit(git, "policy tweak")
    b = _build(builder, synthetic_repo, tmp_path / "b")["zip_sha256"]
    assert a != b


# =========================================================================== #
# Phase C — closed-world policy enforcement
# =========================================================================== #
def test_valid_closed_world_policy_accepted(common):
    pol = common.parse_release_policy(json.dumps(valid_policy_obj(
        ["release/release-allowlist.json"])).encode("utf-8"))
    assert pol.schema_version == 3 and pol.policy_id == "phase12g-test-policy-v3"


def test_unknown_top_level_key_rejected(builder, synthetic_repo, tmp_path, git):
    obj = valid_policy_obj(["release/release-allowlist.json", "release/release-policy.md"])
    obj["surprise"] = 1
    write_policy(synthetic_repo, obj); _commit(git)
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code == "policy_unknown_key"


def test_unknown_nested_key_rejected(builder, synthetic_repo, tmp_path, git):
    obj = valid_policy_obj(["release/release-allowlist.json", "release/release-policy.md"])
    obj["inclusion"]["mystery"] = []
    write_policy(synthetic_repo, obj); _commit(git)
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code == "policy_unknown_key"


def test_missing_required_class_rejected(builder, synthetic_repo, tmp_path, git):
    obj = valid_policy_obj(["release/release-allowlist.json", "release/release-policy.md"])
    del obj["inclusion"]["required_paths"]
    write_policy(synthetic_repo, obj); _commit(git)
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code == "policy_missing"


def test_missing_optional_class_rejected(builder, synthetic_repo, tmp_path, git):
    obj = valid_policy_obj(["release/release-allowlist.json", "release/release-policy.md"])
    del obj["inclusion"]["allowed_extensions"]
    write_policy(synthetic_repo, obj); _commit(git)
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code == "policy_missing"


def test_missing_prohibited_class_rejected(builder, synthetic_repo, tmp_path, git):
    obj = valid_policy_obj(["release/release-allowlist.json", "release/release-policy.md"])
    del obj["prohibited"]["extensions"]
    write_policy(synthetic_repo, obj); _commit(git)
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code == "policy_missing"


def test_malformed_rule_value_rejected(builder, synthetic_repo, tmp_path, git):
    obj = valid_policy_obj(["release/release-allowlist.json", "release/release-policy.md"])
    obj["inclusion"]["allowed_extensions"] = [123]
    write_policy(synthetic_repo, obj); _commit(git)
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code == "policy_schema"


def test_unsupported_wildcard_syntax_rejected(builder, synthetic_repo, tmp_path, git):
    obj = valid_policy_obj(["release/release-allowlist.json", "release/release-policy.md"])
    obj["inclusion"]["allowed_extensions"].append(".*")
    write_policy(synthetic_repo, obj); _commit(git)
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code == "policy_pattern"


def test_duplicate_rule_rejected(builder, synthetic_repo, tmp_path, git):
    obj = valid_policy_obj(["release/release-allowlist.json", "release/release-policy.md"])
    obj["inclusion"]["allowed_extensions"].append(".MD")  # case-collides with .md
    write_policy(synthetic_repo, obj); _commit(git)
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code == "policy_conflict"


def test_required_optional_overlap_rejected(builder, synthetic_repo, tmp_path, git):
    obj = valid_policy_obj(["release/release-allowlist.json", "release/release-policy.md"],
                           allowed_archives=[{"path": "release/release-policy.md", "reason": "x"}])
    write_policy(synthetic_repo, obj); _commit(git)
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    # policy-def conflict: a required path also declared as an allowed archive
    assert e.value.code in {"ambiguous_policy_classification", "policy_conflict"}


def test_required_prohibited_overlap_rejected(common):
    obj = valid_policy_obj(["secret.pem"])  # required path matches a prohibited extension
    with pytest.raises(common.ReleaseError) as e:
        common.parse_release_policy(json.dumps(obj).encode("utf-8"))
    assert e.value.code == "ambiguous_policy_classification"


def test_optional_prohibited_overlap_rejected(common):
    obj = valid_policy_obj(["release/release-allowlist.json"])
    obj["inclusion"]["allowed_extensions"].append(".jsonl")  # allowed & prohibited
    with pytest.raises(common.ReleaseError) as e:
        common.parse_release_policy(json.dumps(obj).encode("utf-8"))
    assert e.value.code == "ambiguous_policy_classification"


def test_unclassified_tracked_root_file_rejected(builder, synthetic_repo, tmp_path, git):
    (synthetic_repo / "mystery.xyz").write_text("data\n", encoding="utf-8")
    _commit(git, "unclassified root")
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code == "unclassified_tracked_path"


def test_unclassified_tracked_nested_file_rejected(builder, synthetic_repo, tmp_path, git):
    (synthetic_repo / "src" / "data.bin").write_bytes(b"\x00\x01")
    _commit(git, "unclassified nested")
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code == "unclassified_tracked_path"


def test_safe_looking_unknown_extension_rejected(builder, synthetic_repo, tmp_path, git):
    (synthetic_repo / "config.ini").write_text("[a]\n", encoding="utf-8")  # not in allowed_extensions
    _commit(git, "unknown ext")
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code == "unclassified_tracked_path"


def test_cli_cannot_broaden_policy(builder, synthetic_repo, tmp_path):
    (synthetic_repo / "extra.db").write_bytes(b"x")  # untracked; declared via generated allowlist
    gen = tmp_path / "gen.json"
    gen.write_text(json.dumps({"schema_version": 1, "files": [
        {"path": "extra.db", "sha256": "0" * 64, "size_bytes": 1}]}), encoding="utf-8")
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out", generated_allowlist=gen)
    assert e.value.code == "prohibited_artifact"


def test_generated_allowlist_cannot_broaden_to_unclassified(builder, synthetic_repo, tmp_path):
    (synthetic_repo / "weird.xyz").write_bytes(b"x")
    gen = tmp_path / "gen.json"
    gen.write_text(json.dumps({"schema_version": 1, "files": [
        {"path": "weird.xyz", "sha256": "0" * 64, "size_bytes": 1}]}), encoding="utf-8")
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out", generated_allowlist=gen)
    assert e.value.code == "unclassified_tracked_path"


def test_tracked_prohibited_file_fails_build(builder, synthetic_repo, tmp_path, git):
    (synthetic_repo / "server.pem").write_text("key\n", encoding="utf-8")
    git("add", "-f", "server.pem"); _commit(git, "add pem")
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code == "prohibited_artifact"


def test_unclassified_archive_rejected_without_allowlist(builder, synthetic_repo, tmp_path, git, common):
    (synthetic_repo / "bundle.zip").write_bytes(_rebuild_zip(common, {"a.txt": b"x"}))
    git("add", "-f", "bundle.zip"); _commit(git, "add zip")
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code == "prohibited_artifact"


def test_allowed_archive_with_prohibited_nested_name_fails(builder, synthetic_repo, tmp_path, git, common):
    bad = _rebuild_zip(common, {"inner/records.jsonl": b'{"x":1}\n', "ok.txt": b"y"})
    (synthetic_repo / "bundle.zip").write_bytes(bad)
    obj = valid_policy_obj(["release/release-allowlist.json", "release/release-policy.md"],
                           allowed_archives=[{"path": "bundle.zip", "reason": "test archive"}])
    write_policy(synthetic_repo, obj)
    git("add", "-f", "bundle.zip"); _commit(git, "add zip + policy")
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code == "prohibited_nested_entry"


def test_allowed_archive_with_safe_names_included(builder, synthetic_repo, tmp_path, git, common):
    good = _rebuild_zip(common, {"inner/fig.txt": b"z", "inner/doc.md": b"m"})
    (synthetic_repo / "bundle.zip").write_bytes(good)
    obj = valid_policy_obj(["release/release-allowlist.json", "release/release-policy.md"],
                           allowed_archives=[{"path": "bundle.zip", "reason": "safe report assets"}])
    write_policy(synthetic_repo, obj)
    git("add", "-f", "bundle.zip"); _commit(git, "add safe zip")
    s = _build(builder, synthetic_repo, tmp_path / "out")
    with zipfile.ZipFile(s["zip_path"]) as z:
        manifest = json.loads(z.read("release-manifest.json"))
    klass = {f["path"]: f["classification"] for f in manifest["files"]}
    assert klass["bundle.zip"] == "ALLOWED_ARCHIVE"


def test_malformed_policy_utf8_fails_closed(common):
    with pytest.raises(common.ReleaseError) as e:
        common.parse_release_policy(b"\xff\xfe not utf8")
    assert e.value.code == "malformed_utf8"


def test_malformed_policy_json_rejected(builder, synthetic_repo, tmp_path, git):
    (synthetic_repo / "release/release-allowlist.json").write_text("{not json", encoding="utf-8")
    _commit(git, "break policy")
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code == "malformed_json"


def test_missing_required_present_file_rejected(builder, synthetic_repo, tmp_path, git):
    obj = valid_policy_obj(["release/release-allowlist.json", "release/does-not-exist.md"])
    write_policy(synthetic_repo, obj); _commit(git)
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code == "policy_required_missing"


def test_ignored_jsonl_excluded(builder, synthetic_repo, tmp_path):
    (synthetic_repo / "cases.jsonl").write_text('{"c":1}\n', encoding="utf-8")  # ignored
    s = _build(builder, synthetic_repo, tmp_path / "out")
    with zipfile.ZipFile(s["zip_path"]) as z:
        assert not any(n.endswith(".jsonl") for n in z.namelist())


# =========================================================================== #
# Phase H — snapshot + publication integrity
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


def test_arbitrary_binary_bytes_preserved(builder, synthetic_repo, tmp_path, git):
    raw = bytes(range(256)) * 8
    (synthetic_repo / "docs").mkdir()
    (synthetic_repo / "docs" / "figure.png").write_bytes(raw)
    obj = valid_policy_obj(["release/release-allowlist.json", "release/release-policy.md"])
    obj["inclusion"]["allowed_extensions"].append(".png")
    write_policy(synthetic_repo, obj)
    git("add", "-f", "docs/figure.png"); _commit(git, "png")
    s = _build(builder, synthetic_repo, tmp_path / "out")
    with zipfile.ZipFile(s["zip_path"]) as z:
        assert z.read("repo/docs/figure.png") == raw


def test_policy_single_read_bytes_match_package(builder, synthetic_repo, tmp_path, common):
    s = _build(builder, synthetic_repo, tmp_path / "out")
    with zipfile.ZipFile(s["zip_path"]) as z:
        packaged = z.read("repo/release/release-allowlist.json")
    on_disk = (synthetic_repo / "release/release-allowlist.json").read_bytes()
    assert packaged == on_disk
    assert common.sha256_bytes(packaged) == s["policy_sha256"]


def test_published_hash_and_size_equal_summary(builder, synthetic_repo, tmp_path, common):
    s = _build(builder, synthetic_repo, tmp_path / "out")
    data = Path(s["zip_path"]).read_bytes()
    assert common.sha256_bytes(data) == s["zip_sha256"]
    assert len(data) == s["zip_size_bytes"]


def test_verifier_runs_before_publication_failure_leaves_no_output(builder, synthetic_repo, tmp_path):
    out = tmp_path / "out"
    with mock.patch.object(builder._verifier, "verify_release_candidate",
                           return_value={"status": "FAIL", "findings": [], "not_verifiable": []}):
        with pytest.raises(builder.ReleaseError) as e:
            _build(builder, synthetic_repo, out)
    assert e.value.code == "verify_before_publish"
    assert not out.exists()
    assert not list(tmp_path.glob(".rc-stage-*"))


def test_pre_publication_not_verifiable_leaves_no_output(builder, synthetic_repo, tmp_path):
    out = tmp_path / "out"
    with mock.patch.object(builder._verifier, "verify_release_candidate",
                           return_value={"status": "NOT_VERIFIABLE", "findings": [], "not_verifiable": []}):
        with pytest.raises(builder.ReleaseError) as e:
            _build(builder, synthetic_repo, out)
    assert e.value.code == "verify_before_publish"
    assert not out.exists()


def test_post_publication_verification_failure_returns_failure(builder, synthetic_repo, tmp_path):
    out = tmp_path / "out"
    real = builder._verifier.verify_release_candidate
    state = {"n": 0}

    def flaky(zip_path):
        state["n"] += 1
        if state["n"] == 1:
            return real(zip_path)  # staging PASS
        return {"status": "FAIL", "findings": [], "not_verifiable": []}  # published FAIL

    with mock.patch.object(builder._verifier, "verify_release_candidate", side_effect=flaky):
        with pytest.raises(builder.ReleaseError) as e:
            _build(builder, synthetic_repo, out)
    assert e.value.code == "verify_before_publish"
    assert not out.exists()


def test_unsupported_hardlink_fails_closed(builder, synthetic_repo, tmp_path):
    out = tmp_path / "out"

    def unsupported(src, dst):
        raise builder.ReleaseError("hardlink_unsupported", "simulated cross-volume link")

    with mock.patch.object(builder, "hardlink_no_clobber", unsupported):
        with pytest.raises(builder.ReleaseError) as e:
            _build(builder, synthetic_repo, out)
    assert e.value.code == "hardlink_unsupported"
    assert not out.exists()


def test_hardlink_no_clobber_rejects_existing(common, tmp_path):
    src = tmp_path / "src.bin"; src.write_bytes(b"data")
    dst = tmp_path / "dst.bin"; dst.write_bytes(b"old")
    with pytest.raises(common.ReleaseError) as e:
        common.hardlink_no_clobber(src, dst)
    assert e.value.code == "destination_exists"
    assert dst.read_bytes() == b"old"


def test_no_osreplace_for_final_zip_in_source():
    src = (Path(__file__).resolve().parents[2] / "scripts" / "release" / "build_release_candidate.py").read_text()
    assert "os.replace" not in src


def test_existing_output_dir_rejected_and_preserved(builder, synthetic_repo, tmp_path):
    out = tmp_path / "out"; out.mkdir()
    sentinel = out / "keep.txt"; sentinel.write_text("preexisting\n", encoding="utf-8")
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, out)
    assert e.value.code == "output_reuse"
    assert sentinel.read_text(encoding="utf-8") == "preexisting\n"  # never deleted


def test_existing_final_zip_rejected(builder, synthetic_repo, tmp_path):
    out = tmp_path / "out"
    with pytest.raises(builder.ReleaseError):
        # output dir absent but pre-create the zip path scenario is covered by output_reuse
        _build(builder, synthetic_repo, out)
        (out / "release-candidate.zip").write_bytes(b"x")
        _build(builder, synthetic_repo, out)


def test_temp_files_removed_after_success(builder, synthetic_repo, tmp_path):
    _build(builder, synthetic_repo, tmp_path / "out")
    assert not list(tmp_path.glob(".rc-stage-*"))


def test_clean_tree_rechecked_after_snapshot(builder, synthetic_repo, tmp_path, monkeypatch, common):
    real_snapshot = builder.read_snapshot_bytes
    state = {"done": False}

    def mutating(path):
        data = real_snapshot(path)
        if not state["done"] and path.name == "README.md":
            state["done"] = True
            (synthetic_repo / "README.md").write_text("MUTATED DURING SNAPSHOT\n", encoding="utf-8")
        return data

    monkeypatch.setattr(builder, "read_snapshot_bytes", mutating)
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code == "source_changed"
    subprocess.run(["git", "-C", str(synthetic_repo), "checkout", "--", "README.md"], capture_output=True)


def test_mutation_size_change_fails_closed(common, tmp_path):
    p = tmp_path / "f.bin"; p.write_bytes(b"12345")
    real_stat = Path.stat

    def fake_stat(self, *a, **k):
        if self == p:
            class S:
                st_size = 999999
            return S()
        return real_stat(self, *a, **k)

    with mock.patch.object(Path, "stat", fake_stat):
        with pytest.raises(common.ReleaseError) as e:
            common.read_snapshot_bytes(p)
    assert e.value.code == "source_changed"


def test_dirty_tree_refused(builder, synthetic_repo, tmp_path):
    (synthetic_repo / "README.md").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code == "dirty_tree"


def test_tracked_jsonl_refused(builder, synthetic_repo, tmp_path, git):
    (synthetic_repo / "records.jsonl").write_text('{"x":1}\n', encoding="utf-8")
    git("add", "-f", "records.jsonl"); _commit(git, "jsonl")
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code == "tracked_jsonl"


def test_symlink_tracked_file_rejected(builder, synthetic_repo, tmp_path, git):
    real = synthetic_repo / "real.txt"; real.write_text("real\n", encoding="utf-8")
    link = synthetic_repo / "link.txt"
    try:
        os.symlink(real, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted on this host")
    git("add", "-A"); _commit(git, "symlink")
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code == "symlink_rejected"


# =========================================================================== #
# Phase F — strict verifier (repackage to inject defects)
# =========================================================================== #
@pytest.fixture()
def built_zip(builder, synthetic_repo, tmp_path):
    return Path(_build(builder, synthetic_repo, tmp_path / "out")["zip_path"])


def test_verify_complete_candidate_pass(verifier, built_zip):
    assert verifier.verify_release_candidate(built_zip)["status"] == "PASS"


@pytest.mark.parametrize("control", ["release-manifest.json", "SHA256SUMS.txt", "FILE_SIZES.json"])
def test_verify_missing_control_rejected(verifier, common, built_zip, tmp_path, control):
    dst = tmp_path / "m.zip"
    _repackage(common, built_zip, dst, lambda it: it.pop(control))
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "missing_control_file" for f in r["findings"])


def test_verify_missing_manifest_schema_version_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        m = json.loads(it["release-manifest.json"]); del m["schema_version"]
        it["release-manifest.json"] = (json.dumps(m) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "schema_missing_field" for f in r["findings"])


@pytest.mark.parametrize("obj_key", ["repository", "policy", "counts"])
def test_verify_missing_manifest_object_fail(verifier, common, built_zip, tmp_path, obj_key):
    def mut(it):
        m = json.loads(it["release-manifest.json"]); del m[obj_key]
        it["release-manifest.json"] = (json.dumps(m) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "schema_missing_field" for f in r["findings"])


def test_verify_unexpected_manifest_field_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        m = json.loads(it["release-manifest.json"]); m["surprise"] = 1
        it["release-manifest.json"] = (json.dumps(m) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "schema_unexpected_field" for f in r["findings"])


@pytest.mark.parametrize("drop", ["path", "sha256", "size_bytes", "classification"])
def test_verify_payload_entry_missing_field_fail(verifier, common, built_zip, tmp_path, drop):
    def mut(it):
        m = json.loads(it["release-manifest.json"]); del m["files"][0][drop]
        it["release-manifest.json"] = (json.dumps(m) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] in {"schema_missing_field", "schema_unexpected_field"}
                                         for f in r["findings"])


def test_verify_boolean_used_as_size_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        m = json.loads(it["release-manifest.json"]); m["files"][0]["size_bytes"] = True
        it["release-manifest.json"] = (json.dumps(m) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "schema_type" for f in r["findings"])


def test_verify_negative_size_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        m = json.loads(it["release-manifest.json"]); m["files"][0]["size_bytes"] = -1
        it["release-manifest.json"] = (json.dumps(m) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "schema_type" for f in r["findings"])


def test_verify_malformed_sha_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        m = json.loads(it["release-manifest.json"]); m["files"][0]["sha256"] = "xyz"
        it["release-manifest.json"] = (json.dumps(m) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "schema_type" for f in r["findings"])


def test_verify_malformed_json_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        it["release-manifest.json"] = b"{ not json"
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "malformed_json" for f in r["findings"])


def test_verify_duplicate_json_key_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        it["release-manifest.json"] = b'{"schema_version":3,"schema_version":3}'
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "duplicate_json_key" for f in r["findings"])


def test_verify_malformed_zip_fail(verifier, tmp_path):
    bad = tmp_path / "bad.zip"; bad.write_bytes(b"this is not a zip file")
    r = verifier.verify_release_candidate(bad)
    assert r["status"] == "FAIL" and r["passed"] is False


def test_verify_duplicate_zip_entry_fail(verifier, built_zip, tmp_path):
    dst = tmp_path / "dup.zip"
    with zipfile.ZipFile(built_zip) as z:
        items = [(i.filename, z.read(i.filename)) for i in z.infolist()]
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # intentional duplicate entry
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
            for name, data in items:
                z.writestr(name, data)
            z.writestr(items[0][0], items[0][1])  # duplicate
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "zip_duplicate" for f in r["findings"])


def test_verify_nondeterministic_metadata_fail(verifier, built_zip, tmp_path):
    dst = tmp_path / "nd.zip"
    with zipfile.ZipFile(built_zip) as z:
        items = {i.filename: z.read(i.filename) for i in z.infolist()}
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:  # default (non-fixed) metadata
        for name in sorted(items):
            z.writestr(name, items[name])
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "nondeterministic_metadata" for f in r["findings"])


def test_verify_malformed_checksum_spacing_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        lines = it["SHA256SUMS.txt"].decode().splitlines()
        lines[0] = lines[0].replace("  ", " ", 1)
        it["SHA256SUMS.txt"] = ("\n".join(lines) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "checksums_format" for f in r["findings"])


def test_verify_duplicate_checksum_path_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        lines = it["SHA256SUMS.txt"].decode().splitlines()
        it["SHA256SUMS.txt"] = ("\n".join(lines + [lines[0]]) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "checksums_duplicate" for f in r["findings"])


def test_verify_omitted_checksum_path_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        lines = it["SHA256SUMS.txt"].decode().splitlines()
        it["SHA256SUMS.txt"] = ("\n".join(lines[1:]) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "checksums_set_mismatch" for f in r["findings"])


def test_verify_extra_checksum_path_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        it["SHA256SUMS.txt"] += (("0" * 64) + "  repo/ghost.txt\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "checksums_set_mismatch" for f in r["findings"])


def test_verify_omitted_size_path_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        sizes = json.loads(it["FILE_SIZES.json"])
        sizes["files"].pop(next(iter(sizes["files"])))
        it["FILE_SIZES.json"] = (json.dumps(sizes) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "sizes_set_mismatch" for f in r["findings"])


def test_verify_extra_size_path_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        sizes = json.loads(it["FILE_SIZES.json"])
        sizes["files"]["repo/ghost.txt"] = 5
        it["FILE_SIZES.json"] = (json.dumps(sizes) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "sizes_set_mismatch" for f in r["findings"])


def test_verify_manifest_checksum_mismatch_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        it["repo/README.md"] = b"TAMPERED\n"
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL"
    assert any(f["code"] in {"changed_file", "manifest_payload_mismatch",
                             "sizes_set_mismatch", "checksums_set_mismatch"} for f in r["findings"])


def test_verify_manifest_size_mismatch_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        m = json.loads(it["release-manifest.json"])
        m["files"][0]["size_bytes"] = m["files"][0]["size_bytes"] + 10
        it["release-manifest.json"] = (json.dumps(m) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL"


def test_verify_unexpected_control_entry_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        it["EXTRA_CONTROL.txt"] = b"nope\n"
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "unexpected_entry" for f in r["findings"])


def test_verify_unexpected_payload_entry_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        it["repo/surprise.txt"] = b"extra\n"
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL"
    assert any(f["code"] in {"manifest_payload_mismatch", "sizes_set_mismatch", "checksums_set_mismatch",
                             "unclassified_tracked_path"} for f in r["findings"])


def test_verify_jsonl_entry_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        it["repo/records.jsonl"] = b'{"x":1}\n'
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL"
    assert any(f["code"] in {"jsonl_present", "prohibited_artifact", "manifest_payload_mismatch",
                             "sizes_set_mismatch", "checksums_set_mismatch"} for f in r["findings"])


def test_verify_policy_identity_mismatch_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        m = json.loads(it["release-manifest.json"])
        m["policy"]["sha256"] = "a" * 64
        it["release-manifest.json"] = (json.dumps(m) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL"
    # either the tampered manifest sha fails set/hash checks or the policy identity check
    assert any(f["code"] in {"policy_identity_mismatch", "changed_file",
                             "manifest_payload_mismatch"} for f in r["findings"])


def test_verify_malformed_candidate_structured_not_traceback(verifier, common, built_zip, tmp_path):
    def mut(it):
        it["release-manifest.json"] = b'{"schema_version": 3, "files": "not-a-list"}'
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)  # must not raise
    assert r["status"] == "FAIL" and r["passed"] is False


def test_verify_not_verifiable_is_not_pass(verifier, common, tmp_path):
    manifest = {
        "schema_version": 3,
        "repository": {"head": "a" * 40, "branch": "b", "base_sha": None},
        "policy": {"policy_id": "x", "schema_version": 3, "sha256": "c" * 64},
        "counts": {"file_count": 0, "tracked_count": 0, "generated_count": 0},
        "control_coverage": {"manifest_files": "x", "sizes_covers": "y", "checksums_covers": "z"},
        "content_controls": {"jsonl_included": False, "result_json_included": False,
                             "credentials_included": False, "databases_included": False,
                             "git_metadata_included": False, "venv_included": False, "built_from": "x"},
        "zip_policy": {"entry_order": "lexical", "timestamp": "t", "permissions": "0644", "compression": "deflate-9"},
        "files": [],
    }
    mbytes = (json.dumps(manifest) + "\n").encode()
    files = {"release-manifest.json": mbytes}
    files["FILE_SIZES.json"] = (json.dumps({"schema_version": 1, "files": {
        "release-manifest.json": len(mbytes)}}) + "\n").encode()
    files["SHA256SUMS.txt"] = common.checksum_text(files)
    z = tmp_path / "empty.zip"
    z.write_bytes(common.deterministic_zip_bytes(files))
    r = verifier.verify_release_candidate(z)
    assert r["status"] == "NOT_VERIFIABLE" and r["passed"] is False


def test_verify_does_not_modify_zip(verifier, built_zip):
    before = built_zip.read_bytes()
    verifier.verify_release_candidate(built_zip)
    assert built_zip.read_bytes() == before
