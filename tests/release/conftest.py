"""Synthetic fixtures for Phase 12G release tests. No real benchmark records."""
from __future__ import annotations

import importlib.util
import io
import json
import struct
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

import pytest

ROOT = Path(__file__).resolve().parents[2]
RELEASE_DIR = ROOT / "scripts" / "release"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, RELEASE_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def common():
    return _load("release_common", "release_common.py")


@pytest.fixture(scope="session")
def verifier(common):
    return _load("verify_release_candidate", "verify_release_candidate.py")


@pytest.fixture(scope="session")
def builder(verifier):
    return _load("g12_build_release", "build_release_candidate.py")


_PROHIBITED = {
    "extensions": [".jsonl", ".db", ".sqlite", ".sqlite3", ".pem", ".key", ".p12", ".pfx"],
    "exact_names": ["result.json", "credentials.json", "credential.json",
                    "secrets.json", "id_rsa", "id_ed25519"],
    "env": {"prohibit_dotenv": True, "allow_exceptions": [".env.example", ".env.sample", ".env.template"]},
    "path_components": [".git", ".venv", "venv", "env", "__pycache__",
                       ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules",
                       ".idea", ".vscode", ".tmp", ".pytest-tmp"],
    "archive_extensions": [".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".zst", ".7z", ".rar"],
}


def valid_policy_obj(required_paths, *, allowed_archives=None, extra_extensions=None,
                     extra_exact_names=None, extra_rules=None):
    """A minimal valid, mechanically disjoint schema-4 policy as a dict.
    Extension rules automatically exclude any required path with that extension."""
    required_paths = list(required_paths)
    exts = [".md", ".py", ".txt", ".json"] + list(extra_extensions or [])
    names = [".gitignore", ".gitkeep", ".env.example"] + list(extra_exact_names or [])
    rules = []
    for i, p in enumerate(required_paths):
        rules.append({"rule_id": f"req-{i}", "class": "REQUIRED", "form": "exact_path",
                      "value": p, "exclude_exact_paths": []})
    for e in exts:
        excl = [p for p in required_paths if PurePosixPath(p).suffix.casefold() == e.casefold()]
        rules.append({"rule_id": f"allow-ext-{e[1:]}", "class": "ALLOWED", "form": "extension",
                      "value": e, "exclude_exact_paths": excl})
    for nm in names:
        rid = "allow-name-" + nm.strip(".").replace(".", "-")
        rules.append({"rule_id": rid, "class": "ALLOWED", "form": "exact_name",
                      "value": nm, "exclude_exact_paths": []})
    for i, a in enumerate(allowed_archives or []):
        rules.append({"rule_id": a.get("rule_id", f"allow-arch-{i}"), "class": "ALLOWED_ARCHIVE",
                      "form": "archive_path", "value": a["path"], "exclude_exact_paths": []})
    rules += list(extra_rules or [])
    return {
        "schema_version": 4,
        "policy_id": "phase12g-test-policy-v4",
        "fail_closed": True,
        "closed_world": True,
        "disjoint": True,
        "source_of_truth": "git ls-files (tracked) plus explicit generated allowlist",
        "archive_inspection_version": 1,
        "inclusion_rules": rules,
        "prohibited": json.loads(json.dumps(_PROHIBITED)),
        "optional_generated": {"allowed": True, "note": "generated files remain classified"},
    }


def valid_policy(required_paths, **kw):
    return json.dumps(valid_policy_obj(required_paths, **kw), indent=2)


def write_policy(repo: Path, obj) -> None:
    (repo / "release" / "release-allowlist.json").write_text(
        json.dumps(obj, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Synthetic-archive helpers (Phase G). Names/metadata only; no real archive.
# --------------------------------------------------------------------------- #
def make_zip(members: dict, *, compression=zipfile.ZIP_DEFLATED, comment=b"") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=compression) as z:
        for name, data in members.items():
            z.writestr(name, data)
        if comment:
            z.comment = comment
    return buf.getvalue()


def make_bzip2_zip(members: dict) -> bytes:
    return make_zip(members, compression=zipfile.ZIP_BZIP2)


def make_encrypted_zip(name: str, data: bytes) -> bytes:
    """Build a one-entry ZIP and set the encryption bit (flag 0x0001) in the
    local and central headers so readers see it as encrypted."""
    raw = bytearray(make_zip({name: data}, compression=zipfile.ZIP_STORED))
    off = raw.find(b"PK\x03\x04")
    if off != -1:
        pos = off + 6
        flag = struct.unpack_from("<H", raw, pos)[0] | 0x0001
        struct.pack_into("<H", raw, pos, flag)
    coff = raw.find(b"PK\x01\x02")
    if coff != -1:
        pos = coff + 8
        flag = struct.unpack_from("<H", raw, pos)[0] | 0x0001
        struct.pack_into("<H", raw, pos, flag)
    return bytes(raw)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo),
         "-c", "user.email=phase12g@example.invalid", "-c", "user.name=Phase12G Test",
         "-c", "commit.gpgsign=false", *args],
        capture_output=True, text=True, check=True,
    ).stdout


@pytest.fixture()
def synthetic_repo(tmp_path):
    """A committed git repo whose every tracked file matches exactly one
    disjoint inclusion rule under the schema-4 policy."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / ".gitignore").write_text("*.jsonl\n.env\n*.db\n.venv/\n", encoding="utf-8")
    (repo / "README.md").write_text("# Synthetic repo\n", encoding="utf-8")
    (repo / "notes.txt").write_text("notes\n", encoding="utf-8")
    (repo / ".env.example").write_text("TOKEN=REPLACE_ME\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
    (repo / "release").mkdir()
    required = ["release/release-allowlist.json", "release/release-policy.md"]
    (repo / "release" / "release-allowlist.json").write_text(valid_policy(required), encoding="utf-8")
    (repo / "release" / "release-policy.md").write_text("# policy\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")
    return repo


@pytest.fixture()
def git(synthetic_repo):
    def _call(*args: str) -> str:
        return _git(synthetic_repo, *args)
    return _call


@pytest.fixture()
def policy_file(synthetic_repo):
    """The EXTERNAL trusted policy file (the tracked policy in the synthetic repo)."""
    return synthetic_repo / "release" / "release-allowlist.json"
