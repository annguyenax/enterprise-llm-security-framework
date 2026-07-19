# Open Questions

Câu hỏi chưa trả lời và việc đã hoãn lại. Không để chúng biến mất vào lịch sử chat.

---

## Q-001 — Ablation profile nào cho Phase 12E?

**Trạng thái:** **ĐÃ ĐÓNG — G0 PASS; master plan APPROVED FOR IMPLEMENTATION**

Đề xuất 8 config: C0_all_on, C1_no_input, C2_no_provenance, C3_no_context,
C4_no_dlp, C5_no_output, C6_none, C7_no_context_no_output. **Không** chạy toàn bộ
2⁵=32 tổ hợp (cỡ mẫu không cho phép kết luận tương tác bậc cao). C0-C7 dùng một
seam in-process; public HTTP luôn `ALL_ON`. Chưa được coi là approved cho tới khi
ba re-audit PASS và người duy trì phê duyệt. Điều kiện đó đã hoàn thành trên
plan commit `d82bac7828e2e54520e0aa29271e820a52ec6f47`: Code X, Gemini và Grok
đều trả **PASS**, không còn Critical, blocking Major hoặc correction bắt buộc.
Triển khai Phase 12E chưa bắt đầu; chưa có kết quả evaluation và chưa chạy holdout.

---

## Q-002 — Có tính confidence interval cho metric tổng hợp không?

**Trạng thái:** **ĐÃ ĐÓNG — Wilson 95% không continuity correction, chỉ cho
AOMR/FPR đủ điều kiện**

Quyết định đã triển khai và được closure 12E.3 xác nhận: Wilson 95% không
continuity correction, áp dụng **chỉ** cho AOMR và FPR có mẫu số ≥
`RATE_REPORTING_MIN_N=10`. Family chỉ raw counts, không percentage, không CI.
Không p-value. Kèm caveat rằng CI chỉ mô tả bất định trong chính mẫu benchmark
tổng hợp này, không thiết lập khoảng hiệu năng tổng quát.
Xem `analyze_v2_results.py:34-43, 1212-1240`.

---

## Q-003 — Ollama chưa cài

**Trạng thái:** Chưa làm — chặn vai "grunt worker" và "payload generator"

Chưa cài Ollama nên chưa dùng được Qwen2.5-Coder local (việc cơ học) và Hermes
local (sinh payload probe). Hai vai này trong `01_AGENT_ROLES.md` đang trống.

Cài: https://ollama.com/download/windows — rồi
`ollama pull qwen2.5-coder:7b` và `ollama pull hermes3:8b`, sau đó bỏ comment
hai model tương ứng trong `~/.continue/config.yaml`.

---

## Q-004 — API key cũ đã revoke chưa?

**Trạng thái:** CẦN HÀNH ĐỘNG — chưa xác nhận

Gemini key và DeepSeek key đã lộ dạng plaintext trong `~/.continue/config.yaml`
(xem D-003). Config đã sửa sang biến môi trường, nhưng **hai key cũ phải được
revoke và tạo lại** — chưa xác nhận đã làm.

---

## Q-005 — Phase 12C final Code X re-audit

**Trạng thái:** **ĐÃ ĐÓNG — PASS**

Code X final re-audit tại `9fed074481f46ce5e3ae2bfa20abcec3e36661fb`
xác nhận nested response construction đã được bảo vệ, không còn Critical hoặc
blocking Major và không có required action trước DONE. Báo cáo authoritative:
`docs/modernization-ai-reviews/codex-phase-12c-final-reaudit.md`.

Q-005 không còn chặn Phase 12E. G0 plan re-audit sau đó cũng đã đóng bằng triple
**PASS**; xem `docs/modernization-ai-reviews/phase-12e-plan-audit-resolution.md`.
Master plan đã được phê duyệt cho triển khai, nhưng implementation chưa bắt đầu.

---

## Q-006 — Giao thức đo latency cho Phase 12E

**Trạng thái:** **ĐÃ ĐÓNG — chọn L2, không có latency reportable** (xem D-007)

RQ4 bị gỡ khỏi các research question có thể báo cáo; H5 phân loại lại thành kỳ
vọng mô tả, không báo cáo. `latency_reportable=false`, `p50`/`p95` null. Timing
lúc chạy chỉ giữ làm chẩn đoán determinism. Không thêm latency mini-gate, không
yêu cầu máy đo chuyên dụng, không đổi hành vi determinism repetition.

L1 giữ lại như phương án bị bác kèm lý do đầy đủ trong
`07_PHASE_12E4_HOLDOUT_PLAN.md` §3.

---

## Q-007 — Định dạng authorization holdout, `issued_by`, `purpose`, GPG

**Trạng thái:** **ĐÃ ĐÓNG** (xem D-010)

- Schema: `phase12e4-holdout-authorization-v1`, canonical JSON nghiêm ngặt, file
  ngoài repository, không commit.
- `issued_by`: `maintainer:annguyenax`
- `purpose`: `phase12e4_holdout_c0_c7`
- **GPG không bắt buộc** dưới mô hình trusted-maintainer đã khai báo (D-009).

---

## Q-008 — Development smoke chạy ở đâu?

**Trạng thái:** **ĐÃ ĐÓNG — worktree sạch riêng** (xem D-012)

Development-only C0–C7 smoke chạy trong một git worktree sạch riêng, output root
ngoài repository, Mock Provider. Không validation, không holdout.

---

## Q-009 — Chính sách retry holdout

**Trạng thái:** **ĐÃ ĐÓNG — lineage `supersedes`, KHÔNG còn là câu hỏi mở**
(xem D-011)

Không chặn thẳng `attempt > 1`. Attempt fatal/partial được giữ nguyên. Retry hợp
lệ đòi hỏi đủ sáu điều kiện: uỷ quyền mới của người duy trì · `authorization_id`
mới · external root mới · `attempt` tăng · `supersedes_authorization_sha256` ·
implementation commit/provider/configs/manifest/mapping/contract không đổi.
Analyzer không bao giờ trộn attempt. Đây là chính sách **ràng buộc**, không phải
đề xuất.

---

## Không phải câu hỏi mở: uỷ quyền chạy holdout

Việc người duy trì cấp uỷ quyền chạy holdout trong tương lai là một **GATE trong
quy trình**, **không phải một câu hỏi thiết kế còn mở**. Thiết kế đã đóng; chỉ
còn chờ đủ chuỗi gate và văn bản uỷ quyền. Xem
`07_PHASE_12E4_HOLDOUT_PLAN.md` §20–21 và D-014.
