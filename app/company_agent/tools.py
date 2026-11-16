"""Tool registry for the company assistant.

Every tool returns plain text for the model. Read tools never mutate data.
Write tools (create_ticket, send_email) are SIMULATED: in guarded mode they
are queued for human approval; in unguarded mode they are "executed" into an
in-memory outbox. Nothing ever leaves the process.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.company_agent import docs as docstore
from app.sql_agent.executor import SqlExecutionError, run_guarded, run_unguarded
from app.sql_agent.guard import evaluate_sql
from app.sql_agent.models import SqlActor, SqlExecution

ORDER_ID = re.compile(r"^DH-\d{4}-\d{5}$")
CUSTOMER_ID = re.compile(r"^KH-\d{4}$")
INTERNAL_EMAIL = re.compile(r"^[a-z0-9._-]+@example\.test$")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    kind: str  # "read" | "write"
    description: str
    args: dict[str, str]
    departments: frozenset[str] | None  # None = every department


TOOLS: dict[str, ToolSpec] = {
    "search_docs": ToolSpec("search_docs", "read", "Tìm tài liệu nội bộ (chính sách, quy trình).",
                            {"query": "từ khoá"}, None),
    "query_db": ToolSpec("query_db", "read", "Chạy MỘT câu SQLite SELECT trên dữ liệu được phép.",
                         {"sql": "câu SELECT có LIMIT"}, None),
    "order_status": ToolSpec("order_status", "read", "Tra trạng thái đơn hàng và vận đơn theo mã DH-YYYY-NNNNN.",
                             {"order_id": "DH-YYYY-NNNNN"}, frozenset({"kinhdoanh", "cskh", "khovan"})),
    "create_ticket": ToolSpec("create_ticket", "write", "Tạo ticket CSKH (cần người duyệt).",
                              {"customer_id": "KH-NNNN", "subject": "tiêu đề", "content": "nội dung"},
                              frozenset({"cskh", "kinhdoanh"})),
    "send_email": ToolSpec("send_email", "write", "Gửi email nội bộ @example.test (cần người duyệt).",
                           {"to": "địa chỉ", "subject": "tiêu đề", "body": "nội dung"}, None),
}


def tool_allowed(name: str, department: str) -> bool:
    spec = TOOLS.get(name)
    if spec is None:
        return False
    return spec.departments is None or department.casefold() in spec.departments


def validate_args(name: str, args: dict) -> list[str]:
    spec = TOOLS[name]
    errors = []
    if not isinstance(args, dict):
        return ["args must be an object"]
    extra = set(args) - set(spec.args)
    missing = set(spec.args) - set(args)
    if extra:
        errors.append(f"unexpected args: {sorted(extra)}")
    if missing:
        errors.append(f"missing args: {sorted(missing)}")
    for key, value in args.items():
        if not isinstance(value, str) or len(value) > 2000:
            errors.append(f"arg {key!r} must be a string <= 2000 chars")
    if errors:
        return errors
    if name == "order_status" and not ORDER_ID.match(args["order_id"]):
        errors.append("order_id format invalid")
    if name == "create_ticket" and not CUSTOMER_ID.match(args["customer_id"]):
        errors.append("customer_id format invalid")
    if name == "send_email" and not INTERNAL_EMAIL.match(args["to"].strip().casefold()):
        errors.append("recipient must be an internal @example.test address")
    return errors


def run_search_docs(args: dict, *, corpus: str, actor: SqlActor, enforce_acl: bool) -> list[tuple[str, str]]:
    hits = docstore.search(args.get("query", ""), kind=corpus, department=actor.department,
                           role=actor.role, enforce_acl=enforce_acl)
    return [(d.filename, d.body[: docstore.MAX_DOC_CHARS]) for d in hits]


def run_query_db(args: dict, *, db: Path, actor: SqlActor, guarded: bool):
    """Return (SqlExecution | None, guard_reasons, executed_sql)."""
    sql = args.get("sql", "")
    if not guarded:
        return run_unguarded(db, sql), [], sql
    verdict = evaluate_sql(sql, actor)
    if verdict.normalized_sql is None:
        return None, verdict.reasons, None
    return run_guarded(db, verdict.normalized_sql, actor), verdict.reasons, verdict.normalized_sql


def run_order_status(args: dict, *, db: Path, actor: SqlActor, guarded: bool) -> SqlExecution:
    """Parameterized lookup: the safe alternative to free-form text-to-SQL."""
    order_id = args.get("order_id", "")
    show_address = (not guarded) or actor.department.casefold() in {"khovan", "cskh"}
    cols = "o.order_id, o.status, o.created_at, o.total_vnd, s.carrier, s.status, s.scheduled_date"
    if show_address:
        cols += ", s.address"
    if not Path(db).is_file():
        raise SqlExecutionError("furniture database is not built")
    conn = sqlite3.connect(Path(db).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        cur = conn.execute(
            f"SELECT {cols}, o.note FROM orders o LEFT JOIN shipments s ON s.order_id = o.order_id "
            "WHERE o.order_id = ? LIMIT 1",
            (order_id,),
        )
        rows = [list(r) for r in cur.fetchall()]
        columns = [d[0] for d in cur.description]
    finally:
        conn.close()
    return SqlExecution(columns=columns, rows=rows)
