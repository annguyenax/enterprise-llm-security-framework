# Review W2d H1 — `feat-p3-w2d-exp` (uncommitted, parent `62e9295`)

**Verdict: PASS** (gate in-sample C0 MOCK; H1-only, không val)

## Phạm vi

- Đọc: `w2d/h1.patch`, `w2d/w2d-results.md`.
- Không sửa code, không commit/push, không val/holdout, không web, không chạy test.

## Kiểm tra chính

- Logic đúng đặc tả: chỉ BLOCK (không phải SANITIZE/HUMAN_REVIEW), so sánh trong-query, tie tính là best (`>=`), score không dùng được thì fallback rank, không survivor thì nhường path `empty-context` sẵn có.
- Kích hoạt hẹp, nhất quán: chỉ đổi `0015`, `0016` ở C0/C1/C2/C4/C5; C3/C6/C7 (no-context) đổi `none` — đúng cơ chế context-guard-only.
- Audit/stop sạch: survivor sạch bị gán `context_guard_best_evidence_blocked`, thêm `StageResult BLOCK`, `passed_pairs=[]` → `all_context_blocked`, không gọi provider.
- Test hợp lý: 12 case mới (fail-closed tie/mạnh hơn, rank fallback, non-BLOCK không veto, BLOCK yếu passthrough); 2 test cũ đổi malicious thành yếu hơn để giữ ý đồ ban đầu, không làm yếu assertion.
- H2 không tăng AOMR C0 → không ship, giữ H1-only: đúng.

## Issue chặn

Không có.

## Ghi chú không chặn

- In-sample nhỏ: gain +2/14 AOMR, FPR trên 12 benign; không suy ra generalization; tradeoff availability khi best evidence bị poison đã được nêu.
- So sánh score dùng `abs()` trên toàn `hits` (gồm cả hit bị loại non-BLOCK) để xét `comparable`: một hit excluded trái dấu có thể ép fallback rank không cần thiết — nhỏ, không sai policy.
- Survivor bị loại giữ nguyên `Decision` gốc (ví dụ ALLOW) với `passed=False` + `reason` mới; audit phụ thuộc `Decision` thay vì `status`/`reason` có thể đọc lệch — nên xác nhận ở review độc lập.
- Đối chiếu số test: prompt ghi `207+79 passed`, `w2d-results.md` ghi H1 `144 passed` (3 suite) — nên ghi rõ 207+79 gồm những suite nào.
