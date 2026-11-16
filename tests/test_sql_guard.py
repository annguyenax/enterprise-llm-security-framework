"""SQL guard tests (P4). No LLM, no network."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.decisions import Decision
from app.sql_agent.acl import permissions
from app.sql_agent.guard import evaluate_sql
from app.sql_agent.models import SqlActor

ROOT = Path(__file__).resolve().parents[1]


def _cases(name):
    lines = (ROOT / "redteam" / "sql" / name).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


DIRECT = _cases("p2sql-direct.jsonl")
BENIGN = _cases("p2sql-benign.jsonl")


def test_case_files_are_large_enough():
    assert len(DIRECT) >= 20 and len(BENIGN) >= 20
    assert len({c["attack_type"] for c in DIRECT}) >= 8


@pytest.mark.parametrize("case", DIRECT, ids=[c["id"] for c in DIRECT])
def test_attacks_are_blocked(case):
    result = evaluate_sql(case["model_sql"], SqlActor(case["department"], case["role"]))
    assert result.decision == Decision.BLOCK, result
    assert result.reasons
    assert result.normalized_sql is None


@pytest.mark.parametrize("case", BENIGN, ids=[c["id"] for c in BENIGN])
def test_benign_are_not_blocked(case):
    result = evaluate_sql(case["model_sql"], SqlActor(case["department"], case["role"]))
    assert result.decision in {Decision.ALLOW, Decision.SANITIZE}, result.reasons
    assert result.normalized_sql


@pytest.mark.parametrize(
    "dept,role,table,denied_col",
    [
        ("KinhDoanh", "member", "products", "dealer_price"),
        ("KinhDoanh", "leader", "customers", "phone"),
        ("KinhDoanh", "leader", "customers", "email"),
        ("KhoVan", "member", "products", "dealer_price"),
        ("KhoVan", "leader", "products", "dealer_price"),
        ("CSKH", "member", "products", "dealer_price"),
        ("KeToan", "member", "customers", "phone"),
        ("KeToan", "member", "customers", "email"),
        ("KinhDoanh", "member", "shipments", "address"),
        ("NhanSu", "member", "employees", "monthly_salary"),
    ],
)
def test_denied_columns_per_acl_row(dept, role, table, denied_col):
    actor = SqlActor(dept, role)
    assert evaluate_sql(f"SELECT {denied_col} FROM {table} LIMIT 5", actor).decision == Decision.BLOCK
    assert evaluate_sql(f"SELECT * FROM {table} LIMIT 5", actor).decision == Decision.BLOCK


@pytest.mark.parametrize(
    "dept,role",
    [("KinhDoanh", "member"), ("KinhDoanh", "leader"), ("KhoVan", "member"),
     ("KhoVan", "leader"), ("CSKH", "member"), ("KeToan", "member"),
     ("NhanSu", "member"), ("NhanSu", "leader"), ("IT", "member")],
)
def test_allowed_tables_readable_and_others_not(dept, role):
    actor = SqlActor(dept, role)
    allowed, denied = permissions(actor)
    every = {"branches", "warehouses", "products", "inventory", "customers", "orders",
             "order_items", "suppliers", "receivables", "product_reviews", "employees",
             "promotions", "shipments", "warranty_claims", "support_tickets"}
    for table in every:
        result = evaluate_sql(f"SELECT count(*) FROM {table} LIMIT 1", actor)
        expected = Decision.ALLOW if table in allowed else Decision.BLOCK
        assert result.decision == expected, (table, result.reasons)
    assert evaluate_sql("SELECT value FROM internal_secrets LIMIT 1", actor).decision == Decision.BLOCK


def test_unknown_actor_gets_nothing():
    assert evaluate_sql("SELECT name FROM products LIMIT 1", SqlActor("Marketing", "member")).decision == Decision.BLOCK
    assert evaluate_sql("SELECT name FROM products LIMIT 1", SqlActor(["x"], "member")).decision == Decision.BLOCK


def test_leader_inherits_member_when_not_listed():
    assert evaluate_sql("SELECT sku FROM products LIMIT 1", SqlActor("CSKH", "leader")).decision == Decision.ALLOW


@pytest.mark.parametrize("sql", [None, "", "   ", 42, ["SELECT 1"]])
def test_non_string_or_empty_rejected(sql):
    assert evaluate_sql(sql, SqlActor("KinhDoanh", "member")).decision == Decision.BLOCK


def test_too_long_rejected():
    sql = "SELECT name FROM products WHERE name = '" + "a" * 2100 + "' LIMIT 1"
    assert evaluate_sql(sql, SqlActor("KinhDoanh", "member")).decision == Decision.BLOCK


@pytest.mark.parametrize("sql", ["SELECT name FROM products", "SELECT name FROM products LIMIT 500"])
def test_limit_enforced_by_wrapping(sql):
    result = evaluate_sql(sql, SqlActor("KinhDoanh", "member"))
    assert result.decision == Decision.SANITIZE
    assert result.normalized_sql.endswith("LIMIT 50")


def test_trailing_semicolon_is_tolerated():
    result = evaluate_sql("SELECT name FROM products LIMIT 3;", SqlActor("KinhDoanh", "member"))
    assert result.decision == Decision.ALLOW
    assert ";" not in result.normalized_sql


def test_semicolon_inside_string_is_still_rejected_conservatively():
    # Lab trade-off: any inner ';' is treated as stacking, even inside a literal.
    result = evaluate_sql("SELECT name FROM products WHERE name = 'a;b' LIMIT 1", SqlActor("KinhDoanh", "member"))
    assert result.decision == Decision.BLOCK
