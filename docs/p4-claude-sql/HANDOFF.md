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
`LLM_MODEL_NAME=claude-sonnet-5-5`, `ANTHROPIC_API_KEY`). Lớp HTTP dùng stdlib (`urllib`), không thêm gói mới vào `requirements.txt`. Mặc định không gọi API trả phí: chỉ khi người dùng chủ động đặt `LLM_PROVIDER=anthropic` + key và gửi request; `p4_live_smoke.py` còn đòi thêm `--allow-paid`. Prompt hệ thống,
lịch sử và khối CONTEXT tách ra `providers/_shared.py`; `ollama.py` dùng chung → hai model
nhận **cùng một chỉ dẫn** (cả nhánh guarded lẫn `unguarded_lab`). CONTEXT đặt trong tham số
`system` (tương đương vị trí system-role trong Ollama). Key không bao giờ xuất hiện trong lỗi.

**B. Dataset** — `datasets/furniture/`: schema (contract), `seed.sql` sinh tất định bởi
`scripts/generate_furniture_seed.py`, tài liệu sạch + bản đầu độc ghép cặp, dòng tấn công P2SQL gián tiếp
và dòng đối chứng lành tính (số lượng hiện tại: xem P4.1 và `datasets/furniture/manifest.json`),
`manifest.json`, `scripts/build_furniture_db.py`. Tính tất định được kiểm bằng
`tests/test_furniture_dataset.py::test_seed_is_deterministic` (sinh vào thư mục tạm của pytest rồi so
từng byte với `seed.sql` và `manifest.json` đang được track — chạy được ở chế độ chỉ đọc). Đặt cạnh dữ liệu cũ; `datasets/v2`, `v3` không đổi
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
SQL injection/P2SQL. Đây là **độ phủ thực nghiệm được lên kế hoạch** để sau này đánh giá giả thuyết
"bảo mật nằm ở gateway, không nằm ở model" — phase này **chưa** kiểm chứng giả thuyết đó (chưa gọi
Claude, kết quả smoke không báo cáo được, chưa có holdout P2SQL độc lập).

## 3. How to test
```powershell
.venv\Scripts\python.exe -m pytest -q tests/test_anthropic_provider.py tests/test_furniture_dataset.py tests/test_sql_guard.py tests/test_sql_agent.py
.venv\Scripts\python.exe scripts\build_furniture_db.py --out data/furniture.db --force
.\scripts\verify_phase.ps1
```
Chạy thật với Claude (TỐN TIỀN — cần người duy trì duyệt, AGENT_RULES rule 4): đặt trong `.env`
`LLM_PROVIDER=anthropic`, `LLM_MODEL_NAME=claude-sonnet-5-5`, `ANTHROPIC_API_KEY=...`, rồi
`uvicorn app.main:app` và gọi `/v1/sql/chat` vs `/v1/unguarded/sql/chat`.

## 4. Evidence
Các số pytest chạy trên Linux VM trong giai đoạn này không được lưu log nên đã bị gỡ khỏi tài liệu.
Bằng chứng chính thức: `evidence/verify_phase-HEAD.txt` (Windows, `.venv` của dự án).

## 5. Risks / TBD
- **Chưa có số liệu đánh giá nào.** Mọi `expected_guard_decision` là kỳ vọng thiết kế.
- *(Tại `e1a3eea`)* `injection_rules.py` được viết **trên chính 18 dòng tấn công của dataset** → đây là dev set,
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

---

# P4.1 — Nâng cấp: dữ liệu thật hơn, tấn công đa dạng, agent công ty

| Commit | Nội dung |
|---|---|
| `afb90b1` | Dữ liệu vận hành thực tế hơn (schema 1.1) |
| `b9045a3` | Đa dạng hoá tấn công, chia dev/holdout |
| `9ace83d` | Trợ lý Nhà Mộc Việt nhiều công cụ |

## What changed
**Dữ liệu (schema 1.1):** thêm `employees`, `promotions`, `shipments`, `warranty_claims`,
`support_tickets`. 6 showroom + kho tổng, 74 SKU theo bộ sưu tập, 300 khách, 1.500 đơn (2025–2026,
cao điểm Tết/cuối năm), 1.410 vận đơn, 600 đánh giá, 400 ticket, 120 yêu cầu bảo hành, 84 nhân sự,
6 chương trình khuyến mãi. 15 tài liệu sạch + 14 tài liệu đầu độc. ACL mở rộng cho bảng mới và
phòng NhanSu, IT.

**Tấn công:**
- Gián tiếp (`datasets/furniture/attacks/indirect-rows.json`): 38 payload (24 dev / 14 holdout,
  38 kỹ thuật) cài ở 7 bảng — base64, homoglyph Cyrillic, zero-width, leetspeak, tiếng Trung,
  chat-template/[INST] spoof, tool-call JSON, markdown/HTML image exfil, link phishing, đổi STK,
  payload chia 2 phần, persona/prompt leak, DoS, stored SQLi trong tên khách, supply-chain trong
  điều khoản NCC... + 32 dòng lành tính giống tấn công.
- Trực tiếp (`redteam/sql/`): 38 tấn công / 31 lành tính — thêm obfuscation hoa/thường + tab,
  `char()`, recursive CTE DoS, `randomblob`, `sqlite_version`, blind boolean, NULL-padding UNION,
  `json_extract`, dấu `；` toàn độ rộng, TEMP VIEW, BEGIN/COMMIT, lộ lương/địa chỉ.
- RAG poisoning mới: đổi số tài khoản, markdown image exfil, base64, tool-call trong tài liệu,
  giá sai, link phishing, chỉ thị chia 2 tài liệu (holdout).

**Agent (`app/company_agent/`):** 5 công cụ `search_docs`, `query_db`, `order_status`
(truy vấn tham số hoá — đối chứng với text-to-SQL), `create_ticket`, `send_email` (mô phỏng, không
gửi thật). Chế độ guarded: Input Guard → allowlist công cụ theo phòng ban → parse JSON + validate
tham số → SQL Guard → RAG/Result Guard trên MỌI output công cụ → hành động ghi vào hàng chờ, chỉ
Leader duyệt → email chỉ tới `@example.test` + DLP → Output Guard + xoá link/ảnh ngoài → tối đa 5 bước.
Unguarded: bỏ toàn bộ. Endpoint: `POST /v1/agent/chat`, `POST /v1/unguarded/agent/chat`,
`POST /v1/agent/actions/{id}/approve`, `GET /v1/agent/outbox`. Tham số `corpus=clean|poisoned`.

## Evidence (số fixture tái hiện được bằng script)
- `scripts/eval_indirect_fixtures.py` (Result Guard, không LLM):
  `dev 24/24`, `holdout 9/14`, `benign flagged 0/32` — **quan sát trên fixture**, tái hiện được bằng
  script (Code X đã chạy lại ra đúng các số này). Dev và holdout do **cùng tác giả** viết; repo
  **không** ghi lại quy trình chỉnh luật, nên tài liệu này **không** đưa ra khẳng định nào về quy trình
  đó, cũng không suy ra nguyên nhân các ca trượt. Cần holdout độc lập trước khi báo bất kỳ tỉ lệ nào.
- Số pytest chạy trên Linux VM ở giai đoạn này không được lưu log nên đã bị gỡ. `evidence/verify_phase-HEAD.txt`
  là một lần chạy **riêng biệt, về sau**, trên Windows tại `ec68cf3` — không thay thế hay xác nhận các log Linux đã mất.

## Risks / TBD (bổ sung)
- Holdout do **cùng tác giả** viết → chỉ là kiểm tra sơ bộ; cần holdout độc lập (Grok/Gemini/người).
- Hàng chờ duyệt và outbox nằm trong bộ nhớ tiến trình, mất khi restart; `approver_role` do client
  tự khai (chưa gắn xác thực) và chưa chặn tự duyệt yêu cầu của chính mình.
- Tìm tài liệu là keyword scoring đơn giản, không dùng retriever BM25/hybrid sẵn có của dự án.
- `order_status` vẫn trả `orders.note` (qua Result Guard) — cố ý, để thử indirect injection.
- Chưa chạy agent với LLM thật (qwen3/Claude): model thật có thể không theo đúng định dạng JSON.

---

# P4.2 — Kiểm thử trên máy Windows của người duy trì + chạy agent với qwen3 thật

## Môi trường
Windows, `.venv` Python 3.14, Ollama 0.40.16 (mới cài), model `qwen3:4b-instruct`.
Biến hệ thống `OLLAMA_HOST=192.168.100.40:11434` khiến Ollama chỉ nghe ở IP LAN; provider dự án
chỉ cho `127.0.0.1` → `scripts/p4_live_ollama.bat` tự mở thêm một tiến trình Ollama ở loopback
cho lần chạy (không sửa biến môi trường của người dùng).

## Evidence (output thật; bản sao được track ở `docs/p4-claude-sql/evidence/`)
- *(Lịch sử, commit `1e5458f`; log không được lưu)* `verify_phase.ps1`: `full_suite: 1708 passed, 4 skipped`; validator,
  determinism, manifest, frozen_artifacts (9 file byte-identical), git_diff_check,
  scope_invariants, no_tracked_db: PASS. FAIL còn lại chỉ do môi trường:
  `no_temp_dirs` (`.pytest-tmp` thuộc tài khoản `MSI\CodexSandboxOffline`, cần quyền admin để xoá —
  `scripts/p4_cleanup_admin.bat`) và `compile` — nguyên nhân thật về sau xác định là lỗi splat
  trong `verify_phase.ps1` (sửa ở `184df3d`), không phải `.pyc` bị khoá như nhận định ban đầu.
- *(Quan sát lịch sử do người duy trì chạy; phụ thuộc trạng thái Ollama và tính ngẫu nhiên của model,
  **không tái hiện được chỉ từ repo**; output thô được lưu ở `evidence/live_smoke-1e5458f-repeat3.txt`)*
  `scripts/p4_live_smoke.py --provider ollama --repeat 3` (11 kịch bản × 2 chế độ × 3 lần):
  - guarded: **tấn công thành công 0/18**; benign chọn đúng công cụ 13/15; lỗi 0.
  - unguarded: **tấn công thành công 12/18** (đọc `internal_secrets`, gửi email ra
    `evil-mail.test`, trả STK giả từ tài liệu đầu độc, `DELETE FROM inventory` — chỉ trên bản sao
    in-memory); benign 12/15; lỗi 0.
  - Lưu ý diễn giải: A1/A2/A3 (guarded) bị **chính model** từ chối trước khi gọi công cụ — guard
    chưa phải ra tay; A4 (RAG poisoning), A5 (indirect qua ghi chú đơn), A6 (DELETE) bị **guard**
    chặn. A2 unguarded không “thành công” chỉ vì model không tổng hợp được bảng lương 84 dòng.
  - n=3 mỗi ô, model ngẫu nhiên → quan sát smoke-test, **không phải số liệu báo cáo**.

## Lỗi phát hiện nhờ chạy model thật và đã sửa (commit `14e1ba0`)
- qwen3 sinh JSON gần đúng (thiếu ``` đóng, thừa `);`) → parser chịu lỗi có kiểm soát (tham số vẫn
  bị validate), thử lại 1 lần khi JSON hỏng, không bao giờ trả khối JSON thô cho người dùng.
- Model gọi lặp cùng công cụ → bỏ qua lời gọi trùng, ép câu trả lời cuối; chạm giới hạn 5 bước →
  hỏi model tổng hợp thay vì trả câu cố định.
- Tài liệu thanh toán không chứa “chuyển khoản” → tìm kiếm trượt; đã bổ sung nội dung.
- Script đo coi việc model *nhắc lại* địa chỉ email là rò rỉ → nay chỉ tính hành động thực sự xảy ra.

## Cách chạy lại
Double-click `scripts\p4_windows_check.bat` (build DB → verify_phase → live smoke qwen3), kết quả ở
`logs\p4-check\`. Chỉ live: `scripts\p4_live_ollama.bat`. Không gọi API trả phí.

## Kết quả verify tại commit `184df3d` (lịch sử; xem mục “Verify tại HEAD” bên dưới cho commit cuối)
`verify_phase.ps1`: **TAT CA PASS** — compile, focused_tests (404 passed), full_suite
(**1708 passed, 4 skipped**), validator, determinism, manifest, frozen_artifacts (9 file
byte-identical), git_diff_check, scope_invariants, no_temp_dirs, no_tracked_db.

Hai việc dọn dẹp để đạt kết quả này:
- `.pytest-tmp` (thuộc `MSI\CodexSandboxOffline`) được người duy trì xoá bằng `scripts/p4_cleanup_admin.bat`.
- Sửa lỗi có sẵn trong `verify_phase.ps1` (commit `184df3d`): khi chỉ có đúng 1 file `.py` thay đổi,
  PowerShell splat chuỗi thành từng ký tự → `py_compile` nhận `'s'` và báo FAIL giả. Đã tái hiện trên
  Windows (exit 1 → exit 0 sau khi bọc `@(...)`).

Việc tiếp theo theo quy trình: audit độc lập (Grok chat mới: kỹ thuật/bảo mật; Gemini:
phương pháp/claim) và người duy trì quyết định. Holdout P2SQL độc lập vẫn là TBD.

## Bằng chứng được lưu trong repo (đáp ứng Code X F1)
`logs/` bị gitignore, nên bản sao nguyên văn được commit tại `docs/p4-claude-sql/evidence/`:
- `verify_phase-184df3d.txt`, `verify_status-184df3d.txt` — output `verify_phase.ps1` trên Windows (TAT CA PASS).
- `live-ollama-1e5458f-repeat3.json`, `live_smoke-1e5458f-repeat3.txt` — output thô của
  `p4_live_smoke.py --repeat 3` với qwen3:4b-instruct, lần chạy 11:52 ngày 16/11/2026 tại commit
  `1e5458f` (code agent giống `14e1ba0`; log của lần chạy 11:41 đã bị ghi đè). Tóm tắt trong file:
  guarded 0/18, unguarded 12/18, benign 13/15 và 12/15, lỗi 0. Đây là **quan sát smoke-test do người duy trì
  chạy trên máy của mình**, ngẫu nhiên, n=3/ô — không phải số liệu báo cáo.

## Verify tại HEAD
`evidence/verify_phase-HEAD.txt`: `base_commit: ec68cf3`, **TAT CA PASS**, full_suite
`1708 passed, 4 skipped`. Commit chứa file bằng chứng này chỉ thêm file bằng chứng và sửa đoạn này trong HANDOFF. Các commit sau `184df3d` chỉ thay đổi
tài liệu, bằng chứng, prompt audit và file `.bat` — không đổi code ứng dụng hay test.

## Trạng thái audit (Code X / Codex CLI, chỉ đọc)
Báo cáo các vòng: `audit/codex-integrity-round1..6.md`. Từ vòng 3 không còn Critical/Major. Vòng 6 còn 2 Minor:
F2 (câu chữ — đã sửa ở commit này) và F8 (sandbox của auditor không có thư mục tạm nên pytest không khởi
động được — vấn đề môi trường auditor; các vòng 1–5 chạy cùng bộ test được: 172 passed). Implementer
**không** tự tuyên bố PASS; người duy trì quyết định.
Grok (audit kỹ thuật/bảo mật): **chưa chạy xong** — Grok Build CLI hết hạn mức miễn phí; chạy lại
`scripts\p4_audit_run.bat` khi có hạn mức. Gemini (phương pháp): chưa chạy (chưa có CLI; cần Node ≥ 20).
