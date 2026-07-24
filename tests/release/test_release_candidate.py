"""Phase 12G disjoint closed-world policy + snapshot-bound archive inspection +
complete verifier semantics tests. Synthetic fixtures only; no real records or
the real tracked archive. Exercises production builder/verifier/policy code.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import unittest.mock as mock
import warnings
import zipfile
from pathlib import Path, PurePosixPath

import pytest

from conftest import (make_bzip2_zip, make_encrypted_zip, make_zip, valid_policy_obj, write_policy)


def _build(builder, repo, out, **kw):
    return builder.build_release_candidate(repo_root=repo, output_dir=out, **kw)


def _commit(git, msg="change"):
    git("add", "-A"); git("commit", "-q", "-m", msg)


def _repackage(common, zip_src: Path, zip_dst: Path, mutate):
    with zipfile.ZipFile(zip_src) as z:
        items = {i.filename: z.read(i.filename) for i in z.infolist()}
    mutate(items)
    zip_dst.write_bytes(common.deterministic_zip_bytes(items))


def _manifest_of(zip_path: Path) -> dict:
    with zipfile.ZipFile(zip_path) as z:
        return json.loads(z.read("release-manifest.json"))


def _add_allowed_archive(repo: Path, git, members: dict, *, path="bundle.zip"):
    (repo / path).write_bytes(make_zip(members))
    obj = valid_policy_obj(["release/release-allowlist.json", "release/release-policy.md"],
                           allowed_archives=[{"path": path}])
    write_policy(repo, obj)
    git("add", "-f", path); git("add", "-A"); git("commit", "-q", "-m", "add archive")


# =========================================================================== #
# Baseline
# =========================================================================== #
def test_clean_build_and_verify_pass(builder, verifier, synthetic_repo, tmp_path):
    s = _build(builder, synthetic_repo, tmp_path / "out")
    assert s["ok"] is True and s["policy_id"] == "phase12g-test-policy-v4"
    assert s["verified_before_publish"] and s["published_atomically"]
    assert s["classification_summary"]["unclassified"] == 0
    assert s["classification_summary"]["ambiguous"] == 0
    assert s["classification_summary"]["overlap"] == 0
    r = verifier.verify_release_candidate(Path(s["zip_path"]))
    assert r["status"] == "PASS", r


def test_changed_policy_changes_release_identity(builder, synthetic_repo, tmp_path, git):
    a = _build(builder, synthetic_repo, tmp_path / "a")["zip_sha256"]
    obj = valid_policy_obj(["release/release-allowlist.json", "release/release-policy.md"],
                           extra_extensions=[".cfg"])
    write_policy(synthetic_repo, obj); _commit(git, "policy tweak")
    b = _build(builder, synthetic_repo, tmp_path / "b")["zip_sha256"]
    assert a != b


# =========================================================================== #
# Phase D — disjoint policy
# =========================================================================== #
def test_every_tracked_path_has_exactly_one_permitted_rule(common, synthetic_repo):
    pol = common.parse_release_policy((synthetic_repo / "release/release-allowlist.json").read_bytes())
    tracked = [x for x in subprocess.run(["git", "-C", str(synthetic_repo), "ls-files", "-z"],
                                         capture_output=True, text=True).stdout.split("\0") if x]
    for rel in tracked:
        pure = PurePosixPath(rel); name_cf = pure.name.casefold(); suf = pure.suffix.casefold()
        matches = [r.rule_id for r in pol.inclusion_rules
                   if common._rule_effective_matches(r, rel, name_cf, suf)]
        assert len(matches) == 1, (rel, matches)


def test_required_exact_path_not_matched_by_extension_rule(common, synthetic_repo):
    pol = common.parse_release_policy((synthetic_repo / "release/release-allowlist.json").read_bytes())
    rel = "release/release-policy.md"
    pure = PurePosixPath(rel)
    matches = [r.rule_id for r in pol.inclusion_rules
               if common._rule_effective_matches(r, rel, pure.name.casefold(), pure.suffix.casefold())]
    assert matches == ["req-0"] or (len(matches) == 1 and matches[0].startswith("req"))
    res = common.classify_path(rel, pol)
    assert res.classification == common.CLASS_REQUIRED


def test_two_permitted_rules_matching_one_path_fail(common):
    # An extension rule WITHOUT the required-path exclusion structurally overlaps.
    obj = valid_policy_obj(["release/release-policy.md"])
    for r in obj["inclusion_rules"]:
        if r["rule_id"] == "allow-ext-md":
            r["exclude_exact_paths"] = []  # remove exclusion -> overlap with req path
    with pytest.raises(common.ReleaseError) as e:
        common.parse_release_policy(json.dumps(obj).encode())
    assert e.value.code == "ambiguous_policy_classification"


def test_allowed_allowed_overlap_fails(common):
    obj = valid_policy_obj(["release/release-allowlist.json"],
                           extra_rules=[{"rule_id": "dup-md", "class": "ALLOWED",
                                         "form": "extension", "value": ".md", "exclude_exact_paths": []}])
    with pytest.raises(common.ReleaseError) as e:
        common.parse_release_policy(json.dumps(obj).encode())
    assert e.value.code == "policy_conflict"


def test_inclusion_prohibited_overlap_fails(common):
    obj = valid_policy_obj(["release/release-allowlist.json"],
                           extra_rules=[{"rule_id": "allow-pem", "class": "ALLOWED",
                                         "form": "extension", "value": ".pem", "exclude_exact_paths": []}])
    with pytest.raises(common.ReleaseError) as e:
        common.parse_release_policy(json.dumps(obj).encode())
    assert e.value.code == "ambiguous_policy_classification"


def test_rule_ordering_does_not_change_classification(common):
    obj = valid_policy_obj(["release/release-allowlist.json", "release/release-policy.md"])
    pol1 = common.parse_release_policy(json.dumps(obj).encode())
    obj2 = json.loads(json.dumps(obj))
    obj2["inclusion_rules"] = list(reversed(obj2["inclusion_rules"]))
    pol2 = common.parse_release_policy(json.dumps(obj2).encode())
    for rel in ["release/release-policy.md", "src/app.py", "README.md"]:
        assert common.classify_path(rel, pol1).classification == common.classify_path(rel, pol2).classification


def test_duplicate_rule_id_fails(common):
    obj = valid_policy_obj(["release/release-allowlist.json"])
    obj["inclusion_rules"].append({"rule_id": "req-0", "class": "ALLOWED", "form": "extension",
                                   "value": ".cfg", "exclude_exact_paths": []})
    with pytest.raises(common.ReleaseError) as e:
        common.parse_release_policy(json.dumps(obj).encode())
    assert e.value.code == "policy_conflict"


def test_duplicate_effective_rule_fails(common):
    obj = valid_policy_obj(["release/release-allowlist.json"])
    obj["inclusion_rules"].append({"rule_id": "extra-txt", "class": "ALLOWED", "form": "extension",
                                   "value": ".txt", "exclude_exact_paths": []})
    with pytest.raises(common.ReleaseError) as e:
        common.parse_release_policy(json.dumps(obj).encode())
    assert e.value.code in {"policy_conflict", "ambiguous_policy_classification"}


def test_unsupported_rule_syntax_fails(common):
    obj = valid_policy_obj(["release/release-allowlist.json"],
                           extra_rules=[{"rule_id": "bad", "class": "ALLOWED", "form": "extension",
                                         "value": "*.md", "exclude_exact_paths": []}])
    with pytest.raises(common.ReleaseError) as e:
        common.parse_release_policy(json.dumps(obj).encode())
    assert e.value.code == "policy_pattern"


def test_unknown_optional_generated_key_rejected(common):
    obj = valid_policy_obj(["release/release-allowlist.json"])
    obj["optional_generated"]["surprise"] = 1
    with pytest.raises(common.ReleaseError) as e:
        common.parse_release_policy(json.dumps(obj).encode())
    assert e.value.code == "policy_schema"


def test_missing_env_allow_exceptions_rejected(common):
    obj = valid_policy_obj(["release/release-allowlist.json"])
    del obj["prohibited"]["env"]["allow_exceptions"]
    with pytest.raises(common.ReleaseError) as e:
        common.parse_release_policy(json.dumps(obj).encode())
    assert e.value.code == "policy_schema"


def test_float_schema_version_rejected(common):
    obj = valid_policy_obj(["release/release-allowlist.json"])
    obj["schema_version"] = 4.0
    with pytest.raises(common.ReleaseError) as e:
        common.parse_release_policy(json.dumps(obj).encode())
    assert e.value.code == "policy_schema"


def test_unclassified_root_file_fails(builder, synthetic_repo, tmp_path, git):
    (synthetic_repo / "mystery.xyz").write_text("data\n", encoding="utf-8")
    _commit(git)
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code in {"unclassified_tracked_path", "tracked_unclassified"}


def test_unclassified_nested_file_fails(builder, synthetic_repo, tmp_path, git):
    (synthetic_repo / "src" / "data.bin").write_bytes(b"\x00\x01")
    _commit(git)
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code in {"unclassified_tracked_path", "tracked_unclassified"}


def test_safe_looking_unknown_file_fails(builder, synthetic_repo, tmp_path, git):
    (synthetic_repo / "config.ini").write_text("[a]\n", encoding="utf-8")
    _commit(git)
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code in {"unclassified_tracked_path", "tracked_unclassified"}


def test_prohibited_tracked_file_fails(builder, synthetic_repo, tmp_path, git):
    (synthetic_repo / "server.pem").write_text("k\n", encoding="utf-8")
    git("add", "-f", "server.pem"); _commit(git)
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert e.value.code in {"tracked_path_prohibited", "tracked_prohibited"}


def test_changed_policy_changes_identity_and_records_rule_id(builder, synthetic_repo, tmp_path):
    s = _build(builder, synthetic_repo, tmp_path / "out")
    manifest = _manifest_of(Path(s["zip_path"]))
    by_path = {f["path"]: f for f in manifest["files"]}
    assert by_path["release/release-allowlist.json"]["rule_id"].startswith("req")
    assert by_path["release/release-allowlist.json"]["classification"] == "REQUIRED"
    assert by_path["src/app.py"]["rule_id"] == "allow-ext-py"


def test_cli_generated_cannot_broaden_policy(builder, synthetic_repo, tmp_path):
    (synthetic_repo / "extra.db").write_bytes(b"x")
    gen = tmp_path / "gen.json"
    gen.write_text(json.dumps({"schema_version": 1, "files": [
        {"path": "extra.db", "sha256": "0" * 64, "size_bytes": 1}]}), encoding="utf-8")
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out", generated_allowlist=gen)
    assert e.value.code in {"tracked_path_prohibited", "prohibited_policy_overlap"}


def test_verifier_recomputes_rule_id(verifier, common, synthetic_repo, tmp_path, builder):
    s = _build(builder, synthetic_repo, tmp_path / "out")
    dst = tmp_path / "z.zip"

    def mut(it):
        m = json.loads(it["release-manifest.json"])
        for f in m["files"]:
            if f["path"] == "src/app.py":
                f["rule_id"] = "allow-ext-md"  # wrong rule id
        it["release-manifest.json"] = (json.dumps(m) + "\n").encode()
    _repackage(common, Path(s["zip_path"]), dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "classification_mismatch" for f in r["findings"])


# =========================================================================== #
# Phase G — snapshot-bound archive inspection + resource limits
# =========================================================================== #
def test_builder_verifier_share_archive_helper(builder, verifier, common):
    assert builder.inspect_archive_bytes is common.inspect_archive_bytes
    assert verifier.rc.inspect_archive_bytes is common.inspect_archive_bytes


def test_allowed_archive_safe_names_passes(builder, verifier, synthetic_repo, tmp_path, git):
    _add_allowed_archive(synthetic_repo, git, {"fig/a.tex": b"x", "b.bib": b"y"})
    s = _build(builder, synthetic_repo, tmp_path / "out")
    manifest = _manifest_of(Path(s["zip_path"]))
    arc = [f for f in manifest["files"] if f["path"] == "bundle.zip"][0]
    assert arc["classification"] == "ALLOWED_ARCHIVE"
    assert arc["archive_inspection"]["result"] == "SAFE"
    assert arc["archive_inspection"]["payload_sha256"] == arc["sha256"]
    assert verifier.verify_release_candidate(Path(s["zip_path"]))["status"] == "PASS"


def test_archive_inspection_bound_to_packaged_bytes(builder, synthetic_repo, tmp_path, git, common):
    _add_allowed_archive(synthetic_repo, git, {"fig/a.tex": b"x", "b.bib": b"y"})
    s = _build(builder, synthetic_repo, tmp_path / "out")
    with zipfile.ZipFile(s["zip_path"]) as z:
        arc_bytes = z.read("repo/bundle.zip")
    manifest = _manifest_of(Path(s["zip_path"]))
    arc = [f for f in manifest["files"] if f["path"] == "bundle.zip"][0]
    assert common.sha256_bytes(arc_bytes) == arc["sha256"] == arc["archive_inspection"]["payload_sha256"]


def test_archive_scan_uses_snapshot_not_second_read(builder, synthetic_repo, tmp_path, git, common):
    _add_allowed_archive(synthetic_repo, git, {"only/one.tex": b"z"})
    crafted = make_zip({"a.tex": b"1", "b.bib": b"2", "c.sty": b"3"})
    real = builder.read_snapshot_bytes

    def patched(path):
        if path.name == "bundle.zip":
            return crafted
        return real(path)

    with mock.patch.object(builder, "read_snapshot_bytes", patched):
        # snapshot returns crafted bytes -> inspection + hash must both use crafted bytes
        s = _build(builder, synthetic_repo, tmp_path / "out")
    manifest = _manifest_of(Path(s["zip_path"]))
    arc = [f for f in manifest["files"] if f["path"] == "bundle.zip"][0]
    assert arc["sha256"] == common.sha256_bytes(crafted)
    assert arc["archive_inspection"]["entry_count"] == 3
    assert arc["archive_inspection"]["payload_sha256"] == common.sha256_bytes(crafted)


def test_verifier_reinspects_archive_metadata(builder, verifier, common, synthetic_repo, tmp_path, git):
    _add_allowed_archive(synthetic_repo, git, {"a.tex": b"1", "b.bib": b"2"})
    s = _build(builder, synthetic_repo, tmp_path / "out")
    dst = tmp_path / "z.zip"

    def mut(it):
        m = json.loads(it["release-manifest.json"])
        for f in m["files"]:
            if f["path"] == "bundle.zip":
                f["archive_inspection"]["entry_count"] = 99  # lie about the scan result
        it["release-manifest.json"] = (json.dumps(m) + "\n").encode()
    _repackage(common, Path(s["zip_path"]), dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "archive_scan_mismatch" for f in r["findings"])


def test_archive_binding_mismatch_direct(common, synthetic_repo):
    pol = common.parse_release_policy((synthetic_repo / "release/release-allowlist.json").read_bytes())
    data = make_zip({"a.tex": b"x"})
    with pytest.raises(common.ReleaseError) as e:
        common.inspect_archive_bytes(data, pol, rule_id="r", payload_sha="0" * 64, payload_size=len(data))
    assert e.value.code == "archive_binding_mismatch"


def _inspect(common, pol, data):
    return common.inspect_archive_bytes(data, pol, rule_id="r",
                                        payload_sha=common.sha256_bytes(data), payload_size=len(data))


@pytest.fixture()
def apol(common, synthetic_repo):
    return common.parse_release_policy((synthetic_repo / "release/release-allowlist.json").read_bytes())


def test_archive_excessive_entry_count_fails(common, apol, monkeypatch):
    monkeypatch.setattr(common, "MAX_ARCHIVE_ENTRIES", 2)
    data = make_zip({"a.tex": b"1", "b.tex": b"2", "c.tex": b"3"})
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, data)
    assert e.value.code == "archive_too_many_entries"


def test_archive_excessive_total_name_bytes_fails(common, apol, monkeypatch):
    monkeypatch.setattr(common, "MAX_TOTAL_NAME_BYTES", 10)
    data = make_zip({"aaaaa.tex": b"1", "bbbbb.tex": b"2"})
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, data)
    assert e.value.code == "archive_total_names_too_long"


def test_archive_excessive_name_length_fails(common, apol, monkeypatch):
    monkeypatch.setattr(common, "MAX_ENTRY_NAME_BYTES", 5)
    data = make_zip({"toolongname.tex": b"1"})
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, data)
    assert e.value.code == "archive_name_too_long"


def test_archive_excessive_nesting_fails(common, apol, monkeypatch):
    monkeypatch.setattr(common, "MAX_ARCHIVE_DEPTH", 2)
    data = make_zip({"a/b/c/d.tex": b"1"})
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, data)
    assert e.value.code == "archive_depth"


def test_archive_duplicate_nested_names_fail(common, apol):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("a.tex", b"1")
            z.writestr("a.tex", b"2")
        data = buf.getvalue()
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, data)
    assert e.value.code == "archive_duplicate_name"


def test_archive_case_colliding_names_fail(common, apol):
    data = make_zip({"A.tex": b"1", "a.tex": b"2"})
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, data)
    assert e.value.code == "archive_case_collision"


def test_archive_absolute_nested_path_fails(common, apol):
    data = make_zip({"/etc/passwd.tex": b"1"})
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, data)
    assert e.value.code in {"archive_absolute", "archive_traversal"}


def test_archive_traversal_nested_path_fails(common, apol):
    data = make_zip({"../evil.tex": b"1"})
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, data)
    assert e.value.code == "archive_traversal"


def test_archive_drive_nested_path_fails(common, apol):
    data = make_zip({"C:/evil.tex": b"1"})
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, data)
    assert e.value.code in {"archive_drive", "archive_backslash"}


def test_archive_control_char_name_fails(common, apol):
    data = make_zip({"bad\x01name.tex": b"1"})
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, data)
    assert e.value.code == "archive_control_char"


def test_archive_prohibited_nested_name_fails(common, apol):
    data = make_zip({"inner/records.jsonl": b"1", "ok.tex": b"2"})
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, data)
    assert e.value.code == "archive_prohibited_nested"


def test_archive_nested_archive_fails(common, apol):
    data = make_zip({"inner/child.zip": b"1"})
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, data)
    assert e.value.code == "archive_nested_archive"


def test_archive_encrypted_entry_fails(common, apol):
    data = make_encrypted_zip("a.tex", b"secret")
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, data)
    assert e.value.code == "archive_encrypted"


def test_archive_unsupported_compression_fails(common, apol):
    try:
        data = make_bzip2_zip({"a.tex": b"payload" * 50})
    except Exception:
        pytest.skip("bz2 compression not available")
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, data)
    assert e.value.code == "archive_unsupported_compression"


def test_archive_malformed_structured_fail(common, apol):
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, b"this is not a zip")
    assert e.value.code == "archive_malformed"


def test_archive_no_nested_content_extracted(common, apol, tmp_path):
    before = set(tmp_path.rglob("*"))
    _inspect(common, apol, make_zip({"a.tex": b"content-should-not-be-extracted"}))
    assert set(tmp_path.rglob("*")) == before


# =========================================================================== #
# Phase H/J — snapshot + publication (retained) + verifier semantics
# =========================================================================== #
def test_zip_bytes_are_the_hashed_bytes(builder, synthetic_repo, tmp_path):
    import hashlib
    s = _build(builder, synthetic_repo, tmp_path / "out")
    with zipfile.ZipFile(s["zip_path"]) as z:
        for item in _manifest_of(Path(s["zip_path"]))["files"]:
            data = z.read(item["archive_path"])
            assert hashlib.sha256(data).hexdigest() == item["sha256"]
            assert len(data) == item["size_bytes"]


def test_arbitrary_binary_bytes_preserved(builder, synthetic_repo, tmp_path, git):
    raw = bytes(range(256)) * 8
    (synthetic_repo / "docs").mkdir()
    (synthetic_repo / "docs" / "figure.png").write_bytes(raw)
    obj = valid_policy_obj(["release/release-allowlist.json", "release/release-policy.md"],
                           extra_extensions=[".png"])
    write_policy(synthetic_repo, obj)
    git("add", "-f", "docs/figure.png"); _commit(git, "png")
    s = _build(builder, synthetic_repo, tmp_path / "out")
    with zipfile.ZipFile(s["zip_path"]) as z:
        assert z.read("repo/docs/figure.png") == raw


def test_policy_single_read_bytes_match_package(builder, synthetic_repo, tmp_path, common):
    s = _build(builder, synthetic_repo, tmp_path / "out")
    with zipfile.ZipFile(s["zip_path"]) as z:
        packaged = z.read("repo/release/release-allowlist.json")
    assert packaged == (synthetic_repo / "release/release-allowlist.json").read_bytes()
    assert common.sha256_bytes(packaged) == s["policy_sha256"]


def test_verifier_runs_before_publication_failure_leaves_no_output(builder, synthetic_repo, tmp_path):
    out = tmp_path / "out"
    with mock.patch.object(builder._verifier, "verify_release_candidate",
                           return_value={"status": "FAIL", "findings": [], "not_verifiable": []}):
        with pytest.raises(builder.ReleaseError) as e:
            _build(builder, synthetic_repo, out)
    assert e.value.code == "verify_before_publish"
    assert not out.exists() and not list(tmp_path.glob(".rc-stage-*"))


def test_pre_publication_not_verifiable_leaves_no_output(builder, synthetic_repo, tmp_path):
    out = tmp_path / "out"
    with mock.patch.object(builder._verifier, "verify_release_candidate",
                           return_value={"status": "NOT_VERIFIABLE", "findings": [], "not_verifiable": []}):
        with pytest.raises(builder.ReleaseError):
            _build(builder, synthetic_repo, out)
    assert not out.exists()


def test_post_publication_verification_failure_returns_failure(builder, synthetic_repo, tmp_path):
    out = tmp_path / "out"
    real = builder._verifier.verify_release_candidate
    state = {"n": 0}

    def flaky(zip_path, **kw):
        state["n"] += 1
        return real(zip_path, **kw) if state["n"] == 1 else {"status": "FAIL", "findings": [], "not_verifiable": []}

    with mock.patch.object(builder._verifier, "verify_release_candidate", side_effect=flaky):
        with pytest.raises(builder.ReleaseError) as e:
            _build(builder, synthetic_repo, out)
    assert e.value.code == "verify_before_publish" and not out.exists()


def test_unsupported_hardlink_fails_closed(builder, synthetic_repo, tmp_path):
    out = tmp_path / "out"

    def unsupported(src, dst):
        raise builder.ReleaseError("hardlink_unsupported", "simulated cross-volume")

    with mock.patch.object(builder, "hardlink_no_clobber", unsupported):
        with pytest.raises(builder.ReleaseError) as e:
            _build(builder, synthetic_repo, out)
    assert e.value.code == "hardlink_unsupported" and not out.exists()


def test_publication_race_at_hardlink_seam(builder, synthetic_repo, tmp_path):
    out = tmp_path / "out"
    real = builder.hardlink_no_clobber

    def racing(src, dst):
        Path(dst).write_bytes(b"racer")  # a concurrent writer wins the seam
        return real(src, dst)

    with mock.patch.object(builder, "hardlink_no_clobber", racing):
        with pytest.raises(builder.ReleaseError) as e:
            _build(builder, synthetic_repo, out)
    assert e.value.code == "destination_exists"


def test_no_osreplace_for_final_zip_in_source():
    src = (Path(__file__).resolve().parents[2] / "scripts" / "release" / "build_release_candidate.py").read_text()
    assert "os.replace" not in src


def test_existing_output_dir_rejected_and_preserved(builder, synthetic_repo, tmp_path):
    out = tmp_path / "out"; out.mkdir()
    sentinel = out / "keep.txt"; sentinel.write_text("preexisting\n", encoding="utf-8")
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, out)
    assert e.value.code == "output_reuse"
    assert sentinel.read_text(encoding="utf-8") == "preexisting\n"


def test_temp_files_removed_after_success(builder, synthetic_repo, tmp_path):
    _build(builder, synthetic_repo, tmp_path / "out")
    assert not list(tmp_path.glob(".rc-stage-*"))


def test_clean_tree_rechecked_after_snapshot(builder, synthetic_repo, tmp_path, monkeypatch):
    real_snapshot = builder.read_snapshot_bytes
    state = {"done": False}

    def mutating(path):
        data = real_snapshot(path)
        if not state["done"] and path.name == "README.md":
            state["done"] = True
            (synthetic_repo / "README.md").write_text("MUTATED\n", encoding="utf-8")
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
# Phase J — strict verifier (repackage to inject defects)
# =========================================================================== #
@pytest.fixture()
def built_zip(builder, synthetic_repo, tmp_path):
    return Path(_build(builder, synthetic_repo, tmp_path / "out")["zip_path"])


def test_verify_complete_candidate_pass(verifier, built_zip):
    r = verifier.verify_release_candidate(built_zip)
    assert r["status"] == "PASS" and r["policy_trust"] == "candidate_anchored"


def test_verify_expected_policy_anchor(verifier, common, built_zip):
    manifest = _manifest_of(built_zip)
    r = verifier.verify_release_candidate(built_zip, expected_policy_sha256=manifest["policy"]["sha256"],
                                          expected_policy_id=manifest["policy"]["policy_id"])
    assert r["status"] == "PASS" and r["policy_trust"] == "expected_anchored"


def test_verify_untrusted_policy_fails(verifier, built_zip):
    r = verifier.verify_release_candidate(built_zip, expected_policy_sha256="a" * 64)
    assert r["status"] == "FAIL" and any(f["code"] == "policy_untrusted" for f in r["findings"])


@pytest.mark.parametrize("control", ["release-manifest.json", "SHA256SUMS.txt", "FILE_SIZES.json"])
def test_verify_missing_control_rejected(verifier, common, built_zip, tmp_path, control):
    dst = tmp_path / "m.zip"
    _repackage(common, built_zip, dst, lambda it: it.pop(control))
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "missing_control_file" for f in r["findings"])


@pytest.mark.parametrize("obj_key", ["builder", "repository", "policy", "counts", "zip_policy"])
def test_verify_missing_manifest_object_fail(verifier, common, built_zip, tmp_path, obj_key):
    def mut(it):
        m = json.loads(it["release-manifest.json"]); del m[obj_key]
        it["release-manifest.json"] = (json.dumps(m) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "schema_missing_field" for f in r["findings"])


def test_verify_unexpected_nested_field_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        m = json.loads(it["release-manifest.json"]); m["repository"]["surprise"] = 1
        it["release-manifest.json"] = (json.dumps(m) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "schema_unexpected_field" for f in r["findings"])


def test_verify_noncanonical_zip_policy_value_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        m = json.loads(it["release-manifest.json"]); m["zip_policy"]["permissions"] = "0777"
        it["release-manifest.json"] = (json.dumps(m) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "schema_value" for f in r["findings"])


def test_verify_payload_count_mismatch_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        m = json.loads(it["release-manifest.json"]); m["counts"]["payload_count"] += 1
        it["release-manifest.json"] = (json.dumps(m) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "counts_mismatch" for f in r["findings"])


def test_verify_entry_count_mismatch_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        m = json.loads(it["release-manifest.json"]); m["counts"]["entry_count"] += 5
        it["release-manifest.json"] = (json.dumps(m) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "counts_mismatch" for f in r["findings"])


def test_verify_generated_semantic_mismatch_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        m = json.loads(it["release-manifest.json"])
        m["files"][0]["source"] = "generated"  # but classification stays REQUIRED/ALLOWED
        it["release-manifest.json"] = (json.dumps(m) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL"


def test_verify_archive_metadata_on_non_archive_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        m = json.loads(it["release-manifest.json"])
        m["files"][0]["archive_inspection"] = {"format": "zip", "entry_count": 1, "total_name_bytes": 1,
                                               "max_name_bytes": 1, "max_depth": 1, "comment_length": 0,
                                               "payload_sha256": m["files"][0]["sha256"],
                                               "payload_size": m["files"][0]["size_bytes"],
                                               "rule_id": m["files"][0]["rule_id"], "limits_version": 1,
                                               "result": "SAFE"}
        it["release-manifest.json"] = (json.dumps(m) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "manifest_schema" for f in r["findings"])


def test_verify_boolean_used_as_size_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        m = json.loads(it["release-manifest.json"]); m["files"][0]["size_bytes"] = True
        it["release-manifest.json"] = (json.dumps(m) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "schema_type" for f in r["findings"])


def test_verify_invalid_enum_value_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        m = json.loads(it["release-manifest.json"]); m["files"][0]["classification"] = "WEIRD"
        it["release-manifest.json"] = (json.dumps(m) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "manifest_schema" for f in r["findings"])


def test_verify_malformed_json_fail(verifier, common, built_zip, tmp_path):
    dst = tmp_path / "z.zip"
    _repackage(common, built_zip, dst, lambda it: it.__setitem__("release-manifest.json", b"{ nope"))
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "malformed_json" for f in r["findings"])


def test_verify_duplicate_json_key_fail(verifier, common, built_zip, tmp_path):
    dst = tmp_path / "z.zip"
    _repackage(common, built_zip, dst,
               lambda it: it.__setitem__("release-manifest.json", b'{"schema_version":4,"schema_version":4}'))
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "duplicate_json_key" for f in r["findings"])


def test_verify_malformed_zip_fail(verifier, tmp_path):
    bad = tmp_path / "bad.zip"; bad.write_bytes(b"not a zip")
    r = verifier.verify_release_candidate(bad)
    assert r["status"] == "FAIL" and r["passed"] is False


def test_verify_duplicate_zip_entry_fail(verifier, built_zip, tmp_path):
    dst = tmp_path / "dup.zip"
    with zipfile.ZipFile(built_zip) as z:
        items = [(i.filename, z.read(i.filename)) for i in z.infolist()]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
            for name, data in items:
                z.writestr(name, data)
            z.writestr(items[0][0], items[0][1])
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "zip_duplicate" for f in r["findings"])


def test_verify_nondeterministic_metadata_fail(verifier, built_zip, tmp_path):
    dst = tmp_path / "nd.zip"
    with zipfile.ZipFile(built_zip) as z:
        items = {i.filename: z.read(i.filename) for i in z.infolist()}
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(items):
            z.writestr(name, items[name])
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "nondeterministic_metadata" for f in r["findings"])


def test_verify_checksum_set_and_spacing(verifier, common, built_zip, tmp_path):
    def mut(it):
        lines = it["SHA256SUMS.txt"].decode().splitlines()
        lines[0] = lines[0].replace("  ", " ", 1)
        it["SHA256SUMS.txt"] = ("\n".join(lines) + "\n").encode()
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "checksums_format" for f in r["findings"])


def test_verify_required_path_absent_fail(verifier, common, built_zip, tmp_path):
    # Drop a REQUIRED payload file + its manifest/size/checksum records (self-consistent omission).
    def mut(it):
        target = "repo/release/release-policy.md"
        it.pop(target, None)
        m = json.loads(it["release-manifest.json"])
        m["files"] = [f for f in m["files"] if f["archive_path"] != target]
        n = len(m["files"])
        m["counts"].update(file_count=n, payload_count=n, tracked_count=n, entry_count=n + 3)
        it["release-manifest.json"] = (json.dumps(m) + "\n").encode()
        sizes = json.loads(it["FILE_SIZES.json"]); sizes["files"].pop(target, None)
        it["FILE_SIZES.json"] = (json.dumps(sizes) + "\n").encode()
    dst = tmp_path / "z.zip"
    with zipfile.ZipFile(built_zip) as z:
        items = {i.filename: z.read(i.filename) for i in z.infolist()}
    mut(items)
    # rebuild checksums to stay self-consistent
    payload = {k: v for k, v in items.items() if k != "SHA256SUMS.txt"}
    items["SHA256SUMS.txt"] = common.checksum_text(payload)
    dst.write_bytes(common.deterministic_zip_bytes(items))
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL" and any(f["code"] == "required_path_absent" for f in r["findings"])


def test_verify_jsonl_entry_fail(verifier, common, built_zip, tmp_path):
    def mut(it):
        it["repo/records.jsonl"] = b'{"x":1}\n'
    dst = tmp_path / "z.zip"; _repackage(common, built_zip, dst, mut)
    r = verifier.verify_release_candidate(dst)
    assert r["status"] == "FAIL"
    assert any(f["code"] in {"jsonl_present", "tracked_path_prohibited", "manifest_payload_mismatch",
                             "sizes_set_mismatch", "checksums_set_mismatch"} for f in r["findings"])


def test_verify_malformed_candidate_structured_not_traceback(verifier, common, built_zip, tmp_path):
    dst = tmp_path / "z.zip"
    _repackage(common, built_zip, dst,
               lambda it: it.__setitem__("release-manifest.json", b'{"schema_version": 4, "files": "nope"}'))
    r = verifier.verify_release_candidate(dst)  # must not raise
    assert r["status"] == "FAIL" and r["passed"] is False


def test_verify_not_verifiable_is_not_pass(verifier, common, tmp_path):
    manifest = {
        "schema_version": 4,
        "builder": {"tool": "build_release_candidate", "manifest_schema_version": 4, "archive_inspection_version": 1},
        "repository": {"head": "a" * 40, "branch": "b", "base_sha": None},
        "policy": {"policy_id": "x", "schema_version": 4, "sha256": "c" * 64},
        "counts": {"file_count": 0, "tracked_count": 0, "generated_count": 0,
                   "payload_count": 0, "control_count": 3, "entry_count": 3},
        "control_coverage": dict(common.CONTROL_COVERAGE_CANON),
        "content_controls": {"jsonl_included": False, "result_json_included": False,
                             "credentials_included": False, "databases_included": False,
                             "git_metadata_included": False, "venv_included": False, "built_from": "x"},
        "zip_policy": dict(common.ZIP_POLICY_CANON),
        "files": [],
    }
    mbytes = (json.dumps(manifest) + "\n").encode()
    files = {"release-manifest.json": mbytes}
    files["FILE_SIZES.json"] = (json.dumps({"schema_version": 1, "files": {
        "release-manifest.json": len(mbytes)}}) + "\n").encode()
    files["SHA256SUMS.txt"] = common.checksum_text(files)
    z = tmp_path / "empty.zip"; z.write_bytes(common.deterministic_zip_bytes(files))
    r = verifier.verify_release_candidate(z)
    assert r["status"] == "NOT_VERIFIABLE" and r["passed"] is False


def test_verify_does_not_modify_zip(verifier, built_zip):
    before = built_zip.read_bytes()
    verifier.verify_release_candidate(built_zip)
    assert built_zip.read_bytes() == before
