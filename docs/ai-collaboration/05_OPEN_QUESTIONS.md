# Open Questions

Câu hỏi chưa trả lời và việc đã hoãn lại. Không để chúng biến mất vào lịch sử chat.

---

## Q-001 — Ablation profile nào cho Phase 12E?

**Trạng thái:** Hoãn tới Phase 12E (Gemini nêu là "deferrable")

Cần chọn tổ hợp guard nào để bật/tắt. Ví dụ: Input Guard + Output Guard nhưng
tắt Context Guard. Chưa quyết.

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

## Q-005 — Phase 12C còn treo một vòng Code X re-audit

**Trạng thái:** Chưa làm

Phase 12C (RAG security pipeline) vẫn ở In Review, chờ một vòng Code X re-audit
cuối. Phase 12D đã Done nhưng 12C thì chưa — cần đóng nốt trước khi bắt đầu 12E,
vì 12E đánh giá chính pipeline của 12C.
