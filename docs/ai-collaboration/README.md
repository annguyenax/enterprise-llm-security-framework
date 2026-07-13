# AI Collaboration Protocol

Lớp giao thức để nhiều AI (Claude, Code X, Gemini, Grok, DeepSeek local) cùng
làm việc trên repo này mà không giẫm chân nhau, không mất ngữ cảnh giữa các
phiên, và không tự phê duyệt chính mình.

**Đây là quy trình phát triển, KHÔNG phải một phần của hệ thống nghiên cứu.**
Không có agent orchestration nào được đưa vào runtime của RAG security pipeline
— làm vậy sẽ thêm biến nhiễu vào đo lường latency và khiến Phase 12E không so
sánh được với baseline.

## Ba nguyên tắc bất di bất dịch

1. **Verifier là script, không phải LLM.** Mọi số liệu (test count, hash,
   determinism) đến từ `scripts/verify_phase.ps1`. LLM có thể báo sai số; script
   thì không.
2. **Agent implement không tự approve chính mình.** Người viết code không phải
   người phê duyệt code. Auditor phải là model KHÁC.
3. **Người duy trì là adjudicator cuối cùng.** Không model nào có quyền tuyên bố
   một phase là DONE.

## Vì sao audit phải đa mô hình

Không phải để "có nhiều agent cho oai". Bằng chứng thực tế từ Phase 12A–12D:
mỗi auditor bắt được loại lỗi mà các auditor khác bỏ sót, vì chúng được train
khác nhau.

| Auditor | Bắt được gì (thực tế đã xảy ra) |
|---|---|
| Code X | Lỗi invariant tinh vi: `list` không hashable làm `x in SET` ném `TypeError`; `bool` là subclass của `int` khiến type-check integer bị lọt |
| Gemini | Lỗi phương pháp luận: 23 family / 120 case là quá nhỏ để báo cáo phần trăm theo từng family |
| Grok | Góc nhìn attacker: độ mới của holdout, rò rỉ template, nhãn residual-risk có trung thực không |

Một subagent Claude audit code do Claude viết sẽ không tái tạo được sự đa dạng
này — đó là lý do lớp audit nằm NGOÀI mọi framework agent nội bộ.

## Các file trong thư mục này

| File | Vai trò |
|---|---|
| `00_PROJECT_STATE.md` | Trạng thái hiện tại: phase nào, commit nào, gate nào đã qua. **Agent đọc file này ĐẦU TIÊN.** |
| `01_AGENT_ROLES.md` | Ai làm gì, model nào, quyền hạn gì, cấm gì |
| `02_ROUTING_RULES.md` | Task loại nào thì gửi model nào |
| `03_HANDOFF_PROTOCOL.md` | Schema bàn giao giữa các agent (YAML, ngắn, có cấu trúc) |
| `04_DECISIONS.md` | Nhật ký quyết định kiến trúc — vì sao chọn A thay vì B |
| `05_OPEN_QUESTIONS.md` | Câu hỏi chưa trả lời, việc hoãn lại |
| `templates/` | Khung prompt cho fix-request và audit-request |
| `handoffs/` | Bàn giao thực tế của từng vòng (`phase-12e-001.yaml`, ...) |

## Vòng lặp chuẩn

```
1. Người + Claude Code: plan ngắn (1 phiên, không tách agent)
2. Implementer: code + chạy scripts/verify_phase.ps1 -> điền handoff YAML
3. Commit theo vòng (audit phải gắn với một commit hash cụ thể)
4. SONG SONG: Code X + Gemini + Grok audit CÙNG commit đó
   (mỗi bên nhận: handoff + diff + câu hỏi theo domain của mình -- KHÔNG gửi
    cả transcript, KHÔNG gửi cả repo)
5. Người adjudicate: tất cả PASS -> vòng sau; có REVISE -> quay lại bước 2
```

## Điều tuyệt đối không làm

- **Không** đưa API key vào file config trong repo hoặc trong `~/.continue/`.
  Dùng biến môi trường. (Đã từng lộ một lần — xem `04_DECISIONS.md`.)
- **Không** dùng proxy/router bên thứ ba để "dùng miễn phí" model trả phí
  (OmniRoute, 9Router). Vừa vi phạm ToS, vừa là supply-chain risk — đúng loại
  rủi ro đồ án này nghiên cứu.
- **Không** bật prompt compression cho bất cứ prompt nào chứa code hoặc diff.
  Compression bỏ token nó cho là dư thừa; với code nó có thể lặng lẽ đổi tên
  biến hoặc cắt mất một điều kiện, và bạn sẽ audit một đoạn code không tồn tại.
- **Không** sửa 9 artifact đã FINAL freeze trong `datasets/v2/`. Mọi thay đổi
  ở đó = benchmark v3 + phải audit lại từ đầu.
