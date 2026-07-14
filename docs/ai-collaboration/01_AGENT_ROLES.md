# Agent Roles

Mỗi vai làm đúng một việc. Vai nào có thể thay bằng script thì **phải** thay
bằng script.

## Sơ đồ

```
                    Người duy trì (Final Adjudicator)
                                    │
                     ┌──────────────┴──────────────┐
                     │  docs/ai-collaboration/     │  ← memory chung
                     │  (00_PROJECT_STATE đọc đầu) │
                     └──────────────┬──────────────┘
                                    │
       Grok Planner ──► Code X ──► Qwen preflight ──► Verifier (SCRIPT)
      (planning chat)                (advisory)               │
                                    │
                         ┌───────────┴───────────┐
                         │                       │
               Grok combined audit       Gemini academic
                 (audit chat riêng)       / statistical
                         └───────────┬───────────┘
                                    │
                       Người duy trì → PASS / REVISE

       Hermes3 local ──► adversarial candidates only (không ground truth)
```

## Bảng vai

| Vai | Ai/Model | Được làm | KHÔNG được làm |
|---|---|---|---|
| **Final Adjudicator / Holdout Approver** | Người duy trì | Quyết định phase gate, tuyên bố DONE, phê duyệt holdout và kết luận cuối | Chuyển quyền phê duyệt cuối cho agent |
| **Planner** | **Grok Web, planning chat riêng** | Phân rã task, chọn cách tiếp cận, xác định gate | Sửa code; dùng cùng chat với Grok Auditor |
| **Primary Implementer** | **Code X** | Viết code, sửa test, cập nhật tài liệu trong scope | **Tự approve implementation của mình hoặc tuyên bố PASS/REVISE** |
| **Mechanical / Local Preflight** | **Qwen2.5-Coder local** | Fixture, format, kiểm tra cơ học, gợi ý lỗi cục bộ | Phát hành PASS/REVISE; findings chưa được người hoặc Code X kiểm chứng trực tiếp |
| **Mechanical Verifier** | **`scripts/verify_phase.ps1`**, không LLM | Chạy test, hash, determinism, scope check; sinh evidence block | Phán đoán hoặc thay adjudicator |
| **Combined Technical / Security / Red-team Auditor** | **Grok Web, audit chat riêng** | Audit code/commit độc lập, invariant, fail-closed, public bypass, adversarial coverage | Sửa code; dùng planning chat; dựa vào tự-đánh-giá của implementer |
| **Academic / Statistical Auditor** | **Gemini Web** | Metric, construct validity, thống kê, giới hạn claim | Sửa code; bỏ qua metric/statistical/claim gate |
| **Adversarial Candidate Generator** | **Hermes3 local** | Sinh candidate/probe để người và auditor xem xét | Phát hành PASS/REVISE; biến candidate thành frozen benchmark ground truth |

## Quy tắc phân quyền Phase 12E

1. Grok Planner và Grok Auditor bắt buộc dùng **hai chat tách biệt**. Audit chat
   phải đọc commit/evidence trực tiếp, không kế thừa kết luận tự tin từ planning chat.
2. Code X là primary implementer nhưng **không được approve implementation của
   chính mình**. G1/G2/G4 cần auditor đúng vai và final adjudication của người duy trì.
3. Qwen và Hermes chỉ là công cụ hỗ trợ, không phát hành verdict `PASS`/`REVISE`.
   Mọi finding của Qwen phải được người duy trì hoặc Code X kiểm tra trực tiếp.
4. Candidate do Hermes sinh chỉ dùng cho adversarial probing. Candidate đó không
   được trở thành label, ground truth hoặc artifact trong benchmark v2 đã FINAL freeze.
5. Gemini Web vẫn là gate bắt buộc cho metric, thống kê và claim, kể cả khi Grok
   đã hoàn tất combined technical/security/red-team audit.

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
