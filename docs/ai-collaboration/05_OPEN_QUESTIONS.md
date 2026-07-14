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

**Trạng thái:** Hoãn tới Phase 12E (Gemini nêu là "deferrable")

Với 120 case, CI có thể rộng đến mức vô nghĩa. Cần cân nhắc có đáng làm không,
hay chỉ báo cáo số tuyệt đối kèm cỡ mẫu.

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
