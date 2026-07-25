"""Phase 12G V4 tests: mandatory external trust anchor, content-free failures,
generated-file contract, plus preserved V3 controls (disjoint policy,
snapshot-bound archive, verify-before-publish). Synthetic fixtures only.
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


def _pf(zip_path):
    # locate the synthetic repo policy for a built zip under <tmp>/<repo>; tests pass explicitly instead
    raise NotImplementedError


def _vr(verifier, zip_path, policy_file, **kw):
    """PASS-capable verification uses the external trusted policy file."""
    return verifier.verify_release_candidate(zip_path, expected_policy_file=policy_file, **kw)


def _repackage(common, zip_src: Path, zip_dst: Path, mutate):
    with zipfile.ZipFile(zip_src) as z:
        items = {i.filename: z.read(i.filename) for i in z.infolist()}
    mutate(items)
    zip_dst.write_bytes(common.deterministic_zip_bytes(items))


def _resign(common, items: dict):
    """Rebuild FILE_SIZES + SHA256SUMS so a mutated candidate stays self-consistent."""
    payload = {k: v for k, v in items.items() if k not in ("FILE_SIZES.json", "SHA256SUMS.txt")}
    sizes = {"schema_version": 1, "files": {k: len(v) for k, v in sorted(payload.items())}}
    items["FILE_SIZES.json"] = (json.dumps(sizes, indent=2, sort_keys=True) + "\n").encode()
    signed = {k: v for k, v in items.items() if k != "SHA256SUMS.txt"}
    items["SHA256SUMS.txt"] = common.checksum_text(signed)


def _manifest_of(zip_path: Path) -> dict:
    with zipfile.ZipFile(zip_path) as z:
        return json.loads(z.read("release-manifest.json"))


def _add_allowed_archive(repo: Path, git, members: dict, *, path="bundle.zip"):
    (repo / path).write_bytes(make_zip(members))
    obj = valid_policy_obj(["release/release-allowlist.json", "release/release-policy.md"],
                           allowed_archives=[{"path": path}])
    write_policy(repo, obj)
    git("add", "-f", path); git("add", "-A"); git("commit", "-q", "-m", "add archive")


@pytest.fixture()
def built_zip(builder, synthetic_repo, tmp_path):
    _build(builder, synthetic_repo, tmp_path / "out")
    return (tmp_path / "out" / "release-candidate.zip")


# =========================================================================== #
# Baseline
# =========================================================================== #
def test_clean_build_and_verify_pass(builder, verifier, synthetic_repo, tmp_path, policy_file):
    s = _build(builder, synthetic_repo, tmp_path / "out")
    assert s["ok"] is True and s["trust_anchor_source"] == "external_tracked_policy"
    assert s["verifier_trust_mode"] == "external_file"
    assert s["prepublication_verifier_result"] == "PASS" and s["postpublication_verifier_result"] == "PASS"
    assert s["generated_count"] == 0 and s["generated_allowlist_sha256"] is None
    r = _vr(verifier, (tmp_path / "out" / "release-candidate.zip"), policy_file)
    assert r["status"] == "PASS" and r["policy_trust"] == "external_file", r


def test_manifest_has_canonical_zero_generated_state(builder, synthetic_repo, tmp_path):
    s = _build(builder, synthetic_repo, tmp_path / "out")
    m = _manifest_of((tmp_path / "out" / "release-candidate.zip"))
    assert m["schema_version"] == 5
    assert m["generated"] == {"count": 0, "allowlist_sha256": None}
    assert m["counts"]["generated_count"] == 0


# =========================================================================== #
# Phase D — mandatory external policy trust anchor
# =========================================================================== #
def test_verifier_without_expected_policy_is_not_verifiable(verifier, built_zip):
    r = verifier.verify_release_candidate(built_zip)  # no anchor
    assert r["status"] == "NOT_VERIFIABLE" and r["passed"] is False
    assert r["policy_trust"] == "unanchored"
    assert any(n["code"] == "policy_unanchored" for n in r["not_verifiable"])


def test_candidate_anchored_pass_removed(verifier, built_zip):
    r = verifier.verify_release_candidate(built_zip)
    assert r["status"] != "PASS"
    assert "candidate_anchored" not in json.dumps(r)


def test_trusted_sha_only_cannot_pass(verifier, built_zip):
    m = _manifest_of(built_zip)
    r = verifier.verify_release_candidate(built_zip, expected_policy_sha256=m["policy"]["sha256"])
    assert r["status"] == "NOT_VERIFIABLE" and r["policy_trust"] == "hash_only"
    assert any(n["code"] == "policy_hash_only" for n in r["not_verifiable"])


def test_external_policy_file_exact_match_passes(verifier, built_zip, policy_file):
    r = _vr(verifier, built_zip, policy_file)
    assert r["status"] == "PASS" and r["policy_trust"] == "external_file"


def test_external_policy_hash_only_mismatch_fails(verifier, built_zip):
    r = verifier.verify_release_candidate(built_zip, expected_policy_sha256="a" * 64)
    assert r["status"] == "FAIL" and any(f["code"] == "policy_untrusted" for f in r["findings"])


def test_external_policy_bytes_mismatch_fails(verifier, built_zip, tmp_path):
    other = tmp_path / "other-policy.json"
    other.write_text(json.dumps(valid_policy_obj(["release/release-allowlist.json"])), encoding="utf-8")
    r = _vr(verifier, built_zip, other)
    assert r["status"] == "FAIL"
    assert any(f["code"] in {"policy_bytes_mismatch", "policy_untrusted", "policy_identity_mismatch"}
               for f in r["findings"])


def test_candidate_embedded_policy_mismatch_fails(verifier, common, built_zip, tmp_path, policy_file):
    def mut(it):
        it[f"repo/release/release-allowlist.json"] = b'{"tampered": true}\n'
    dst = tmp_path / "z.zip"
    with zipfile.ZipFile(built_zip) as z:
        items = {i.filename: z.read(i.filename) for i in z.infolist()}
    mut(items); _resign(common, items)
    dst.write_bytes(common.deterministic_zip_bytes(items))
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL"


def test_attacker_replaces_policy_and_manifest_together_still_fails(verifier, common, built_zip, tmp_path, policy_file):
    # Coherently swap embedded policy + manifest policy identity to weaken prohibited classes.
    weak = valid_policy_obj(["release/release-allowlist.json", "release/release-policy.md"])
    weak["prohibited"]["exact_names"] = []  # attacker weakens
    weak_bytes = (json.dumps(weak, indent=2) + "\n").encode()
    import hashlib
    weak_sha = hashlib.sha256(weak_bytes).hexdigest()
    with zipfile.ZipFile(built_zip) as z:
        items = {i.filename: z.read(i.filename) for i in z.infolist()}
    items["repo/release/release-allowlist.json"] = weak_bytes
    m = json.loads(items["release-manifest.json"])
    m["policy"]["sha256"] = weak_sha
    for f in m["files"]:
        if f["path"] == "release/release-allowlist.json":
            f["sha256"] = weak_sha; f["size_bytes"] = len(weak_bytes)
    items["release-manifest.json"] = (json.dumps(m, indent=2, sort_keys=True) + "\n").encode()
    _resign(common, items)
    dst = tmp_path / "z.zip"; dst.write_bytes(common.deterministic_zip_bytes(items))
    r = _vr(verifier, dst, policy_file)  # trusted external policy still the strong one
    assert r["status"] == "FAIL"
    assert any(f["code"] in {"policy_bytes_mismatch", "policy_untrusted"} for f in r["findings"])


def test_payload_rule_mismatch_under_external_policy_fails(verifier, common, built_zip, tmp_path, policy_file):
    def mut(it):
        m = json.loads(it["release-manifest.json"])
        for f in m["files"]:
            if f["path"] == "src/app.py":
                f["rule_id"] = "allow-ext-txt"
        it["release-manifest.json"] = (json.dumps(m, indent=2, sort_keys=True) + "\n").encode()
        _resign(common, it)
    dst = tmp_path / "z.zip"; _repackage_full(common, built_zip, dst, mut)
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL" and any(f["code"] == "classification_mismatch" for f in r["findings"])


def _repackage_full(common, zip_src, zip_dst, mutate):
    with zipfile.ZipFile(zip_src) as z:
        items = {i.filename: z.read(i.filename) for i in z.infolist()}
    mutate(items)
    zip_dst.write_bytes(common.deterministic_zip_bytes(items))


def test_builder_passes_trusted_bytes_to_verification(builder, synthetic_repo, tmp_path, monkeypatch):
    calls = []
    real = builder._verifier.verify_release_candidate

    def spy(zip_path, **kw):
        calls.append(kw.get("expected_policy_file"))
        return real(zip_path, **kw)

    monkeypatch.setattr(builder._verifier, "verify_release_candidate", spy)
    _build(builder, synthetic_repo, tmp_path / "out")
    assert len(calls) == 2  # staging + published
    # Both verifications consume ONE immutable trusted byte snapshot (not the mutable repo path).
    for c in calls:
        assert c is not None and Path(c).name == "trusted-policy.json"
    assert calls[0] == calls[1]


def test_builder_refuses_publication_when_trusted_verification_not_pass(builder, synthetic_repo, tmp_path):
    out = tmp_path / "out"
    with mock.patch.object(builder._verifier, "verify_release_candidate",
                           return_value={"status": "NOT_VERIFIABLE", "findings": [], "not_verifiable": []}):
        with pytest.raises(builder.ReleaseError) as e:
            _build(builder, synthetic_repo, out)
    assert e.value.code == "verify_before_publish" and not out.exists()


def test_cli_without_anchor_uses_non_pass_exit_code(verifier, built_zip):
    rc = verifier.main(["--zip", str(built_zip)])
    assert rc != 0  # NOT_VERIFIABLE -> exit 2


def test_cli_with_external_policy_file_passes(verifier, built_zip, policy_file):
    rc = verifier.main(["--zip", str(built_zip), "--expected-policy-file", str(policy_file)])
    assert rc == 0


# =========================================================================== #
# Phase G — content-free failures
# =========================================================================== #
def _assert_content_free(report, *forbidden):
    blob = json.dumps(report)
    assert report["content_free"] is True
    for f in report.get("findings", []):
        assert f.get("content_free") is True
    for s in forbidden:
        assert s not in blob, f"leaked: {s}"


def test_content_free_unexpected_entry_name(verifier, common, built_zip, tmp_path, policy_file):
    secret = "repo/AWS_SECRET_ACCESS_KEY_deadbeef.txt"
    def mut(it):
        it[secret] = b"x"
    dst = tmp_path / "z.zip"; _repackage_full(common, built_zip, dst, mut)
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL"
    _assert_content_free(r, "AWS_SECRET_ACCESS_KEY_deadbeef", secret)


def test_content_free_traversal_and_absolute_names(verifier, common, built_zip, tmp_path, policy_file):
    dst = tmp_path / "z.zip"
    with zipfile.ZipFile(built_zip) as z:
        items = {i.filename: z.read(i.filename) for i in z.infolist()}
    # unsafe outer names are rejected by read_zip_entries -> zip_unsafe_path (generic)
    items["repo/../../Users/victim/secret.txt"] = b"x"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for n, d in items.items():
                z.writestr(n, d)
        dst.write_bytes(buf.getvalue())
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL"
    _assert_content_free(r, "victim", "secret.txt", "..")


def test_content_free_nested_archive_credential_name(verifier, common, synthetic_repo, tmp_path, git, policy_file):
    _add_allowed_archive(synthetic_repo, git, {"credentials/id_rsa": b"KEY", "ok.tex": b"y"})
    # inspection fails on the nested prohibited name; verifier surfaces only a code + hash
    r = builder_build_and_verify(common, synthetic_repo, tmp_path)  # helper below
    assert r is None  # build fails before producing a candidate


def builder_build_and_verify(common, repo, tmp_path):
    # The builder rejects the prohibited nested archive at build time (content-free).
    import importlib
    b = importlib.import_module("g12_build_release")
    try:
        b.build_release_candidate(repo_root=repo, output_dir=tmp_path / "out")
    except b.ReleaseError as e:
        assert "id_rsa" not in e.message and "credentials" not in e.message
        return None
    return "built"


def test_content_free_malicious_policy_id(verifier, common, built_zip, tmp_path, policy_file):
    def mut(it):
        m = json.loads(it["release-manifest.json"])
        m["policy"]["policy_id"] = "pwned-by-ATTACKER-token-cafebabe"
        it["release-manifest.json"] = (json.dumps(m, indent=2, sort_keys=True) + "\n").encode()
        _resign(common, it)
    dst = tmp_path / "z.zip"; _repackage_full(common, built_zip, dst, mut)
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL"
    _assert_content_free(r, "pwned-by-ATTACKER-token-cafebabe", "ATTACKER")


def test_content_free_malformed_checksum_key(verifier, common, built_zip, tmp_path, policy_file):
    def mut(it):
        it["SHA256SUMS.txt"] += (("0" * 64) + "  repo/TOKEN-abc123-secret.txt\n").encode()
    dst = tmp_path / "z.zip"; _repackage_full(common, built_zip, dst, mut)
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL"
    _assert_content_free(r, "TOKEN-abc123-secret")


def test_content_free_malformed_json(verifier, common, built_zip, tmp_path, policy_file):
    dst = tmp_path / "z.zip"
    _repackage_full(common, built_zip, dst,
                    lambda it: it.__setitem__("release-manifest.json", b'{"secret":"LEAKED-TOKEN-xyz" '))
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL"
    _assert_content_free(r, "LEAKED-TOKEN-xyz")


def test_content_free_malformed_zip(verifier, tmp_path, policy_file):
    bad = tmp_path / "bad.zip"; bad.write_bytes(b"PK\x03\x04 not really a zip SECRET-LEAK-123")
    r = _vr(verifier, bad, policy_file)
    assert r["status"] == "FAIL"
    _assert_content_free(r, "SECRET-LEAK-123")


def test_content_free_unicode_failure(verifier, common, built_zip, tmp_path, policy_file):
    dst = tmp_path / "z.zip"
    _repackage_full(common, built_zip, dst,
                    lambda it: it.__setitem__("release-manifest.json", b"\xff\xfe\x00SECRETBYTES"))
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL"
    _assert_content_free(r, "SECRETBYTES")


def test_whole_report_secret_absence(verifier, common, built_zip, tmp_path, policy_file):
    secret = "repo/subdir/MEGA-SECRET-PASSWORD-9f9f9f.jsonl"
    def mut(it):
        it[secret] = b'{"x":1}\n'
    dst = tmp_path / "z.zip"; _repackage_full(common, built_zip, dst, mut)
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL"
    _assert_content_free(r, "MEGA-SECRET-PASSWORD-9f9f9f", secret)


# =========================================================================== #
# Phase I — generated-file contract
# =========================================================================== #
def _gen_manifest_mut(count, allowlist_sha):
    def mut(it, common):
        m = json.loads(it["release-manifest.json"])
        m["generated"] = {"count": count, "allowlist_sha256": allowlist_sha}
        it["release-manifest.json"] = (json.dumps(m, indent=2, sort_keys=True) + "\n").encode()
        _resign(common, it)
    return mut


def test_generated_zero_state_passes(verifier, built_zip, policy_file):
    assert _vr(verifier, built_zip, policy_file)["status"] == "PASS"


def test_generated_metadata_present_with_zero_count_fails(verifier, common, built_zip, tmp_path, policy_file):
    def mut(it):
        m = json.loads(it["release-manifest.json"])
        m["generated"] = {"count": 0, "allowlist_sha256": "a" * 64}  # non-null with zero count
        it["release-manifest.json"] = (json.dumps(m, indent=2, sort_keys=True) + "\n").encode()
        _resign(common, it)
    dst = tmp_path / "z.zip"; _repackage_full(common, built_zip, dst, mut)
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL"


def test_generated_missing_field_fails(verifier, common, built_zip, tmp_path, policy_file):
    def mut(it):
        m = json.loads(it["release-manifest.json"])
        m["generated"] = {"count": 0}  # missing allowlist_sha256
        it["release-manifest.json"] = (json.dumps(m, indent=2, sort_keys=True) + "\n").encode()
        _resign(common, it)
    dst = tmp_path / "z.zip"; _repackage_full(common, built_zip, dst, mut)
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL" and any(f["code"] == "schema_missing_field" for f in r["findings"])


def test_generated_wrong_rule_form_fails(builder, verifier, common, synthetic_repo, tmp_path, git, policy_file):
    # Build with a real generated file, then flip only rule_form -> must fail.
    (synthetic_repo / "pipfreeze.txt").write_text("pytest==8.0\n", encoding="utf-8")
    import hashlib
    data = (synthetic_repo / "pipfreeze.txt").read_bytes()
    gen = tmp_path / "gen.json"
    gen.write_text(json.dumps({"schema_version": 1, "generated_files": [
        {"path": "pipfreeze.txt", "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}]}),
        encoding="utf-8")
    # pipfreeze.txt is untracked (generated); commit only leaves it out of tracked set
    s = _build(builder, synthetic_repo, tmp_path / "out", generated_allowlist=gen)
    zip_path = (tmp_path / "out" / "release-candidate.zip")
    m = _manifest_of(zip_path)
    genrows = [f for f in m["files"] if f["source"] == "generated"]
    assert genrows and genrows[0]["rule_form"] == "generated"
    def mut(it):
        mm = json.loads(it["release-manifest.json"])
        for f in mm["files"]:
            if f["source"] == "generated":
                f["rule_form"] = "extension"  # non-canonical
        it["release-manifest.json"] = (json.dumps(mm, indent=2, sort_keys=True) + "\n").encode()
        _resign(common, it)
    dst = tmp_path / "z.zip"; _repackage_full(common, zip_path, dst, mut)
    r = verifier.verify_release_candidate(dst, expected_policy_file=policy_file,
                                          expected_generated_file=gen)
    assert r["status"] == "FAIL" and any(f["code"] == "generated_semantic" for f in r["findings"])


def test_generated_nonzero_without_external_anchor_not_pass(builder, verifier, common, synthetic_repo, tmp_path, policy_file):
    (synthetic_repo / "pipfreeze.txt").write_text("pytest==8.0\n", encoding="utf-8")
    import hashlib
    data = (synthetic_repo / "pipfreeze.txt").read_bytes()
    gen = tmp_path / "gen.json"
    gen.write_text(json.dumps({"schema_version": 1, "generated_files": [
        {"path": "pipfreeze.txt", "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}]}),
        encoding="utf-8")
    s = _build(builder, synthetic_repo, tmp_path / "out", generated_allowlist=gen)
    r = _vr(verifier, (tmp_path / "out" / "release-candidate.zip"), policy_file)  # no expected_generated_sha256
    assert r["status"] == "NOT_VERIFIABLE"
    assert any(n["code"] == "generated_anchor_missing" for n in r["not_verifiable"])


def test_generated_external_anchor_match_passes(builder, verifier, common, synthetic_repo, tmp_path, policy_file):
    (synthetic_repo / "pipfreeze.txt").write_text("pytest==8.0\n", encoding="utf-8")
    import hashlib
    data = (synthetic_repo / "pipfreeze.txt").read_bytes()
    gen = tmp_path / "gen.json"
    gen.write_text(json.dumps({"schema_version": 1, "generated_files": [
        {"path": "pipfreeze.txt", "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}]}),
        encoding="utf-8")
    s = _build(builder, synthetic_repo, tmp_path / "out", generated_allowlist=gen)
    m = _manifest_of((tmp_path / "out" / "release-candidate.zip"))
    r = verifier.verify_release_candidate((tmp_path / "out" / "release-candidate.zip"), expected_policy_file=policy_file,
                                          expected_generated_file=gen)
    assert r["status"] == "PASS" and r["generated_count"] == 1


def _gen_decl(path, entries):
    path.write_text(json.dumps({"schema_version": 1, "generated_files": entries}), encoding="utf-8")
    return path


def test_generated_hash_only_cannot_pass(builder, verifier, synthetic_repo, tmp_path, policy_file):
    (synthetic_repo / "pipfreeze.txt").write_text("pytest==8.0\n", encoding="utf-8")
    import hashlib
    data = (synthetic_repo / "pipfreeze.txt").read_bytes()
    gen = _gen_decl(tmp_path / "gen.json", [
        {"path": "pipfreeze.txt", "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}])
    s = _build(builder, synthetic_repo, tmp_path / "out", generated_allowlist=gen)
    m = _manifest_of((tmp_path / "out" / "release-candidate.zip"))
    r = verifier.verify_release_candidate((tmp_path / "out" / "release-candidate.zip"), expected_policy_file=policy_file,
                                          expected_generated_sha256=m["generated"]["allowlist_sha256"])
    assert r["status"] == "NOT_VERIFIABLE"
    assert any(n["code"] == "generated_hash_only" for n in r["not_verifiable"])


def test_generated_anchor_mismatch_fails(builder, verifier, synthetic_repo, tmp_path, policy_file):
    (synthetic_repo / "pipfreeze.txt").write_text("pytest==8.0\n", encoding="utf-8")
    import hashlib
    data = (synthetic_repo / "pipfreeze.txt").read_bytes()
    gen = _gen_decl(tmp_path / "gen.json", [
        {"path": "pipfreeze.txt", "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}])
    s = _build(builder, synthetic_repo, tmp_path / "out", generated_allowlist=gen)
    # A reformatted declaration: same mapping, different bytes -> different declaration SHA.
    gen2 = tmp_path / "gen2.json"
    gen2.write_text(json.dumps({"schema_version": 1, "generated_files": [
        {"path": "pipfreeze.txt", "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}]},
        indent=4), encoding="utf-8")
    r = verifier.verify_release_candidate((tmp_path / "out" / "release-candidate.zip"), expected_policy_file=policy_file,
                                          expected_generated_file=gen2)
    assert r["status"] == "FAIL" and any(f["code"] == "generated_anchor_mismatch" for f in r["findings"])


def test_generated_declaration_path_absent_fails(builder, verifier, synthetic_repo, tmp_path, policy_file):
    (synthetic_repo / "pipfreeze.txt").write_text("pytest==8.0\n", encoding="utf-8")
    import hashlib
    data = (synthetic_repo / "pipfreeze.txt").read_bytes()
    gen = _gen_decl(tmp_path / "gen.json", [
        {"path": "pipfreeze.txt", "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}])
    s = _build(builder, synthetic_repo, tmp_path / "out", generated_allowlist=gen)
    # Declaration with an EXTRA path not in the candidate -> set mismatch.
    other = _gen_decl(tmp_path / "gen3.json", [
        {"path": "pipfreeze.txt", "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)},
        {"path": "phantom.txt", "sha256": "0" * 64, "size_bytes": 1}])
    r = verifier.verify_release_candidate((tmp_path / "out" / "release-candidate.zip"), expected_policy_file=policy_file,
                                          expected_generated_file=other)
    assert r["status"] == "FAIL"
    assert any(f["code"] in {"generated_set_mismatch", "generated_anchor_mismatch"} for f in r["findings"])


def test_generated_declaration_malformed_fails(common):
    with pytest.raises(common.ReleaseError) as e:
        common.parse_generated_declaration(b"{ not json")
    assert e.value.code == "malformed_json"


def test_generated_declaration_boolean_size_fails(common):
    raw = json.dumps({"schema_version": 1, "generated_files": [
        {"path": "a.txt", "sha256": "0" * 64, "size_bytes": True}]}).encode()
    with pytest.raises(common.ReleaseError) as e:
        common.parse_generated_declaration(raw)
    assert e.value.code == "generated_declaration"


def test_generated_declaration_duplicate_path_fails(common):
    raw = json.dumps({"schema_version": 1, "generated_files": [
        {"path": "a.txt", "sha256": "0" * 64, "size_bytes": 1},
        {"path": "a.txt", "sha256": "1" * 64, "size_bytes": 2}]}).encode()
    with pytest.raises(common.ReleaseError) as e:
        common.parse_generated_declaration(raw)
    assert e.value.code == "generated_declaration"


def test_generated_declaration_unexpected_field_fails(common):
    raw = json.dumps({"schema_version": 1, "generated_files": [
        {"path": "a.txt", "sha256": "0" * 64, "size_bytes": 1, "surprise": 1}]}).encode()
    with pytest.raises(common.ReleaseError) as e:
        common.parse_generated_declaration(raw)
    assert e.value.code == "generated_declaration"


# --- contradictory anchors ---
def test_policy_file_and_matching_sha_passes(verifier, common, built_zip, policy_file):
    trusted_sha = common.sha256_bytes(Path(policy_file).read_bytes())
    r = verifier.verify_release_candidate(built_zip, expected_policy_file=policy_file,
                                          expected_policy_sha256=trusted_sha)
    assert r["status"] == "PASS"


def test_policy_file_and_mismatching_sha_fails(verifier, built_zip, policy_file):
    r = verifier.verify_release_candidate(built_zip, expected_policy_file=policy_file,
                                          expected_policy_sha256="c" * 64)
    assert r["status"] == "FAIL" and any(f["code"] == "contradictory_policy_anchor" for f in r["findings"])


def test_generated_file_and_mismatching_sha_fails(builder, verifier, synthetic_repo, tmp_path, policy_file):
    (synthetic_repo / "pipfreeze.txt").write_text("pytest==8.0\n", encoding="utf-8")
    import hashlib
    data = (synthetic_repo / "pipfreeze.txt").read_bytes()
    gen = _gen_decl(tmp_path / "gen.json", [
        {"path": "pipfreeze.txt", "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}])
    s = _build(builder, synthetic_repo, tmp_path / "out", generated_allowlist=gen)
    r = verifier.verify_release_candidate((tmp_path / "out" / "release-candidate.zip"), expected_policy_file=policy_file,
                                          expected_generated_file=gen, expected_generated_sha256="d" * 64)
    assert r["status"] == "FAIL" and any(f["code"] == "contradictory_generated_anchor" for f in r["findings"])


# --- ZIP comment / metadata channels ---
def test_nonempty_outer_zip_comment_fails(verifier, common, built_zip, tmp_path, policy_file):
    with zipfile.ZipFile(built_zip) as z:
        items = {i.filename: z.read(i.filename) for i in z.infolist()}
    dst = tmp_path / "c.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n in sorted(items):
            z.writestr(n, items[n])
        z.comment = b"HIDDEN-DATA-OUTSIDE-MANIFEST"
    dst.write_bytes(buf.getvalue())
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL" and any(f["code"] == "zip_comment_nonempty" for f in r["findings"])
    _assert_content_free(r, "HIDDEN-DATA-OUTSIDE-MANIFEST")


def test_entry_comment_fails(verifier, common, built_zip, tmp_path, policy_file):
    with zipfile.ZipFile(built_zip) as z:
        infos = z.infolist()
        items = [(i, z.read(i.filename)) for i in infos]
    dst = tmp_path / "ec.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for i, data in items:
            zi = zipfile.ZipInfo(i.filename, date_time=common.ZIP_TIMESTAMP)
            zi.comment = b"ENTRY-HIDDEN"
            z.writestr(zi, data)
    dst.write_bytes(buf.getvalue())
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL"
    _assert_content_free(r, "ENTRY-HIDDEN")


def test_builder_produces_empty_zip_comment(builder, synthetic_repo, tmp_path):
    s = _build(builder, synthetic_repo, tmp_path / "out")
    with zipfile.ZipFile((tmp_path / "out" / "release-candidate.zip")) as z:
        assert z.comment == b""
        assert all(i.comment == b"" and i.extra == b"" for i in z.infolist())


# --- content-free: candidate repo_head + builder errors ---
def test_content_free_malicious_repo_head(verifier, common, built_zip, tmp_path, policy_file):
    def mut(it):
        m = json.loads(it["release-manifest.json"])
        m["repository"]["head"] = "deadbeefLEAKTOKEN" + "a" * 24  # 40-ish, malicious content
        it["release-manifest.json"] = (json.dumps(m, indent=2, sort_keys=True) + "\n").encode()
        _resign(common, it)
    dst = tmp_path / "z.zip"; _repackage_full(common, built_zip, dst, mut)
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL"
    assert "repo_head" not in {k for k in r}  # raw head field removed from report
    _assert_content_free(r, "LEAKTOKEN", "deadbeefLEAKTOKEN")


def test_builder_error_output_content_free(builder, synthetic_repo, tmp_path, git):
    # A prohibited tracked file with a secret-like name; the builder CLI error must be code-only.
    (synthetic_repo / "SECRET_TOKEN_cafef00d.pem").write_text("k\n", encoding="utf-8")
    git("add", "-f", "SECRET_TOKEN_cafef00d.pem"); _commit(git, "pem")
    import io as _io
    import contextlib
    buf = _io.StringIO()
    with contextlib.redirect_stderr(buf), contextlib.redirect_stdout(buf):
        rc = builder.main(["--repo-root", str(synthetic_repo), "--output-dir", str(tmp_path / "out")])
    out = buf.getvalue()
    assert rc == 1
    assert "SECRET_TOKEN_cafef00d" not in out
    assert '"error_code"' in out and '"content_free": true' in out


def test_generated_sha_mismatch_at_build_fails(builder, synthetic_repo, tmp_path):
    (synthetic_repo / "pipfreeze.txt").write_text("pytest==8.0\n", encoding="utf-8")
    gen = tmp_path / "gen.json"
    gen.write_text(json.dumps({"schema_version": 1, "generated_files": [
        {"path": "pipfreeze.txt", "sha256": "0" * 64, "size_bytes": 999}]}), encoding="utf-8")
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, tmp_path / "out", generated_allowlist=gen)
    assert e.value.code == "generated_mismatch"


# =========================================================================== #
# Phase J — preserved V3 controls
# =========================================================================== #
def test_every_tracked_path_has_exactly_one_permitted_rule(common, synthetic_repo):
    pol = common.parse_release_policy((synthetic_repo / "release/release-allowlist.json").read_bytes())
    tracked = [x for x in subprocess.run(["git", "-C", str(synthetic_repo), "ls-files", "-z"],
                                         capture_output=True, text=True).stdout.split("\0") if x]
    for rel in tracked:
        pure = PurePosixPath(rel)
        matches = [r.rule_id for r in pol.inclusion_rules
                   if common._rule_effective_matches(r, rel, pure.name.casefold(), pure.suffix.casefold())]
        assert len(matches) == 1, (rel, matches)


def test_two_permitted_rules_matching_one_path_fail(common):
    obj = valid_policy_obj(["release/release-policy.md"])
    for r in obj["inclusion_rules"]:
        if r["rule_id"] == "allow-ext-md":
            r["exclude_exact_paths"] = []
    with pytest.raises(common.ReleaseError) as e:
        common.parse_release_policy(json.dumps(obj).encode())
    assert e.value.code == "ambiguous_policy_classification"


def test_unhashable_rule_class_rejected(common):
    obj = valid_policy_obj(["release/release-allowlist.json"])
    obj["inclusion_rules"][0]["class"] = ["REQUIRED"]  # unhashable
    with pytest.raises(common.ReleaseError) as e:
        common.parse_release_policy(json.dumps(obj).encode())
    assert e.value.code == "policy_schema"


def test_drive_shaped_exact_name_rejected(common):
    obj = valid_policy_obj(["release/release-allowlist.json"],
                           extra_exact_names=["C:evil"])
    with pytest.raises(common.ReleaseError) as e:
        common.parse_release_policy(json.dumps(obj).encode())
    assert e.value.code == "policy_schema"


def test_unclassified_root_file_fails(builder, synthetic_repo, tmp_path, git):
    (synthetic_repo / "mystery.xyz").write_text("data\n", encoding="utf-8")
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


def test_builder_verifier_share_archive_helper(builder, verifier, common):
    assert builder.inspect_archive_bytes is common.inspect_archive_bytes
    assert verifier.rc.inspect_archive_bytes is common.inspect_archive_bytes


def test_allowed_archive_safe_names_passes(builder, verifier, synthetic_repo, tmp_path, git, policy_file):
    _add_allowed_archive(synthetic_repo, git, {"fig/a.tex": b"x", "b.bib": b"y"})
    s = _build(builder, synthetic_repo, tmp_path / "out")
    m = _manifest_of((tmp_path / "out" / "release-candidate.zip"))
    arc = [f for f in m["files"] if f["path"] == "bundle.zip"][0]
    assert arc["classification"] == "ALLOWED_ARCHIVE" and arc["archive_inspection"]["result"] == "SAFE"
    assert _vr(verifier, (tmp_path / "out" / "release-candidate.zip"), policy_file)["status"] == "PASS"


def test_archive_scan_uses_snapshot_not_second_read(builder, synthetic_repo, tmp_path, git, common):
    _add_allowed_archive(synthetic_repo, git, {"only/one.tex": b"z"})
    crafted = make_zip({"a.tex": b"1", "b.bib": b"2", "c.sty": b"3"})
    real = builder.read_snapshot_bytes

    def patched(path):
        return crafted if path.name == "bundle.zip" else real(path)

    with mock.patch.object(builder, "read_snapshot_bytes", patched):
        s = _build(builder, synthetic_repo, tmp_path / "out")
    arc = [f for f in _manifest_of((tmp_path / "out" / "release-candidate.zip"))["files"] if f["path"] == "bundle.zip"][0]
    assert arc["sha256"] == common.sha256_bytes(crafted)
    assert arc["archive_inspection"]["entry_count"] == 3


def test_verifier_reinspects_archive_metadata(builder, verifier, common, synthetic_repo, tmp_path, git, policy_file):
    _add_allowed_archive(synthetic_repo, git, {"a.tex": b"1", "b.bib": b"2"})
    s = _build(builder, synthetic_repo, tmp_path / "out")
    def mut(it):
        m = json.loads(it["release-manifest.json"])
        for f in m["files"]:
            if f["path"] == "bundle.zip":
                f["archive_inspection"]["entry_count"] = 99
        it["release-manifest.json"] = (json.dumps(m, indent=2, sort_keys=True) + "\n").encode()
        _resign(common, it)
    dst = tmp_path / "z.zip"; _repackage_full(common, (tmp_path / "out" / "release-candidate.zip"), dst, mut)
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL" and any(f["code"] == "archive_scan_mismatch" for f in r["findings"])


def test_archive_traversal_nested_name_direct(common, synthetic_repo):
    pol = common.parse_release_policy((synthetic_repo / "release/release-allowlist.json").read_bytes())
    data = make_zip({"../evil.tex": b"1"})
    with pytest.raises(common.ReleaseError) as e:
        common.inspect_archive_bytes(data, pol, rule_id="r",
                                     payload_sha=common.sha256_bytes(data), payload_size=len(data))
    assert e.value.code == "archive_traversal"


def test_archive_encrypted_entry_fails(common, synthetic_repo):
    pol = common.parse_release_policy((synthetic_repo / "release/release-allowlist.json").read_bytes())
    data = make_encrypted_zip("a.tex", b"secret")
    with pytest.raises(common.ReleaseError) as e:
        common.inspect_archive_bytes(data, pol, rule_id="r",
                                     payload_sha=common.sha256_bytes(data), payload_size=len(data))
    assert e.value.code == "archive_encrypted"


def test_outer_zip_entry_count_bound(common, tmp_path, monkeypatch):
    monkeypatch.setattr(common, "MAX_ZIP_ENTRIES", 3)
    z = tmp_path / "big.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for i in range(5):
            zf.writestr(f"f{i}.txt", b"x")
    with pytest.raises(common.ReleaseError) as e:
        common.read_zip_entries(z)
    assert e.value.code == "zip_too_many_entries"


def test_zip_bytes_are_the_hashed_bytes(builder, synthetic_repo, tmp_path):
    import hashlib
    s = _build(builder, synthetic_repo, tmp_path / "out")
    with zipfile.ZipFile((tmp_path / "out" / "release-candidate.zip")) as z:
        for item in _manifest_of((tmp_path / "out" / "release-candidate.zip"))["files"]:
            data = z.read(item["archive_path"])
            assert hashlib.sha256(data).hexdigest() == item["sha256"] and len(data) == item["size_bytes"]


def test_policy_single_read_bytes_match_package(builder, synthetic_repo, tmp_path, common):
    s = _build(builder, synthetic_repo, tmp_path / "out")
    with zipfile.ZipFile((tmp_path / "out" / "release-candidate.zip")) as z:
        packaged = z.read("repo/release/release-allowlist.json")
    assert packaged == (synthetic_repo / "release/release-allowlist.json").read_bytes()


def test_verify_before_publish_and_race(builder, synthetic_repo, tmp_path):
    out = tmp_path / "out"
    real = builder.hardlink_no_clobber

    def racing(src, dst):
        Path(dst).write_bytes(b"racer")
        return real(src, dst)

    with mock.patch.object(builder, "hardlink_no_clobber", racing):
        with pytest.raises(builder.ReleaseError) as e:
            _build(builder, synthetic_repo, out)
    assert e.value.code == "destination_exists"


def test_unsupported_hardlink_fails_closed(builder, synthetic_repo, tmp_path):
    out = tmp_path / "out"

    def unsupported(src, dst):
        raise builder.ReleaseError("hardlink_unsupported", "simulated")

    with mock.patch.object(builder, "hardlink_no_clobber", unsupported):
        with pytest.raises(builder.ReleaseError) as e:
            _build(builder, synthetic_repo, out)
    assert e.value.code == "hardlink_unsupported" and not out.exists()


def test_no_osreplace_for_final_zip_in_source():
    src = (Path(__file__).resolve().parents[2] / "scripts" / "release" / "build_release_candidate.py").read_text()
    assert "os.replace" not in src


def test_no_candidate_anchored_pass_branch_in_source():
    src = (Path(__file__).resolve().parents[2] / "scripts" / "release" / "verify_release_candidate.py").read_text()
    assert "candidate_anchored" not in src


def test_existing_output_dir_rejected_and_preserved(builder, synthetic_repo, tmp_path):
    out = tmp_path / "out"; out.mkdir()
    sentinel = out / "keep.txt"; sentinel.write_text("preexisting\n", encoding="utf-8")
    with pytest.raises(builder.ReleaseError) as e:
        _build(builder, synthetic_repo, out)
    assert e.value.code == "output_reuse" and sentinel.read_text(encoding="utf-8") == "preexisting\n"


def test_temp_files_removed_after_success(builder, synthetic_repo, tmp_path):
    _build(builder, synthetic_repo, tmp_path / "out")
    assert not list(tmp_path.glob(".rc-stage-*"))


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


# =========================================================================== #
# Verifier schema (content-free FAIL) regressions
# =========================================================================== #
def test_verify_missing_control_rejected(verifier, common, built_zip, tmp_path, policy_file):
    dst = tmp_path / "m.zip"
    _repackage_full(common, built_zip, dst, lambda it: it.pop("SHA256SUMS.txt"))
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL" and any(f["code"] == "missing_control_file" for f in r["findings"])


@pytest.mark.parametrize("obj_key", ["builder", "repository", "policy", "generated", "counts", "zip_policy"])
def test_verify_missing_manifest_object_fail(verifier, common, built_zip, tmp_path, policy_file, obj_key):
    def mut(it):
        m = json.loads(it["release-manifest.json"]); del m[obj_key]
        it["release-manifest.json"] = (json.dumps(m, indent=2, sort_keys=True) + "\n").encode()
        _resign(common, it)
    dst = tmp_path / "z.zip"; _repackage_full(common, built_zip, dst, mut)
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL" and any(f["code"] == "schema_missing_field" for f in r["findings"])


def test_verify_boolean_size_fail(verifier, common, built_zip, tmp_path, policy_file):
    def mut(it):
        m = json.loads(it["release-manifest.json"]); m["files"][0]["size_bytes"] = True
        it["release-manifest.json"] = (json.dumps(m, indent=2, sort_keys=True) + "\n").encode()
        _resign(common, it)
    dst = tmp_path / "z.zip"; _repackage_full(common, built_zip, dst, mut)
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL" and any(f["code"] == "schema_type" for f in r["findings"])


def test_verify_count_mismatch_fail(verifier, common, built_zip, tmp_path, policy_file):
    def mut(it):
        m = json.loads(it["release-manifest.json"]); m["counts"]["payload_count"] += 1
        it["release-manifest.json"] = (json.dumps(m, indent=2, sort_keys=True) + "\n").encode()
        _resign(common, it)
    dst = tmp_path / "z.zip"; _repackage_full(common, built_zip, dst, mut)
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL" and any(f["code"] == "counts_mismatch" for f in r["findings"])


def test_verify_nondeterministic_metadata_fail(verifier, built_zip, tmp_path, policy_file):
    dst = tmp_path / "nd.zip"
    with zipfile.ZipFile(built_zip) as z:
        items = {i.filename: z.read(i.filename) for i in z.infolist()}
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(items):
            z.writestr(name, items[name])
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL" and any(f["code"] == "nondeterministic_metadata" for f in r["findings"])


def test_verify_not_verifiable_is_not_pass(verifier, common, tmp_path, policy_file):
    manifest = {
        "schema_version": 5,
        "builder": {"tool": "build_release_candidate", "manifest_schema_version": 5, "archive_inspection_version": 1},
        "repository": {"head": "a" * 40, "branch": "b", "base_sha": None},
        "policy": {"policy_id": "x", "schema_version": 4, "sha256": "c" * 64},
        "generated": {"count": 0, "allowlist_sha256": None},
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
    r = _vr(verifier, z, policy_file)
    assert r["status"] == "NOT_VERIFIABLE" and r["passed"] is False


def test_verify_does_not_modify_zip(verifier, built_zip, policy_file):
    before = built_zip.read_bytes()
    _vr(verifier, built_zip, policy_file)
    assert built_zip.read_bytes() == before


# =========================================================================== #
# Re-added V3 archive-governance + limit regressions (no weakening)
# =========================================================================== #
@pytest.fixture()
def apol(common, synthetic_repo):
    return common.parse_release_policy((synthetic_repo / "release/release-allowlist.json").read_bytes())


def _inspect(common, pol, data):
    return common.inspect_archive_bytes(data, pol, rule_id="r",
                                        payload_sha=common.sha256_bytes(data), payload_size=len(data))


def test_archive_binding_mismatch_direct(common, apol):
    data = make_zip({"a.tex": b"x"})
    with pytest.raises(common.ReleaseError) as e:
        common.inspect_archive_bytes(data, apol, rule_id="r", payload_sha="0" * 64, payload_size=len(data))
    assert e.value.code == "archive_binding_mismatch"


def test_archive_excessive_entry_count_fails(common, apol, monkeypatch):
    monkeypatch.setattr(common, "MAX_ARCHIVE_ENTRIES", 2)
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, make_zip({"a.tex": b"1", "b.tex": b"2", "c.tex": b"3"}))
    assert e.value.code == "archive_too_many_entries"


def test_archive_total_name_bytes_fails(common, apol, monkeypatch):
    monkeypatch.setattr(common, "MAX_TOTAL_NAME_BYTES", 10)
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, make_zip({"aaaaa.tex": b"1", "bbbbb.tex": b"2"}))
    assert e.value.code == "archive_total_names_too_long"


def test_archive_name_length_fails(common, apol, monkeypatch):
    monkeypatch.setattr(common, "MAX_ENTRY_NAME_BYTES", 5)
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, make_zip({"toolongname.tex": b"1"}))
    assert e.value.code == "archive_name_too_long"


def test_archive_depth_fails(common, apol, monkeypatch):
    monkeypatch.setattr(common, "MAX_ARCHIVE_DEPTH", 2)
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, make_zip({"a/b/c/d.tex": b"1"}))
    assert e.value.code == "archive_depth"


def test_archive_duplicate_names_fail(common, apol):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("a.tex", b"1"); z.writestr("a.tex", b"2")
        data = buf.getvalue()
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, data)
    assert e.value.code == "archive_duplicate_name"


def test_archive_case_collision_fails(common, apol):
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, make_zip({"A.tex": b"1", "a.tex": b"2"}))
    assert e.value.code == "archive_case_collision"


def test_archive_absolute_name_fails(common, apol):
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, make_zip({"/etc/x.tex": b"1"}))
    assert e.value.code in {"archive_absolute", "archive_traversal"}


def test_archive_drive_name_fails(common, apol):
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, make_zip({"C:/x.tex": b"1"}))
    assert e.value.code in {"archive_drive", "archive_backslash"}


def test_archive_control_char_name_fails(common, apol):
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, make_zip({"bad\x01name.tex": b"1"}))
    assert e.value.code == "archive_control_char"


def test_archive_prohibited_nested_fails(common, apol):
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, make_zip({"inner/records.jsonl": b"1", "ok.tex": b"2"}))
    assert e.value.code == "archive_prohibited_nested"


def test_archive_nested_archive_fails(common, apol):
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, make_zip({"inner/child.zip": b"1"}))
    assert e.value.code == "archive_nested_archive"


def test_archive_unsupported_compression_fails(common, apol):
    try:
        data = make_bzip2_zip({"a.tex": b"payload" * 50})
    except Exception:
        pytest.skip("bz2 unavailable")
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, data)
    assert e.value.code == "archive_unsupported_compression"


def test_archive_comment_too_long_fails(common, apol, monkeypatch):
    monkeypatch.setattr(common, "MAX_ARCHIVE_COMMENT_BYTES", 4)
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, make_zip({"a.tex": b"1"}, comment=b"x" * 20))
    assert e.value.code == "archive_comment_too_long"


def test_archive_malformed_fails(common, apol):
    with pytest.raises(common.ReleaseError) as e:
        _inspect(common, apol, b"not a zip")
    assert e.value.code == "archive_malformed"


def test_archive_no_nested_content_extracted(common, apol, tmp_path):
    before = set(tmp_path.rglob("*"))
    _inspect(common, apol, make_zip({"a.tex": b"do-not-extract"}))
    assert set(tmp_path.rglob("*")) == before


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


def test_verify_invalid_enum_value_fail(verifier, common, built_zip, tmp_path, policy_file):
    def mut(it):
        m = json.loads(it["release-manifest.json"]); m["files"][0]["classification"] = "WEIRD"
        it["release-manifest.json"] = (json.dumps(m, indent=2, sort_keys=True) + "\n").encode()
        _resign(common, it)
    dst = tmp_path / "z.zip"; _repackage_full(common, built_zip, dst, mut)
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL"


def test_verify_unexpected_nested_field_fail(verifier, common, built_zip, tmp_path, policy_file):
    def mut(it):
        m = json.loads(it["release-manifest.json"]); m["repository"]["surprise"] = 1
        it["release-manifest.json"] = (json.dumps(m, indent=2, sort_keys=True) + "\n").encode()
        _resign(common, it)
    dst = tmp_path / "z.zip"; _repackage_full(common, built_zip, dst, mut)
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL" and any(f["code"] == "schema_unexpected_field" for f in r["findings"])


def test_verify_noncanonical_zip_policy_fail(verifier, common, built_zip, tmp_path, policy_file):
    def mut(it):
        m = json.loads(it["release-manifest.json"]); m["zip_policy"]["permissions"] = "0777"
        it["release-manifest.json"] = (json.dumps(m, indent=2, sort_keys=True) + "\n").encode()
        _resign(common, it)
    dst = tmp_path / "z.zip"; _repackage_full(common, built_zip, dst, mut)
    r = _vr(verifier, dst, policy_file)
    assert r["status"] == "FAIL" and any(f["code"] == "schema_value" for f in r["findings"])
