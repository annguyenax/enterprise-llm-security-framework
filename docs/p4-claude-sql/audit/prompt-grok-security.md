Bạn là **independent technical/security auditor** (Grok) cho repo này. Đây là audit chat MỚI,
bạn không tham gia viết code. CHỈ ĐỌC: không sửa, tạo, xoá file; không commit; không gọi mạng.

Phạm vi: các commit `64e4b04..HEAD` trên nhánh `feat/claude-provider-sql-guard`
(xem `git log --oneline 64e4b04..HEAD` và `git diff 64e4b04..HEAD --stat`).
Đọc trước: `CLAUDE.md`, `AGENT_RULES.md`, `docs/p4-claude-sql/00_CONTRACT.md`, `docs/p4-claude-sql/HANDOFF.md`.

Trọng tâm (đọc code thật, trích file:dòng):
1. `app/sql_agent/guard.py`, `executor.py`: có cách nào đọc `internal_secrets`/cột bị cấm, chạy
   ghi/DDL, ATTACH, PRAGMA, hàm nguy hiểm, hoặc DoS vượt qua guard/authorizer không? Thử nghĩ các
   payload cụ thể (alias, view, CTE, subquery, `sqlite_temp_master`, ký tự Unicode, comment trong chuỗi).
2. `app/sql_agent/result_guard.py`, `injection_rules.py`: lỗ hổng của luật indirect injection; luật nào
   quá rộng gây chặn nhầm.
3. `app/company_agent/agent.py`, `tools.py`, `app/api/agent_routes.py`: tool abuse, bypass allowlist,
   parser JSON "repair" có mở lỗ không, approval flow (tự duyệt, giả role), outbox, link stripping.
4. `app/services/providers/anthropic.py`: rò key, SSRF qua BASE_URL, xử lý lỗi.
5. Unguarded endpoints có thể làm hỏng file DB gốc không.

Định dạng trả lời (tiếng Việt, ngắn gọn):
- Bảng findings: ID | Mức (Critical/Major/Minor/Info) | file:dòng | mô tả | payload/cách tái hiện | đề xuất sửa.
- Chỉ báo finding có căn cứ trong code; ghi rõ nếu là suy đoán.
- Kết luận cuối: `VERDICT: PASS` hoặc `VERDICT: REVISE` (REVISE nếu còn Critical hoặc Major chặn).
