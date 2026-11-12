# Review Claude — VAL1 thẻ 17 (diff only)

1 lượt, 12:50–12:51 ngày 12/11/2026, Asia/Saigon. tokrun label `review-claude-val1-card17`. stderr: claude-chain trying claude-opus-5-5, served by claude-sonnet-5-5 (fallback). Không sửa file.

VERDICT: PASS

**Issues:** không có lỗi bắt phải sửa. Có một ghi chú nhỏ ở cuối, không chặn.

**Lý do:**
- **Các kiểm tra khác còn nguyên.** Tôi đã đọc thẻ 17 trong file hiện tại (`VAL1-RUNBOOK.md:539-570`), SHA-256 khớp `c0f48830…a7`. Các kiểm tra HEAD, branch, cây sạch, `.env`, timeout 30/Judge OFF, keep_alive/base_url, smoke OK, official_30s, output/analysis chưa tồn tại, ledger chưa tồn tại → tạo mới → phải rỗng, freeze chưa tồn tại, và dòng `PREFLIGHT_ONLY_COMPLETE` đều còn đủ và giữ đúng thứ tự. Chỗ thay đổi duy nhất là dòng hash.
- **Nhánh absent ghi đúng nguyên văn.** Dòng 561 ghi đúng chuỗi `'test_retrieval_db: absent (fixture-only tests)'` vào `$Log` bằng `Tee-Object -Append`, không có ký tự thừa.
- **Nhánh db tồn tại có hash, không bỏ qua thầm.** Dòng 558-559 hash riêng file db bằng `Get-FileHash`. Smoke, dependency và test-audit vẫn hash bắt buộc như trước (dòng 557). Nếu thiếu một trong ba file này thì `Get-FileHash` vẫn báo lỗi như cũ, gate không bị nới.
- **Không tạo/ghi db, không làm yếu gate.** Thẻ 17 chỉ kiểm tra file db có tồn tại hay không, không tạo hay ghi gì vào db. Thẻ 08 (dòng 295) vẫn dừng nếu db có sẵn trước khi chạy test. Vì vậy nếu db có mặt ở thẻ 17 thì chỉ có thể do test tạo ra, và nó sẽ được hash.
- **Ghi chú nhỏ (không chặn):** nhờ `-PathType Leaf`, nếu đường dẫn db lại là một thư mục thì receipt vẫn ghi "absent". Trường hợp này gần như không thể xảy ra vì thư mục preflight do runbook kiểm soát, nên không cần sửa.
