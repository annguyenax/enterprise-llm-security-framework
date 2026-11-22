"""Integrity tests for the synthetic furniture dataset (P4)."""
from __future__ import annotations

import importlib.util
import json
import re
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "datasets" / "furniture"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


KEYCOL = {"orders": "order_id", "product_reviews": "review_id", "support_tickets": "ticket_id",
          "warranty_claims": "claim_id", "shipments": "shipment_id", "suppliers": "supplier_id",
          "customers": "customer_id"}


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    out = tmp_path_factory.mktemp("furniture") / "furniture.db"
    counts = _load("build_furniture_db").build(out)
    conn = sqlite3.connect(out)
    yield conn, counts, out
    conn.close()


@pytest.fixture(scope="module")
def manifest():
    return json.loads((DS / "manifest.json").read_text(encoding="utf-8"))


def test_every_table_has_rows(db):
    _, counts, _ = db
    assert all(n > 0 for n in counts.values()), counts


def test_foreign_keys_hold(db):
    conn, _, _ = db
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_build_refuses_overwrite_without_force(db):
    _, _, out = db
    with pytest.raises(FileExistsError):
        _load("build_furniture_db").build(out)


def test_seed_is_deterministic(tmp_path, monkeypatch):
    gen = _load("generate_furniture_seed")
    before = (DS / "sql" / "seed.sql").read_bytes()
    monkeypatch.setattr(gen, "OUT_SQL", tmp_path / "seed.sql")
    monkeypatch.setattr(gen, "OUT_MANIFEST", tmp_path / "manifest.json")
    gen.main()
    assert (tmp_path / "seed.sql").read_bytes() == before
    assert (tmp_path / "manifest.json").read_bytes() == (DS / "manifest.json").read_bytes()


def test_pii_is_synthetic(db):
    conn, _, _ = db
    for phone, email in conn.execute("SELECT phone, email FROM customers"):
        assert email.endswith("@example.test")
        assert re.fullmatch(r"09\d\d-000-\d{3}", phone)


def test_secrets_are_fake_markers_only(db):
    conn, _, _ = db
    values = [v for (v,) in conn.execute("SELECT value FROM internal_secrets")]
    assert values and all(re.fullmatch(r"FAKE-SECRET-\d{4}-EXAMPLE", v) for v in values)


def test_manifest_row_fixtures_resolve(db, manifest):
    conn, _, _ = db
    rows = [e for e in manifest["entries"] if e["kind"] in {"attack_row", "benign_row"}]
    keycol = KEYCOL
    for e in rows:
        val = conn.execute(
            f"SELECT {e['column']} FROM {e['table']} WHERE {keycol[e['table']]} = ?", (e["key"],)
        ).fetchone()
        assert val and val[0].strip(), e["id"]


def test_attack_rows_diverse_and_split(manifest):
    attacks = [e for e in manifest["entries"] if e["kind"] == "attack_row"]
    benign = [e for e in manifest["entries"] if e["kind"] == "benign_row"]
    assert len(attacks) >= 30 and len(benign) >= 30
    assert len({e["attack_type"] for e in attacks}) >= 20
    assert len({e["table"] for e in attacks}) >= 6
    assert {e["split"] for e in attacks} == {"dev", "holdout"}


def test_planted_rows_do_not_collide(manifest):
    keys = [(e["table"], e["key"]) for e in manifest["entries"] if e["kind"] in {"attack_row", "benign_row"}]
    assert len(keys) == len(set(keys))


def test_docs_resolve_and_poisoned_are_paired(manifest):
    docs = [e for e in manifest["entries"] if e["kind"] in {"clean", "poisoned"}]
    clean_ids = {e["id"] for e in docs if e["kind"] == "clean"}
    assert len(clean_ids) >= 15
    poisoned = [e for e in docs if e["kind"] == "poisoned"]
    assert len(poisoned) >= 14
    for e in docs:
        assert (ROOT / e["path"]).is_file()
    for e in poisoned:
        assert e["paired_with"] in clean_ids
        assert e["attack_type"]


def test_ids_unique(manifest):
    ids = [e["id"] for e in manifest["entries"]]
    assert len(ids) == len(set(ids))
