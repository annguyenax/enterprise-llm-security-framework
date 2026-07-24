"""Synthetic fixtures for Phase 12G release tests. No real benchmark records."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

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
    return _load("g12_release_common", "release_common.py")


@pytest.fixture(scope="session")
def builder():
    return _load("g12_build_release", "build_release_candidate.py")


@pytest.fixture(scope="session")
def verifier():
    return _load("g12_verify_release", "verify_release_candidate.py")


def valid_policy(required_present):
    """A minimal valid schema-2 policy JSON string."""
    return json.dumps({
        "schema_version": 2,
        "policy_id": "phase12g-test-policy-v2",
        "fail_closed": True,
        "prohibited": {
            "extensions": [".jsonl", ".db", ".sqlite", ".sqlite3", ".pem", ".key", ".p12", ".pfx"],
            "exact_names": ["result.json", "credentials.json", "credential.json",
                            "secrets.json", "id_rsa", "id_ed25519"],
            "env": {"prohibit_dotenv": True, "allow_exceptions": [".env.example", ".env.sample", ".env.template"]},
            "path_components": [".git", ".venv", "venv", "env", "__pycache__",
                               ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules",
                               ".idea", ".vscode", ".tmp", ".pytest-tmp"],
        },
        "required_present": list(required_present),
        "optional_generated": {"allowed": True},
    }, indent=2)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo),
         "-c", "user.email=phase12g@example.invalid", "-c", "user.name=Phase12G Test",
         "-c", "commit.gpgsign=false", *args],
        capture_output=True, text=True, check=True,
    ).stdout


@pytest.fixture()
def synthetic_repo(tmp_path):
    """A committed git repo with tracked source/docs, a .gitignore, and a valid
    machine-consumable release policy that references only files it contains."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / ".gitignore").write_text("*.jsonl\n.env\n*.db\n.venv/\n", encoding="utf-8")
    (repo / "README.md").write_text("# Synthetic repo\n", encoding="utf-8")
    (repo / "requirements.txt").write_text("pytest\n", encoding="utf-8")
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
