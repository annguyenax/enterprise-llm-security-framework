# Agent Roles

Mỗi vai làm đúng một việc. Vai nào có thể thay bằng script thì **phải** thay
bằng script.

## Sơ đồ

```
              Người duy trì (Final Adjudicator + Holdout Approver duy nhất)
                                    │
                     ┌──────────────┴──────────────┐
                     │  docs/ai-collaboration/     │  ← memory chung
                     │  (00_PROJECT_STATE đọc đầu) │
                     └──────────────┬──────────────┘
                                    │
   Claude Code (lead architect + primary implementer)
        └── GitHub Copilot (tactical, dưới review của Claude)
                                    │
              Qwen / Hermes preflight (advisory) ──► Verifier (SCRIPT)
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
      Grok technical/       Gemini methodology/      Code X reconciler
      security audit           claims audit        + artifact integrity
              └─────────────────────┼─────────────────────┘
                                    │
                       Người duy trì → PASS / REVISE

       Hermes3 local ──► adversarial candidates only (không ground truth)
```

## Bảng vai (Phase 12E.4 trở đi)

| Vai | Ai/Model | Được làm | KHÔNG được làm |
|---|---|---|---|
| **Final Adjudicator / Holdout Approver duy nhất** | Người duy trì | Quyết định phase gate, tuyên bố DONE, **cấp uỷ quyền holdout**, kết luận cuối | Chuyển quyền phê duyệt cuối hoặc quyền uỷ quyền holdout cho bất kỳ agent nào |
| **Lead Architect / Primary Implementer** | **Claude Code** | Thiết kế, viết code, sửa test, cập nhật tài liệu trong scope | **Tự audit công việc của mình; tuyên bố PASS/REVISE; tạo, sửa hoặc tự ký file authorization holdout; chạy holdout** |
| **Tactical Coding Support** | **GitHub Copilot** | Hỗ trợ soạn code chiến thuật **dưới review của Claude Code** | Quyết định thiết kế; phát hành verdict; đóng vai auditor |
| **Plan Reconciler / Artifact-Integrity Auditor** | **Code X** | Đối chiếu kế hoạch, audit tính toàn vẹn artifact (hash, kích thước, identity, forbidden-field scan) | **Implement code**; phê duyệt holdout |
| **Independent Technical / Security Auditor** | **Grok Web, audit chat riêng** | Audit code/commit độc lập, invariant, fail-closed, public bypass, adversarial coverage | Sửa code; dùng chung chat với planning; dựa vào tự-đánh-giá của implementer |
| **Independent Methodology / Claims Auditor** | **Gemini Web** | Metric, construct validity, thống kê, giới hạn claim | Sửa code; bỏ qua metric/statistical/claim gate |
| **Advisory Pre-Audit** | **Qwen2.5-Coder local**, **Hermes3 local** | Fixture, format, kiểm tra cơ học, sinh candidate/probe để người và auditor xem xét | Phát hành PASS/REVISE; biến candidate thành frozen benchmark ground truth |
| **Mechanical Verifier** | **`scripts/verify_phase.ps1`**, không LLM | Chạy test, hash, determinism, scope check; sinh evidence block | Phán đoán hoặc thay adjudicator |

## Quy tắc phân quyền Phase 12E.4

1. **Claude Code là primary implementer nhưng không được audit chính mình.** Mọi
   công việc của Claude Code phải qua Grok (technical/security) và Gemini
   (methodology/claims) độc lập, rồi mới tới adjudication của người duy trì.
2. **Code X không implement.** Vai của Code X ở 12E.4 là đối chiếu kế hoạch và
   audit tính toàn vẹn artifact sau khi chạy.
3. Grok planning và Grok audit bắt buộc dùng **hai chat tách biệt**. Audit chat
   phải đọc commit/evidence trực tiếp.
4. Qwen và Hermes chỉ là công cụ hỗ trợ, **không phát hành verdict**
   `PASS`/`REVISE`. Mọi finding phải được người duy trì hoặc Claude Code kiểm
   chứng trực tiếp.
5. Candidate do Hermes sinh chỉ dùng cho adversarial probing. Candidate đó
   **không** được trở thành label, ground truth hoặc artifact trong benchmark v2
   đã FINAL freeze.
6. Gemini Web vẫn là gate bắt buộc cho metric, thống kê và claim, kể cả khi Grok
   đã hoàn tất technical/security audit.
7. **Chỉ người duy trì mới cấp được uỷ quyền holdout.** Không agent nào được tạo,
   sửa hoặc tự ký file authorization. Không agent nào được chạy holdout khi chưa
   có file uỷ quyền do người duy trì cấp.

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
