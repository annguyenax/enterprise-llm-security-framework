"""Phase 12G release builder + verifier tests. Synthetic fixtures only."""
from __future__ import annotations

import json
import os
import subprocess
import zipfile
from pathlib import Path

import pytest


def _build(builder, repo, out, **kw):
    return builder.build_release_candidate(repo_root=repo, output_dir=out, **kw)


# --------------------------------------------------------------------------- #
# Clean deterministic build + ZIP reopen verification
# --------------------------------------------------------------------------- #
def test_clean_deterministic_build(builder, verifier, synthetic_repo, tmp_path):
    summary = _build(builder, synthetic_repo, tmp_path / "out")
    assert summary["ok"] is True
    zip_path = Path(summary["zip_path"])
    assert zip_path.is_file()
    report = verifier.verify_release_candidate(zip_path)
    assert report["status"] == "PASS", report
    # Repo content is under repo/ ; control files present.
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
    assert "release-manifest.json" in names
    assert "repo/README.md" in names
    assert "repo/.env.example" in names  # template is allowed


def test_deterministic_zip_bytes(builder, synthetic_repo, tmp_path):
    one = _build(builder, synthetic_repo, tmp_path / "a")
    two = _build(builder, synthetic_repo, tmp_path / "b")
    assert one["zip_sha256"] == two["zip_sha256"]
    assert Path(one["zip_path"]).read_bytes() == Path(two["zip_path"]).read_bytes()


def test_expected_head_and_branch_enforced(builder, synthetic_repo, tmp_path, git):
    head = git("rev-parse", "HEAD").strip()
    ok = _build(builder, synthetic_repo, tmp_path / "ok", expected_head=head,
                base_sha="0" * 40)
    assert ok["ok"] is True
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, tmp_path / "bad", expected_head="1" * 40)
    assert exc.value.code == "identity_mismatch"


# --------------------------------------------------------------------------- #
# Fail-closed refusals
# --------------------------------------------------------------------------- #
def test_dirty_tree_refused(builder, synthetic_repo, tmp_path):
    (synthetic_repo / "README.md").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert exc.value.code == "dirty_tree"


def test_existing_output_refused(builder, synthetic_repo, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, out)
    assert exc.value.code == "output_reuse"


def test_tracked_jsonl_refused(builder, synthetic_repo, tmp_path, git):
    # Force-add a JSONL despite .gitignore, then commit -> tracked JSONL.
    (synthetic_repo / "records.jsonl").write_text('{"x":1}\n', encoding="utf-8")
    git("add", "-f", "records.jsonl")
    git("commit", "-q", "-m", "add jsonl")
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert exc.value.code == "tracked_jsonl"


def test_ignored_jsonl_excluded(builder, synthetic_repo, tmp_path):
    # A gitignored jsonl in the working tree must never be discovered/packaged.
    (synthetic_repo / "cases.jsonl").write_text('{"case":1}\n', encoding="utf-8")
    summary = _build(builder, synthetic_repo, tmp_path / "out")
    with zipfile.ZipFile(summary["zip_path"]) as z:
        assert not any(n.endswith(".jsonl") for n in z.namelist())


def test_tracked_result_json_refused(builder, synthetic_repo, tmp_path, git):
    (synthetic_repo / "result.json").write_text("{}\n", encoding="utf-8")
    git("add", "result.json")
    git("commit", "-q", "-m", "add result.json")
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert exc.value.code == "prohibited_artifact"


@pytest.mark.parametrize("name", ["real.db", "id_rsa", "server.pem", "credentials.json"])
def test_tracked_credential_and_database_refused(builder, synthetic_repo, tmp_path, git, name):
    (synthetic_repo / name).write_text("x\n", encoding="utf-8")
    git("add", "-f", name)
    git("commit", "-q", "-m", f"add {name}")
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert exc.value.code == "prohibited_artifact"


def test_real_dotenv_refused_but_example_allowed(builder, synthetic_repo, tmp_path, git):
    (synthetic_repo / ".env").write_text("SECRET=abc\n", encoding="utf-8")
    git("add", "-f", ".env")
    git("commit", "-q", "-m", "add .env")
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert exc.value.code == "prohibited_artifact"


# --------------------------------------------------------------------------- #
# Generated allowlist: path traversal, duplicate, mismatch
# --------------------------------------------------------------------------- #
def _gen_allowlist(tmp_path, entries):
    p = tmp_path / "gen.json"
    p.write_text(json.dumps({"schema_version": 1, "files": entries}), encoding="utf-8")
    return p


def test_generated_path_traversal_refused(builder, synthetic_repo, tmp_path):
    gen = _gen_allowlist(tmp_path, [{"path": "../escape.txt", "sha256": "0" * 64, "size_bytes": 1}])
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, tmp_path / "out", generated_allowlist=gen)
    assert exc.value.code in {"path_traversal", "path_absolute", "generated_allowlist"}


def test_generated_duplicate_of_tracked_refused(builder, synthetic_repo, tmp_path):
    gen = _gen_allowlist(tmp_path, [{"path": "README.md", "sha256": "0" * 64, "size_bytes": 1}])
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, tmp_path / "out", generated_allowlist=gen)
    assert exc.value.code in {"duplicate_logical_path", "generated_mismatch"}


def test_generated_mismatch_refused(builder, synthetic_repo, tmp_path):
    (synthetic_repo / "dep.txt").write_text("pkg==1.0\n", encoding="utf-8")  # untracked generated
    gen = _gen_allowlist(tmp_path, [{"path": "dep.txt", "sha256": "0" * 64, "size_bytes": 999}])
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, tmp_path / "out", generated_allowlist=gen)
    assert exc.value.code == "generated_mismatch"


# --------------------------------------------------------------------------- #
# Symlink / reparse rejection (where testable)
# --------------------------------------------------------------------------- #
def test_symlink_tracked_file_rejected(builder, synthetic_repo, tmp_path, git):
    real = synthetic_repo / "real.txt"
    real.write_text("real\n", encoding="utf-8")
    link = synthetic_repo / "link.txt"
    try:
        os.symlink(real, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted on this host")
    git("add", "-A")
    git("commit", "-q", "-m", "add symlink")
    with pytest.raises(builder.ReleaseError) as exc:
        _build(builder, synthetic_repo, tmp_path / "out")
    assert exc.value.code == "symlink_rejected"


# --------------------------------------------------------------------------- #
# Verifier: changed / missing / malformed / duplicate / NOT_VERIFIABLE
# --------------------------------------------------------------------------- #
def _repackage(zip_src: Path, zip_dst: Path, mutate):
    with zipfile.ZipFile(zip_src) as z:
        items = {i.filename: z.read(i.filename) for i in z.infolist()}
    mutate(items)
    with zipfile.ZipFile(zip_dst, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(items):
            z.writestr(name, items[name])


def test_verifier_detects_changed_file(builder, verifier, synthetic_repo, tmp_path):
    summary = _build(builder, synthetic_repo, tmp_path / "out")
    tampered = tmp_path / "tampered.zip"
    _repackage(Path(summary["zip_path"]), tampered,
               lambda items: items.__setitem__("repo/README.md", b"TAMPERED\n"))
    report = verifier.verify_release_candidate(tampered)
    assert report["status"] == "FAIL"
    assert any(f["code"] in {"changed_file", "manifest_mismatch"} for f in report["findings"])


def test_verifier_detects_missing_control_file(builder, verifier, synthetic_repo, tmp_path):
    summary = _build(builder, synthetic_repo, tmp_path / "out")
    stripped = tmp_path / "stripped.zip"
    _repackage(Path(summary["zip_path"]), stripped,
               lambda items: items.pop("release-manifest.json"))
    report = verifier.verify_release_candidate(stripped)
    assert report["status"] == "FAIL"
    assert any(f["code"] == "missing_control_file" for f in report["findings"])


def test_verifier_detects_malformed_manifest(builder, verifier, synthetic_repo, tmp_path):
    summary = _build(builder, synthetic_repo, tmp_path / "out")
    broken = tmp_path / "broken.zip"
    _repackage(Path(summary["zip_path"]), broken,
               lambda items: items.__setitem__("release-manifest.json", b"{not json"))
    report = verifier.verify_release_candidate(broken)
    assert report["status"] == "FAIL"
    assert any(f["code"] == "manifest_schema" for f in report["findings"])


def test_verifier_detects_jsonl_entry(builder, verifier, synthetic_repo, tmp_path):
    summary = _build(builder, synthetic_repo, tmp_path / "out")
    poisoned = tmp_path / "poisoned.zip"
    _repackage(Path(summary["zip_path"]), poisoned,
               lambda items: items.__setitem__("repo/records.jsonl", b'{"x":1}\n'))
    report = verifier.verify_release_candidate(poisoned)
    assert report["status"] == "FAIL"
    assert any(f["code"] in {"jsonl_present", "prohibited_present", "manifest_mismatch"}
               for f in report["findings"])


def test_verifier_not_verifiable_is_not_pass(verifier, tmp_path):
    # An archive with only control files and no repo payload -> NOT_VERIFIABLE.
    import scripts  # noqa: F401 - ensure sys.path unaffected
    from importlib import import_module  # noqa: F401
    manifest = {"schema_version": 1, "repo_head": "a" * 40, "base_sha": None, "files": []}
    manifest_bytes = (json.dumps(manifest) + "\n").encode("utf-8")
    files = {"release-manifest.json": manifest_bytes,
             "FILE_SIZES.json": b'{"schema_version":1,"files":{}}\n'}
    import hashlib
    sums = "".join(f"{hashlib.sha256(files[n]).hexdigest()}  {n}\n" for n in sorted(files))
    files["SHA256SUMS.txt"] = sums.encode("ascii")
    zpath = tmp_path / "empty.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            z.writestr(name, files[name])
    report = verifier.verify_release_candidate(zpath)
    assert report["status"] == "NOT_VERIFIABLE"
    assert report["passed"] is False


def test_verifier_does_not_modify_zip(builder, verifier, synthetic_repo, tmp_path):
    summary = _build(builder, synthetic_repo, tmp_path / "out")
    zip_path = Path(summary["zip_path"])
    before = zip_path.read_bytes()
    verifier.verify_release_candidate(zip_path)
    assert zip_path.read_bytes() == before


# --------------------------------------------------------------------------- #
# CLI surfaces
# --------------------------------------------------------------------------- #
def test_build_cli_content_free_status(builder, synthetic_repo, tmp_path):
    out = tmp_path / "cli.json"
    rc = builder.main(["--repo-root", str(synthetic_repo),
                       "--output-dir", str(tmp_path / "out"),
                       "--summary-out", str(out)])
    assert rc == 0
    summary = json.loads(out.read_text(encoding="utf-8"))
    assert summary["ok"] is True and "zip_sha256" in summary
