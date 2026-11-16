# P4 — Bàn giao: Provider Claude + Dữ liệu nội thất + SQL Guard

Nhánh: `feat/claude-provider-sql-guard` (local, **chưa push**). Gốc: `64e4b04`.
Người làm: Claude (leader, implementer). **Không tự tuyên bố PASS** — cần audit độc lập
(Grok chat mới cho kỹ thuật/bảo mật, Gemini cho phương pháp/claim) và người duy trì quyết định.

Ghi chú quy trình: kế hoạch ban đầu giao cho các worker Codex/Grok qua Agent Orchestrator,
nhưng worker không chạy được (harness chưa đăng nhập, spawn lỗi, worktree tạo từ `origin/main`
nên thiếu contract). Leader tự làm cả 3 task theo đúng `00_CONTRACT.md`, mỗi task một commit.

| Commit | Nội dung |
|---|---|
| `eff5243` | Contract, schema chốt, đề bài worker |
| `72af597` | Task A — provider Anthropic |
| `adf8877` | Task B — dataset nội thất |
| `e1a3eea` | Task C — SQL agent + SQL guard + result guard |

## 1. What changed
**A. Provider Claude** — `app/services/providers/anthropic.py` (`LLM_PROVIDER=anthropic`,
`LLM_MODEL_NAME=claude-sonnet-5-5`, `ANTHROPIC_API_KEY`). Chỉ dùng stdlib. Prompt hệ thống,
lịch sử và khối CONTEXT tách ra `providers/_shared.py`; `ollama.py` dùng chung → hai model
nhận **cùng một chỉ dẫn** (cả nhánh guarded lẫn `unguarded_lab`). CONTEXT đặt trong tham số
`system` (tương đương vị trí system-role trong Ollama). Key không bao giờ xuất hiện trong lỗi.

**B. Dataset** — `datasets/furniture/`: schema (contract), `seed.sql` sinh tất định bởi
`scripts/generate_furniture_seed.py`, 8 tài liệu sạch + 6 bản đầu độc ghép cặp, 18 dòng tấn công
P2SQL gián tiếp (9 `orders.note`, 9 `product_reviews.content`) + 18 dòng đối chứng lành tính,
`manifest.json`, `scripts/build_furniture_db.py`. Đặt cạnh dữ liệu cũ; `datasets/v2`, `v3` không đổi
(`git diff eff5243 HEAD -- datasets/v2 datasets/v3` = 0 dòng).

**C. SQL agent** — `app/sql_agent/`:
- `guard.py`: biên dịch SQL (EXPLAIN, không chạy) bằng chính SQLite với **authorizer** trên schema
  rỗng → biết chính xác bảng/cột được đọc (kể cả `SELECT *`, CTE, subquery, UNION). Chỉ 1 câu
  SELECT/WITH; ACL bảng/cột theo phòng ban–vai trò; `internal_secrets`, `sqlite_master`,
  `pragma_*` không bao giờ đọc được; hàm ngoài allowlist bị chặn; ép `LIMIT ≤ 50`. Lớp regex phụ:
  stacked query, comment, ATTACH/PRAGMA/ghi.
- `executor.py`: guarded = `mode=ro` + `query_only` + cùng authorizer + giới hạn thời gian/dòng.
  Unguarded = chạy mọi thứ (kể cả nhiều câu lệnh) trên **bản sao in-memory** — file gốc không đổi.
- `result_guard.py` + `injection_rules.py`: quét ô văn bản trong kết quả (RAG guard có sẵn +
  luật P2SQL gián tiếp + DLP) **trước** lần gọi LLM thứ hai.
- `agent.py`: Input Guard → LLM sinh SQL → SQL Guard → thực thi → Result Guard → LLM trả lời →
  Output Guard. Bản unguarded bỏ toàn bộ guard và đưa schema đầy đủ.
- Endpoint: `POST /v1/sql/chat`, `POST /v1/unguarded/sql/chat` (`app/api/sql_routes.py`).
- `redteam/sql/p2sql-direct.jsonl` (22 ca, 13 loại) và `p2sql-benign.jsonl` (21 ca). Thêm
  `!redteam/sql/*.jsonl` vào `.gitignore` (đường dẫn hẹp; không đụng holdout v2).

## 2. Why
Tạo bảng 2x2 {qwen3 local, Claude Sonnet 5.5} × {không guard, có guard} cho cả RAG poisoning và
SQL injection/P2SQL, để kiểm chứng luận điểm "bảo mật nằm ở gateway, không nằm ở model".

## 3. How to test
```powershell
.venv\Scripts\python.exe -m pytest -q tests/test_anthropic_provider.py tests/test_furniture_dataset.py tests/test_sql_guard.py tests/test_sql_agent.py
.venv\Scripts\python.exe scripts\build_furniture_db.py --out data/furniture.db --force
.\scripts\verify_phase.ps1
```
Chạy thật với Claude (TỐN TIỀN — cần người duy trì duyệt, AGENT_RULES rule 4): đặt trong `.env`
`LLM_PROVIDER=anthropic`, `LLM_MODEL_NAME=claude-sonnet-5-5`, `ANTHROPIC_API_KEY=...`, rồi
`uvicorn app.main:app` và gọi `/v1/sql/chat` vs `/v1/unguarded/sql/chat`.

## 4. Evidence (output thật, Linux VM, Python 3.10.12 — KHÔNG phải `.venv` Windows của dự án)
- Bộ test P4 + provider liên quan: `120 passed, 1 warning in 3.47s`.
- Toàn bộ `tests/` (trừ `phase12f/release/ci`): `2 failed, 1350 passed, 16 skipped`.
  `tests/phase12f tests/release tests/ci`: `3 failed, 269 passed, 7 skipped`.
- 5 test lỗi đều **có sẵn từ trước**, do môi trường Python 3.10 (vd. `Path.read_text(newline=...)`
  chỉ có từ 3.13); đã xác nhận các test này cũng lỗi trên commit gốc `64e4b04`.
- Người duy trì cần chạy lại `verify_phase.ps1` trên Windows để có evidence block chính thức.

## 5. Risks / TBD
- **Chưa có số liệu đánh giá nào.** Mọi `expected_guard_decision` là kỳ vọng thiết kế.
- `injection_rules.py` được viết **trên chính 18 dòng tấn công của dataset** → đây là dev set,
  dễ overfit. Cần một bộ holdout P2SQL gián tiếp do người/AI khác viết độc lập trước khi báo tỉ lệ.
- Lớp regex phụ của SQL guard bảo thủ: chặn `;`, `#`, từ khoá ghi (vd. `update`) cả khi nằm trong
  chuỗi literal → có thể false positive.
- Tautology (`OR 1=1`) trong phạm vi bảng/cột được phép **không bị chặn** — guard bảo vệ ranh giới
  dữ liệu, không phải ngữ nghĩa câu hỏi.
- `/v1/unguarded/sql/chat` không có xác thực (giống các endpoint `/v1/*` khác); chỉ chạy trên
  bản sao in-memory của dữ liệu giả.
- `ollama.py` đã refactor sang `_shared.py`; test cũ vẫn qua nhưng nên thử lại demo Ollama thật.
- Gọi API Claude chưa được thực hiện lần nào.
- File `scripts/seed_enterprise_knowledge_base.py` (sửa dở của bạn) **không** nằm trong commit nào.
