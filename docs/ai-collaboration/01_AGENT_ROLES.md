# Agent Roles

Mỗi vai làm đúng một việc. Vai nào có thể thay bằng script thì **phải** thay
bằng script.

## Sơ đồ

```
                    Người duy trì (Orchestrator + Adjudicator)
                                    │
                     ┌──────────────┴──────────────┐
                     │  docs/ai-collaboration/     │  ← memory chung
                     │  (00_PROJECT_STATE đọc đầu) │
                     └──────────────┬──────────────┘
                                    │
        Planner ──► Implementer ──► Verifier (SCRIPT) ──► Handoff
                                    │
              ┌─────────────────────┼─────────────────────┐  ← chạy SONG SONG
              │                     │                     │     trên CÙNG commit
      Security Auditor      Academic Auditor       Red-team Auditor
         (Code X)               (Gemini)                (Grok)
              └─────────────────────┼─────────────────────┘
                                    │
                         Người adjudicate → PASS / REVISE
```

## Bảng vai

| Vai | Ai/Model | Được làm | KHÔNG được làm |
|---|---|---|---|
| **Orchestrator / Adjudicator** | Người (Nguyen Van An) | Quyết định phase gate, tuyên bố DONE, phê duyệt commit | — |
| **Planner** | Claude Code, hoặc DeepSeek-R1 (rẻ) | Phân rã task, chọn cách tiếp cận | Sửa code |
| **Implementer** | Claude Code (logic phức tạp) hoặc Continue + DeepSeek (số lượng lớn) | Viết code, sửa test, cập nhật tài liệu | **Tự tuyên bố công việc của mình là PASS** |
| **Verifier** | **`scripts/verify_phase.ps1` — SCRIPT, không LLM** | Chạy test, hash, determinism, scope check; sinh evidence block | — (không có phán đoán) |
| **Security Auditor** | Code X | Tìm lỗi logic, invariant, edge case, fail-closed | Sửa code (chỉ báo cáo) |
| **Academic Auditor** | Gemini | Tính hợp lệ phương pháp, giới hạn claim, thống kê | Sửa code |
| **Red-team Auditor** | Grok | Độ phủ tấn công, rò rỉ template, độ mới holdout | Sửa code |
| **Payload Generator** | Hermes local (Ollama), khi cần | Sinh biến thể tấn công cho probe Phase 12E | **Đưa payload vào `datasets/v2/`** (đã FINAL freeze) |
| **Grunt worker** | Qwen2.5-Coder local | Docstring, fixture, format, refactor cơ học | Đụng vào logic guard hoặc validator |

## Vì sao Verifier phải là script

Trong Phase 12D, mọi con số dùng để đóng phase (255 passed, 578 passed, 9 hash
byte-identical) đều phải kiểm chứng được và tái lập được. Một LLM được hỏi
"test có pass không?" có thể trả lời sai — vì ảo giác, vì đọc nhầm output, hoặc
vì muốn làm hài lòng. Script thì không.

Đây cũng là lý do `verify_phase.ps1` in ra **evidence block** thay vì để agent
tự tường thuật: auditor nhận số liệu từ script, không từ lời kể của implementer.

## Vì sao Implementer không được tự approve

Đây không phải hình thức. Trong Phase 12D, ba vòng REVISE liên tiếp đều do
auditor bên ngoài phát hiện những thứ implementer đã tự tin là đã xong:

- Vòng 1: guard-independence bị vi phạm (validator import `app.guards.*`)
- Vòng 2: type-check chỉ phủ scalar, bỏ sót `list`/`dict` → `TypeError`
- Vòng 3: tài liệu mô tả sai chính hành vi của code vừa viết

Nếu implementer tự approve, cả ba đã lọt vào bản final.
