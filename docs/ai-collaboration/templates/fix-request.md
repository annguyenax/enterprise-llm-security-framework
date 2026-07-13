# Template: Fix Request

Giao việc cho Implementer (Claude Code hoặc Continue + DeepSeek) sau khi có
verdict REVISE từ auditor.

---

```
Bạn là implementation agent. Sửa các finding dưới đây.

Repository: <đường dẫn>
Branch: <branch>
Base commit: <commit>

## Đọc trước (bắt buộc)
- docs/ai-collaboration/00_PROJECT_STATE.md
- docs/ai-collaboration/01_AGENT_ROLES.md
- <báo cáo audit chứa finding>

## Finding cần sửa
<dán nguyên các Critical + blocking Major từ báo cáo audit>

Với MỖI finding, bạn phải:
1. Tái tạo lại lỗi trước (chứng minh nó có thật)
2. Sửa nguyên nhân gốc, không vá triệu chứng
3. Thêm regression test chứng minh lỗi không quay lại
4. Chỉ khi đó mới cập nhật tài liệu

## Phạm vi ĐƯỢC sửa
- <liệt kê cụ thể>

## Phạm vi CẤM sửa
- datasets/v2/ (9 artifact đã FINAL freeze — đổi 1 byte = benchmark v3 + audit lại)
- app/ trừ khi finding chỉ đích danh
- requirements.txt (KHÔNG cài gói mới; httpx2 là typosquat, tuyệt đối không)
- reports/evaluation/, report-latex-template/
- <phase tiếp theo>

## Bắt buộc trước khi kết thúc
1. Chạy: .\scripts\verify_phase.ps1
   Mọi hạng mục phải PASS. Dán nguyên EVIDENCE BLOCK vào câu trả lời.
2. Điền handoff: docs/ai-collaboration/handoffs/<task_id>.yaml
   theo schema trong 03_HANDOFF_PROTOCOL.md
3. Cập nhật docs/ai-collaboration/00_PROJECT_STATE.md nếu trạng thái phase đổi

## Cấm
- Không commit, không push (người duy trì quyết định)
- Không tự tuyên bố PASS/APPROVE/DONE — bạn là implementer, không phải adjudicator
- Không báo số liệu test từ trí nhớ; chỉ dán từ output của script
- Không bắt đầu phase tiếp theo

## Trả lời bằng tiếng Việt, gồm:
1. Nguyên nhân gốc của từng finding
2. Đã sửa gì, ở đâu
3. Test mới thêm (tên hàm cụ thể)
4. EVIDENCE BLOCK từ verify_phase.ps1
5. Rủi ro còn lại (không được để trống giả tạo)
6. Việc đã cố ý KHÔNG làm và vì sao
```
