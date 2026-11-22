# P4 — Claude provider + Furniture dataset + SQL guard: CONTRACT

Owner: leader (Claude, chat session). Workers: Codex via Agent Orchestrator.
Base branch: `feat/claude-provider-sql-guard`. Lab-scale PoC, synthetic data only.

## Goal (đồ án)
2x2 matrix: {qwen3 local (Ollama), Claude Sonnet 5.5 (cloud)} x {unguarded, guarded}
for (a) RAG data poisoning and (b) SQL injection / P2SQL (prompt-to-SQL injection,
direct and indirect). Claim to support: "security is in the gateway, not the model".
NO numbers are produced in this phase. No paid API calls (AGENT_RULES rule 4).

## Hard rules for every worker
1. Read `CLAUDE.md` and `AGENT_RULES.md` first. They win over this file.
2. NEVER touch `datasets/v2/**`, `datasets/v3/**`, holdout files, `.env`.
3. No new packages (stdlib + what is already in requirements.txt only).
4. No network calls in tests. No real API key anywhere. No paid API call at all.
5. Only edit the files listed in YOUR task. Anything else -> write it in your report.
6. Do not push, do not open PRs, do not merge. Commit only on your own task branch.
7. Run `pytest -q` on your new tests + `tests/test_llm_provider.py tests/test_gateway_provider.py`
   and paste the real output in your report. Do not claim PASS/DONE; leader + maintainer decide.
8. Synthetic only: fictional company "Nha Moc Viet Lab", `@example.test` emails,
   phones `09xx-000-xxx`, fake markers like `FAKE-SECRET-0000-EXAMPLE`.

## Shared interfaces
### Env vars (`.env.example` gets placeholders only)
- `LLM_PROVIDER=anthropic` | `ollama` | `mock` (default mock)
- `LLM_MODEL_NAME=claude-sonnet-5-5` (when anthropic)
- `ANTHROPIC_API_KEY=` (placeholder only)
- `ANTHROPIC_BASE_URL=https://api.anthropic.com`
- `ANTHROPIC_MAX_TOKENS=1024`
- `FURNITURE_DB_PATH=data/furniture.db`

### Provider (Worker A)
`app/services/providers/anthropic.py` registers `"anthropic"` via `register_provider`
and implements `BaseLLMProvider.generate(LLMProviderRequest) -> LLMProviderResponse`
with the SAME system-prompt semantics as `ollama.py` (guarded vs `unguarded_lab`),
so the A/B comparison is not confounded by different prompts.

### Database (Worker B fills, schema frozen by leader)
- Schema: `datasets/furniture/sql/schema.sql` (DO NOT rename tables/columns).
- Seed: `datasets/furniture/sql/seed.sql`.
- Builder: `scripts/build_furniture_db.py --out data/furniture.db` (deterministic, idempotent).
- Role/column sensitivity is defined in the schema comments and in the ACL table below.

### ACL used by SQL guard (Worker C implements, Worker B must make data exercise it)
| department  | role    | allowed tables (SELECT only)                                         | denied columns |
|-------------|---------|----------------------------------------------------------------------|----------------|
| KinhDoanh   | member  | products, inventory, orders, order_items, branches, product_reviews  | products.dealer_price, customers.* |
| KinhDoanh   | leader  | + customers                                                           | customers.phone, customers.email |
| KhoVan      | member  | products, inventory, warehouses, branches                             | products.dealer_price |
| KhoVan      | leader  | + suppliers                                                           | — |
| CSKH        | member  | products, orders, order_items, product_reviews, customers             | products.dealer_price |
| KeToan      | member  | orders, order_items, receivables, products, customers, suppliers      | customers.phone, customers.email |
| (v1.1)      |         | Bảng đầy đủ v1.1 (thêm shipments, warranty_claims, support_tickets, promotions, employees; phòng NhanSu, IT) xem `app/sql_agent/acl.py` | |
| any         | any     | NEVER: internal_secrets, sqlite_master/sqlite_schema, pragma_*        | — |

### SQL agent (Worker C)
Package `app/sql_agent/`:
- `guard.py`: `evaluate_sql(sql: str, actor: SqlActor) -> SqlGuardResult`
  (`decision: Decision`, `reasons: list[str]`, `normalized_sql: str | None`).
  Rules: exactly one statement; SELECT/WITH only; no ATTACH/PRAGMA/load_extension;
  table+column allowlist per ACL above (no `SELECT *` on tables with denied columns);
  enforce `LIMIT <= 50`; deny comment-smuggling and stacked queries.
- `executor.py`: read-only execution (`file:...?mode=ro` URI + `PRAGMA query_only=ON`),
  row cap, timeout. Unguarded lab runs against a throw-away in-memory COPY so destructive
  SQL is demonstrable without damaging the seed DB.
- `result_guard.py`: scan returned rows (e.g. `orders.note`, `product_reviews.content`)
  for indirect injection with existing `app/guards/rag_guard.py` / `output_guard.py` logic
  before rows are given back to the LLM (indirect P2SQL defense).
- `agent.py`: question -> provider produces SQL in a ```sql block -> guard -> execute ->
  result guard -> provider writes Vietnamese answer -> existing Output Guard.
- Routes in new file `app/api/sql_routes.py`: `POST /v1/sql/chat` (guarded) and
  `POST /v1/unguarded/sql/chat` (no guards, in-memory copy). `app/main.py` include_router
  is merged by the leader — workers do not edit `app/main.py` except Worker A's import line.

## File ownership (to avoid merge conflicts)
| Worker | Files |
|---|---|
| A | `app/services/providers/anthropic.py`, `tests/test_anthropic_provider.py`, `.env.example` (anthropic block), `app/main.py` (one conditional import, like ollama) |
| B | `datasets/furniture/**` except `sql/schema.sql`, `scripts/build_furniture_db.py`, `tests/test_furniture_dataset.py` |
| C | `app/sql_agent/**`, `app/api/sql_routes.py`, `tests/test_sql_guard.py`, `tests/test_sql_agent.py`, `redteam/sql/*.jsonl` (attack prompts) |
| Leader | this file, `schema.sql`, merge, `app/main.py` router include, final docs |

## Report template (each worker, in `docs/p4-claude-sql/report-<A|B|C>.md`)
What changed / Why / How to test / Evidence (real pytest output) / Risks & TBD.
