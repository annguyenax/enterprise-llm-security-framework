# Decisions Log

Nhật ký quyết định kiến trúc cho quy trình phát triển. Mỗi mục ghi: quyết định
gì, vì sao, và cái gì đã bị loại bỏ.

---

## D-001 — Verifier là script, không phải LLM agent

**Ngày:** 2026-07-13 · **Trạng thái:** Đã áp dụng

Mọi số liệu dùng để đóng một phase (test count, SHA-256, determinism) đến từ
`scripts/verify_phase.ps1`, không từ lời tường thuật của LLM.

**Vì sao:** Số liệu đóng phase phải tái lập được và kiểm chứng được. LLM được
hỏi "test có pass không" có thể trả lời sai do ảo giác hoặc đọc nhầm output.

**Loại bỏ:** Phương án dùng một "Test Agent" LLM — không mang lại giá trị nào mà
script không làm được, lại tốn token và có thể báo sai.

---

## D-002 — Không dùng OmniRoute / 9Router

**Ngày:** 2026-07-13 · **Trạng thái:** Đã quyết, KHÔNG cài

Không dùng OmniRoute, 9Router, hoặc bất kỳ proxy nào quảng cáo "unlimited free
AI coding" / "never hit limits". Continue gọi thẳng DeepSeek, Gemini, Ollama.

**Vì sao — ba lý do độc lập:**

1. **Vi phạm ToS.** Các công cụ này quảng cáo truy cập "FREE Claude/GPT/Gemini"
   qua 40–230 provider và "never hit limits" — tức là lách quota của dịch vụ trả
   phí. Một đồ án tốt nghiệp không nên được xây bằng công cụ vi phạm điều khoản
   dịch vụ; nếu hội đồng hỏi, không có câu trả lời tốt.
2. **Supply-chain risk.** Cài một proxy cầm toàn bộ API key và toàn bộ code là
   đúng chính xác threat model mà đồ án này nghiên cứu. Repo còn đang document
   vụ typosquat `httpx2` trong `TASK_BOARD.md` — không thể vừa cảnh báo vừa mắc
   phải.
3. **Không cần thiết.** Continue hỗ trợ native `provider: deepseek`,
   `provider: gemini`, `provider: ollama`. Router ở giữa không mua thêm được gì
   ngoài rủi ro.

---

## D-003 — API key chỉ qua biến môi trường

**Ngày:** 2026-07-13 · **Trạng thái:** Đã áp dụng, CẦN HÀNH ĐỘNG

`~/.continue/config.yaml` từng chứa **Gemini API key và DeepSeek API key ở dạng
plaintext**. Đã thay bằng `${{ env.GEMINI_API_KEY }}` /
`${{ env.DEEPSEEK_API_KEY }}`.

**Hành động bắt buộc:** hai key cũ **phải được revoke và tạo lại** — chúng đã
lộ. DeepSeek key gắn với billing nên đặc biệt nhạy.

**Bài học:** file config của công cụ dev cũng là attack surface. Không hardcode
secret ở bất cứ đâu, kể cả file ngoài repo.

---

## D-004 — Harness: ENABLED cho scaffolding, KHÔNG có quyền audit

**Ngày:** 2026-07-13 · **Trạng thái:** ENABLED (`~/.claude/skills/harness`)

```
Harness: ENABLED
Role: scaffolding and Claude workflow support
Audit authority: NO
```

Dùng Harness để: tạo skill, scaffold workflow, chia nhỏ context, tạo template,
hỗ trợ Claude subagent, đọc/áp dụng pattern. **Không** dùng làm lớp audit cuối.

**Vì sao không cho quyền audit:** Mọi agent Harness sinh ra đều là subagent
Claude. Điều đó (a) tốn token — mỗi subagent cold-start đọc lại context, và
(b) **không tái tạo được sự đa dạng của audit đa mô hình**. Một subagent Claude
audit code do Claude viết vi phạm chính nguyên tắc "implementer không tự
approve". Harness không gọi được Code X, Gemini, hay Grok.

### Rà soát bảo mật (P3) — thực hiện 2026-07-13, KẾT QUẢ SẠCH

| Hạng mục | Kết quả |
|---|---|
| Nguồn | `https://github.com/revfactory/harness.git` |
| Commit đã ghim | `cceac68ea1d0ad198ef4b7b906cd238375836387` (2026-06-10) |
| Nội dung | 7 file, 120 KB, **thuần Markdown — không có code thực thi** |
| Hook (`preToolUse`/`postToolUse`/`settings.json`) | Không có |
| Shell / subprocess / `exec()` / `curl` | Không có |
| Network access | Không có |
| Đọc `.env` / home dir / credential | Không có |
| Git write (`commit`/`push`/`--force`) | Không có |

Vì là tài liệu thuần văn bản, Harness không tự thực thi được gì — mọi hành động
đều đi qua tool của Claude Code và chịu lớp permission ở đó. **Không cấp quyền
sửa hoặc push Git tự động.**

**Giữ lại:** phần `references/` (6 pattern kiến trúc) là tài liệu tốt, đáng đọc.

---

## D-005 — Không đưa agent orchestration vào runtime Phase 12E

**Ngày:** 2026-07-13 · **Trạng thái:** Ràng buộc cứng

Multi-agent chỉ nằm ở tầng phát triển. Không có agent nào chạy trong RAG security
pipeline lúc evaluation.

**Vì sao:** thêm orchestration vào runtime sẽ (a) thay đổi latency, (b) tạo biến
nhiễu, (c) khiến kết quả không so sánh được với baseline, và (d) khiến luận văn
không xác định được metric đến từ guard hay từ orchestration.

---

## D-006 — Không bật prompt compression cho prompt chứa code

**Ngày:** 2026-07-13 · **Trạng thái:** Ràng buộc cứng

**Vì sao:** compression (RTK/Caveman/LLMLingua) hoạt động bằng cách bỏ token nó
cho là dư thừa. Với văn xuôi thì chấp nhận được; với một diff hoặc prompt audit,
nó có thể lặng lẽ đổi tên biến, bỏ dấu ngoặc, hoặc cắt mất một điều kiện — và
auditor sẽ review một đoạn code không tồn tại. Rủi ro này không đáng để đổi lấy
vài phần trăm token.
