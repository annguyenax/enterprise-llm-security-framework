"""SQL guard: decide whether model-generated SQL may run for an actor.

Primary layer: SQLite's own compiler. The statement is prepared (EXPLAIN,
never executed) against an empty in-memory copy of the schema with an
authorizer that records every table/column READ and denies every other
action (writes, ATTACH, PRAGMA, DDL, unsafe functions). This sees through
aliases, CTEs, subqueries, UNIONs and `SELECT *`, which regex cannot.

Secondary layer: cheap lexical checks for stacked statements, comments and
dangerous keywords, so obvious payloads are rejected with a clear reason.
"""
from __future__ import annotations

import re
import sqlite3
from functools import lru_cache
from pathlib import Path

from app.core.decisions import Decision
from app.sql_agent.acl import FORBIDDEN_TABLES, permissions
from app.sql_agent.models import SqlActor, SqlGuardResult

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "datasets" / "furniture" / "sql" / "schema.sql"
MAX_SQL_CHARS = 2000
MAX_LIMIT = 50

SAFE_FUNCTIONS = frozenset({
    "count", "sum", "avg", "min", "max", "total", "group_concat", "lower", "upper",
    "length", "substr", "substring", "trim", "ltrim", "rtrim", "replace", "instr",
    "round", "abs", "coalesce", "ifnull", "nullif", "date", "time", "datetime",
    "strftime", "julianday", "iif", "like", "glob",
})

_LEXICAL_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"--|/\*|\*/|#"), "SQL comments are not allowed (comment smuggling)"),
    (re.compile(r"\b(attach|detach)\b", re.I), "ATTACH/DETACH is not allowed"),
    (re.compile(r"\bpragma\b", re.I), "PRAGMA is not allowed"),
    (re.compile(r"\bload_extension\b", re.I), "load_extension is not allowed"),
    (re.compile(r"\bwith\s+recursive\b", re.I), "recursive CTEs are not allowed (resource exhaustion)"),
    (re.compile(r"\b(insert|update|delete|drop|alter|create|replace\s+into|vacuum|reindex|analyze)\b", re.I),
     "only read-only SELECT statements are allowed"),
]
_LIMIT_RE = re.compile(r"\blimit\s+(\d+)(\s*(,|offset)\s*\d+)?\s*$", re.I)

_ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    getattr(sqlite3, "SQLITE_RECURSIVE", 33),
}


@lru_cache(maxsize=1)
def _schema_sql() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


def make_authorizer(allowed: frozenset[str], denied_cols: frozenset[str], log: list):
    """Build a sqlite3 authorizer enforcing the ACL. Reused by the executor."""

    def authorizer(action, arg1, arg2, _db, _trigger):
        if action == sqlite3.SQLITE_SELECT:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ:
            table = (arg1 or "").casefold()
            column = (arg2 or "").casefold()
            if table in FORBIDDEN_TABLES or table.startswith("pragma_"):
                log.append(f"table '{table}' is never readable")
                return sqlite3.SQLITE_DENY
            if table not in allowed:
                log.append(f"table '{table}' is not permitted for this actor")
                return sqlite3.SQLITE_DENY
            if column and f"{table}.{column}" in denied_cols:
                log.append(f"column '{table}.{column}' is not permitted for this actor")
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_FUNCTION:
            if (arg2 or "").casefold() in SAFE_FUNCTIONS:
                return sqlite3.SQLITE_OK
            log.append(f"function '{arg2}' is not allowed")
            return sqlite3.SQLITE_DENY
        if action in _ALLOWED_ACTIONS:
            return sqlite3.SQLITE_OK
        log.append(f"sqlite action {action} is not allowed (read-only)")
        return sqlite3.SQLITE_DENY

    return authorizer


def _block(reasons: list[str]) -> SqlGuardResult:
    return SqlGuardResult(decision=Decision.BLOCK, reasons=reasons or ["SQL rejected"])


def evaluate_sql(sql: str, actor: SqlActor) -> SqlGuardResult:
    if not isinstance(sql, str) or not sql.strip():
        return _block(["empty or non-string SQL"])
    if len(sql) > MAX_SQL_CHARS:
        return _block([f"SQL longer than {MAX_SQL_CHARS} characters"])
    allowed, denied_cols = permissions(actor)
    if not allowed:
        return _block(["unknown department/role: no tables permitted"])

    text = sql.strip()
    while text.endswith(";"):
        text = text[:-1].rstrip()
    if ";" in text:
        return _block(["multiple statements (stacked queries) are not allowed"])
    if not re.match(r"^\s*(select|with)\b", text, re.I):
        return _block(["only SELECT / WITH queries are allowed"])
    reasons = [reason for pattern, reason in _LEXICAL_RULES if pattern.search(text)]
    if reasons:
        return _block(reasons)

    log: list[str] = []
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(_schema_sql())
        reads: list[str] = []

        auth = make_authorizer(allowed, denied_cols, log)

        def recording(action, a1, a2, db, trig):
            if action == sqlite3.SQLITE_READ and a1:
                reads.append(a1.casefold())
            return auth(action, a1, a2, db, trig)

        conn.set_authorizer(recording)
        try:
            conn.execute("EXPLAIN " + text)
        except sqlite3.Warning:
            return _block(["multiple statements (stacked queries) are not allowed"])
        except sqlite3.DatabaseError as exc:
            if log:
                return _block(sorted(set(log)))
            return _block([f"SQL does not compile: {type(exc).__name__}"])
    finally:
        conn.close()
    if log:  # defensive: a denial that did not raise
        return _block(sorted(set(log)))

    tables = sorted(set(reads))
    match = _LIMIT_RE.search(text)
    if match is None or int(match.group(1)) > MAX_LIMIT:
        wrapped = f"SELECT * FROM ({text}) LIMIT {MAX_LIMIT}"
        return SqlGuardResult(
            decision=Decision.SANITIZE,
            reasons=[f"row limit enforced (LIMIT {MAX_LIMIT})"],
            normalized_sql=wrapped,
            tables_read=tables,
        )
    return SqlGuardResult(decision=Decision.ALLOW, normalized_sql=text, tables_read=tables)
