# Handoff Protocol

Bàn giao giữa các agent phải **ngắn và có cấu trúc**. Không gửi cả transcript,
không gửi cả diff dưới dạng văn bản dài, không gửi cả repo.

## Vì sao

Auditor không cần biết implementer đã thử bao nhiêu cách rồi vứt đi. Nó cần
biết: đã đổi file nào, test nói gì, rủi ro còn lại là gì, và cần audit cái gì.
Một handoff 40 dòng thay cho một transcript 3000 dòng — đây là chỗ tiết kiệm
token lớn nhất trong toàn bộ quy trình.

## Schema

Lưu vào `docs/ai-collaboration/handoffs/<task_id>.yaml`.

```yaml
task_id: phase-12e-001
agent_role: implementer          # implementer | planner | auditor
base_commit: 4e10a2e             # BẮT BUỘC — audit phải gắn với commit cụ thể
result: completed                # completed | blocked | partial

summary: >
  Một đoạn ngắn: đã làm gì, không làm gì.

modified_files:
  - app/evaluation/runner.py
  - tests/test_ablation_runner.py

# Dán nguyên xi từ output của scripts/verify_phase.ps1 — KHÔNG tự gõ lại.
validation:
  focused_tests: 18 passed
  full_suite: 596 passed, 1 warning
  validator: PASS
  determinism: PASS
  frozen_artifacts: PASS (9 file byte-identical, status=final)
  git_diff_check: PASS
  scope_invariants: PASS

known_risks:
  - latency đang đo bằng perf_counter, chưa loại trừ nhiễu I/O
  - chưa có aggregation qua nhiều process

out_of_scope:
  - không đụng datasets/v2 (FINAL freeze)
  - không đụng app/guards/*

required_next_agent:
  role: security_auditor
  scope:
    - configuration isolation giữa các ablation profile
    - tính đúng đắn của metric
    - output có deterministic không
```

## Quy tắc

1. **`base_commit` là bắt buộc.** Audit không gắn với commit hash là audit vô
   nghĩa — không ai biết đã review đúng bytes nào. Phase 12D làm đúng điều này:
   cả ba auditor đều review `4e10a2e`.
2. **`validation` phải copy từ script**, không được tự gõ lại từ trí nhớ.
3. **`known_risks` không được để trống một cách giả tạo.** Nếu thật sự không có
   rủi ro nào, ghi `- none identified` và nói rõ vì sao.
4. **`out_of_scope` là lời hứa.** Auditor sẽ kiểm chứng nó bằng
   `git diff --name-status`.

## Cái gì KHÔNG đưa vào handoff

- Transcript hội thoại
- Toàn bộ nội dung file đã sửa (auditor tự đọc diff)
- Lịch sử các cách tiếp cận đã thử và bỏ
- Số liệu tự tường thuật không có script backing
