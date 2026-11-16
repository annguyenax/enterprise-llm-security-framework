# Task C — SQL agent + SQL guard (P2SQL defense)

Read first: CLAUDE.md, AGENT_RULES.md, docs/p4-claude-sql/00_CONTRACT.md (ACL table + interfaces).
Task B fills seed data in parallel; build your OWN tiny fixture DB in tests from
`datasets/furniture/sql/schema.sql` + a few INSERTs. Do not depend on seed.sql.

Implement package `app/sql_agent/` exactly per contract:
- `models.py`: `SqlActor(department, role)`, `SqlGuardResult`.
- `guard.py` `evaluate_sql`: stdlib only. Use `sqlite3` itself to help: open an in-memory DB with the
  schema and use `sqlite3.Connection.set_authorizer` to learn every table/column the statement
  READS (SQLITE_READ) and reject any non-SELECT action. This is more robust than regex parsing —
  regex is a secondary layer only (stacked `;`, comments, ATTACH, PRAGMA, load_extension).
  `SELECT *` on a table with denied columns -> BLOCK (authorizer will report the denied column).
  Missing/ > 50 LIMIT -> SANITIZE by wrapping `SELECT * FROM (<sql>) LIMIT 50`.
- `executor.py`: guarded = `file:{path}?mode=ro` + `PRAGMA query_only=ON` + authorizer still on +
  progress handler timeout + row cap. Unguarded = `sqlite3.connect(':memory:')` + `backup()` copy;
  execute with `executescript` allowed (that IS the vulnerable baseline), never touch the file.
- `result_guard.py`: run text cells through existing rag_guard (as context chunks) and DLP/output guard;
  sanitize/withhold cells, record reasons.
- `agent.py`: prompt provider for one ```sql block (Vietnamese system prompt listing ONLY the tables the
  actor may see in guarded mode; full schema in unguarded mode), extract, guard, execute, result-guard,
  ask provider for final Vietnamese answer, run existing Output Guard. Input Guard runs first on the question.
  Must work with any BaseLLMProvider; tests use a scripted fake provider.
- `app/api/sql_routes.py`: `POST /v1/sql/chat` and `POST /v1/unguarded/sql/chat`
  body `{question, department, role}`; response includes generated_sql, sql_guard decision+reasons,
  rows (capped), result_guard reasons, answer, final_decision. Audit via existing audit_logger.
  Do NOT edit app/main.py (leader includes the router).
- `redteam/sql/p2sql-direct.jsonl` (>= 20) and `redteam/sql/p2sql-benign.jsonl` (>= 20): question,
  department, role, expected decision, attack_type (union exfil, stacked DROP, comment smuggling,
  internal_secrets, pragma/sqlite_master, ACL column bypass, tautology, Vietnamese social engineering).

Tests: `tests/test_sql_guard.py` (every attack class blocked; every benign allowed; ACL per row of table),
`tests/test_sql_agent.py` (fake provider: direct P2SQL blocked in guarded, succeeds in unguarded copy
WITHOUT modifying source DB file; indirect payload in orders.note is sanitized before 2nd provider call).

Write `docs/p4-claude-sql/report-C.md` per contract template.
