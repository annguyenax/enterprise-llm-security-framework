"""Execute SQL against the furniture database.

Guarded path: read-only URI, `PRAGMA query_only`, the same ACL authorizer as
the guard (defense in depth), a time budget and a row cap.

Unguarded lab path: the INTENTIONALLY vulnerable baseline. It runs whatever
the model produced, stacked statements included, but always against a
throw-away in-memory copy, so destructive SQL is demonstrable without ever
modifying the source database file.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from app.sql_agent.acl import permissions
from app.sql_agent.guard import make_authorizer
from app.sql_agent.models import SqlActor, SqlExecution

MAX_ROWS = 50
TIME_BUDGET_SECONDS = 2.0


class SqlExecutionError(RuntimeError):
    """Execution failed; message is safe to show (no paths, no raw errors)."""


def _ro_uri(db_path: Path) -> str:
    return Path(db_path).resolve().as_uri() + "?mode=ro"


def _deadline_handler(deadline: float):
    def handler():
        return 1 if time.monotonic() > deadline else 0

    return handler


def run_guarded(db_path: Path, sql: str, actor: SqlActor, max_rows: int = MAX_ROWS) -> SqlExecution:
    if not Path(db_path).is_file():
        raise SqlExecutionError("furniture database is not built")
    conn = sqlite3.connect(_ro_uri(db_path), uri=True)
    try:
        conn.execute("PRAGMA query_only = ON")
        allowed, denied = permissions(actor)
        log: list[str] = []
        conn.set_authorizer(make_authorizer(allowed, denied, log))
        conn.set_progress_handler(_deadline_handler(time.monotonic() + TIME_BUDGET_SECONDS), 1000)
        try:
            cur = conn.execute(sql)
            rows = cur.fetchmany(max_rows + 1)
        except sqlite3.DatabaseError as exc:
            reason = "; ".join(sorted(set(log))) or type(exc).__name__
            raise SqlExecutionError(f"query rejected at execution: {reason}") from None
        columns = [d[0] for d in cur.description or []]
    finally:
        conn.close()
    return SqlExecution(
        columns=columns,
        rows=[list(r) for r in rows[:max_rows]],
        truncated=len(rows) > max_rows,
    )


def _split_statements(sql: str) -> list[str]:
    statements, buf = [], ""
    for ch in sql:
        buf += ch
        if ch == ";" and sqlite3.complete_statement(buf):
            if buf.strip(" ;\n\t"):
                statements.append(buf.strip())
            buf = ""
    if buf.strip():
        statements.append(buf.strip())
    return statements


def run_unguarded(db_path: Path, sql: str, max_rows: int = MAX_ROWS) -> SqlExecution:
    if not Path(db_path).is_file():
        raise SqlExecutionError("furniture database is not built")
    source = sqlite3.connect(_ro_uri(db_path), uri=True)
    mem = sqlite3.connect(":memory:")
    try:
        source.backup(mem)
    finally:
        source.close()
    try:
        schema_before = mem.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name").fetchall()
        mem.set_progress_handler(_deadline_handler(time.monotonic() + TIME_BUDGET_SECONDS), 1000)
        columns: list[str] = []
        rows: list = []
        executed = 0
        for statement in _split_statements(sql):
            try:
                cur = mem.execute(statement)
            except sqlite3.DatabaseError as exc:
                raise SqlExecutionError(f"statement {executed + 1} failed: {type(exc).__name__}") from None
            executed += 1
            if cur.description:
                columns = [d[0] for d in cur.description]
                rows = cur.fetchmany(max_rows + 1)
        mem.set_progress_handler(None, 0)
        schema_after = mem.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name").fetchall()
        # total_changes misses DDL (DROP/ALTER), so compare the schema too.
        modified = mem.total_changes > 0 or schema_after != schema_before
    finally:
        mem.close()
    return SqlExecution(
        columns=columns,
        rows=[list(r) for r in rows[:max_rows]],
        truncated=len(rows) > max_rows,
        statements_executed=executed,
        database_modified=modified,
    )
