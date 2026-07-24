"""Synthetic fixtures for Phase 12G release tests. No real benchmark records."""
from __future__ import annotations

import importlib.util
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
def builder():
    return _load("g12_build_release", "build_release_candidate.py")


@pytest.fixture(scope="session")
def verifier():
    return _load("g12_verify_release", "verify_release_candidate.py")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo),
         "-c", "user.email=phase12g@example.invalid",
         "-c", "user.name=Phase12G Test",
         "-c", "commit.gpgsign=false",
         *args],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


@pytest.fixture()
def synthetic_repo(tmp_path):
    """A small committed git repo with tracked source + docs and a .gitignore."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / ".gitignore").write_text("*.jsonl\n.env\n*.db\n.venv/\n", encoding="utf-8")
    (repo / "README.md").write_text("# Synthetic repo\n", encoding="utf-8")
    (repo / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (repo / ".env.example").write_text("TOKEN=REPLACE_ME\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    manifests = repo / "datasets" / "v2" / "manifests"
    manifests.mkdir(parents=True)
    (manifests / "benchmark-v2-manifest.json").write_text('{"manifest_status":"final"}\n', encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")
    return repo


@pytest.fixture()
def git(synthetic_repo):
    def _call(*args: str) -> str:
        return _git(synthetic_repo, *args)
    return _call
