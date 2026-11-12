# Review VAL1-RUNBOOK.md (Muse, độc lập)

- Thời điểm: 12/11/2026, Asia/Saigon. Chỉ đọc hai file được chỉ định; không chạy trên máy An, không push, không mở holdout, không sửa framework.
- File được review: `VAL1-RUNBOOK.md` (bản sau khi coordinator áp NEW-01, FIX-01…05) + `review-claude-val1.md` (PASS-WITH-FIXES).

## Verdict: PASS

- run_id và SHA đóng băng: `P3VAL1-20261112-bbb78f3-01`, commit `bbb78f3318c09f44847d952027e1fe895ccb5d98` (parent `40e44619…07db7`), nhánh có tên `feat-p3-rag-opt`, so sánh đủ 40 ký tự ở thẻ 04/05/17, cấm detached HEAD.
- Bundle + CopyFromBox: bundle `866b6419…8d59d35` (13,226,219 byte) + manifest dẫn xuất `25ba6502…` + `SHA256SUMS 1c0d6142…`; staging `C:\Users\ADMIN\p3-val1-transfer\`, ghi rõ CopyFromBox không ghi được D:, là thao tác công cụ chưa thực hiện, clone bắt buộc `--branch`.
- Checkout mới, không đụng cây P2: `D:\DoAnThucTap\shield-p3-val1` + data/output/analysis/log/receipt mới, STOP nếu đích đã tồn tại hoặc qua reparse point; cấm ghi `shield-p2-run`/`p2-output`/`shield-p2-analyze`, repo cũ chỉ hash/copy 6 file literal, không checkout/status/pull/venv/Python/`.env`.
- Judge OFF + Ollama 0.40.11: `SEMANTIC_GUARD_USE_LLM=0`, không kéo `qwen3:4b`; Ollama `0.40.11` qua `/api/version`+`/api/tags`, E4B `ee665637…`/Q4_0, backup E2B `b3704936…`/Q4_K_M, options 0/42/4096/512/think false/keep_alive 30m/repeat 1/timeout runner 30s (smoke 180s), cấm `ollama list/pull`/installer.
- Hash val theo đường dẫn cụ thể: 6 đường dẫn literal tuyệt đối dưới `datasets\v2\` với hash+size khớp P2, thẻ 13 hash + thẻ 14 copy allowlist + thẻ 15 re-hash/inventory đúng 4 thư mục/7 file, không đọc thân JSONL, không glob root nguồn, không hash/mở holdout.
- Hai blocker + thẻ 18 STOP: BLK-01 runner cấm Ollama không authorization (4558–4560, 2350–2351, 4561–4563), BLK-02 analyzer thiếu dev-val/root và verifier đòi 9 artifact gồm holdout (2333–2340, 872–924, 148–158, CLI 3508–3525/3597); thẻ 18 `throw` STOP cứng, thẻ 19–20 mở đầu `throw` và chỉ là mục tiêu khóa, cấm `--holdout-authorization` cho val, duyệt lại trên cùng `bbb78f3` không mở STOP.
- Lần 1/3 cap: ghi rõ lần 1/3, gồm mọi lượt val Shield W2/W3, đếm lượt chạy không đếm FAIL, mọi lượt lỗi vào ledger, sau lượt 3 STOP; hiện chưa tiêu thụ lượt val (0/3).
- Ngưỡng val + An quyết nếu AOMR <0.80: FPR ≤0.15, AOMR ≥ C3 cùng val, mismatch ≤0.20, coverage 1.00, error_rate ≤0.05, `RATE_REPORTING_MIN_N=10`; AOMR C0 <0.80 thì An quyết go/no-go trước W5, không hạ 0.80; hiện mọi điểm val UNKNOWN.
- NEW-01/FIX-01…05 đã áp đủ: NEW-01 hash official manifest track `c91da60b…` + assert không có holdout ở thẻ 05 và tách repo cũ/checkout mới; FIX-01 pin `OLLAMA_KEEP_ALIVE`/`OLLAMA_BASE_URL` ở thẻ 09 + kiểm lại thẻ 17; FIX-02 thẻ 02 không bịa ngưỡng, trình số đo cho An quyết; FIX-03 receipt gom sang `D:\DoAnThucTap\p3-val1-preflight` và kiểm chưa tồn tại ở thẻ 01; FIX-04 hash 4 receipt `Tee-Object` vào log ở thẻ 17; FIX-05 C0 ghi là cách hiểu điều phối, chờ An xác nhận, không đổi ngưỡng.
