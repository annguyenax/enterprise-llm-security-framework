"""Regression: unguarded A/B must read the ``response`` field (Code X P0)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "run_demo_ab_paired.py"


def _load():
    spec = importlib.util.spec_from_file_location("run_demo_ab_paired", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_extract_unguarded_answer_prefers_response_field():
    mod = _load()
    canary = "FLAG{DEMO-KB-CANARY-7F3A9}"
    body = {
        "response": f"Day la bang luong\n{canary}\n",
        "answer": None,
        "content": None,
        "guards_enabled": False,
    }
    text = mod._extract_unguarded_answer(body)
    assert canary in text
    assert mod._extract_unguarded_answer({"answer": "nope", "response": canary}) == canary
    assert mod._extract_unguarded_answer({}) == ""


def test_extract_does_not_miss_leak_when_only_response_present():
    """Pre-fix bug: only looking at answer/content missed real leaks."""
    mod = _load()
    canary = "FLAG{DEMO-KB-CANARY-7F3A9}"
    # Old broken path would return ""
    body = {"response": f"secret {canary}", "provider_name": "ollama"}
    assert canary in mod._extract_unguarded_answer(body)
