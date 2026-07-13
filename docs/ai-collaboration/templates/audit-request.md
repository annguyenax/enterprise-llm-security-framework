# Template: Audit Request

Điền chỗ trống, gửi cho **một** auditor. Ba auditor chạy **song song** trên
**cùng một commit**.

> **Không gửi kèm:** transcript, toàn bộ repo, hay diff dài dán thô. Auditor tự
> đọc commit trên GitHub. Nếu repo private, đính kèm `git diff` của đúng những
> file trong `modified_files`.

---

```
Thực hiện READ-ONLY audit cho <PHASE>.

Repository: <URL hoặc đường dẫn>
Branch: <branch>
Commit cần review: <base_commit>      ← BẮT BUỘC, audit phải gắn với commit này

Không sửa file. Không commit. Không bắt đầu phase tiếp theo.

## Ngữ cảnh (đọc trước)
- docs/ai-collaboration/00_PROJECT_STATE.md
- docs/ai-collaboration/handoffs/<task_id>.yaml
- <tài liệu domain liên quan>

## File đã thay đổi
<dán modified_files từ handoff>

## Bằng chứng verification (từ scripts/verify_phase.ps1, KHÔNG tự gõ lại)
<dán nguyên EVIDENCE BLOCK>

## Rủi ro implementer đã tự khai
<dán known_risks từ handoff>

## Phạm vi audit của bạn
<CHỌN MỘT KHỐI BÊN DƯỚI THEO AUDITOR>

## Định dạng trả lời bắt buộc
# <Auditor> <Phase> Audit

## Repository State Verified
- Branch:
- Commit:
- Actual artifacts inspected: yes/no

## <các mục theo domain>

## Critical Issues
None hoặc danh sách

## Major Issues
Mỗi mục: artifact/method · evidence · impact · minimal correction · blocking yes/no

## Minor Issues

## Required Fixes Before <gate>
None hoặc danh sách

## Deferrable to Phase <N+1>

## Final Verdict
PASS hoặc REVISE
```

---

## Khối phạm vi — Code X (Security / Technical)

```
Tìm lỗi logic, invariant bị vi phạm, edge case chưa xử lý, và đường fail-closed
bị hở. Cụ thể kiểm tra:
- Giá trị malformed (list/dict/bool/null) có gây exception chưa bắt không
- Thứ tự validation: type-check có TRƯỚC membership/hash không
- Có rò rỉ đường dẫn tuyệt đối hoặc nội dung thô ra thông báo lỗi không
- Test có thật sự chứng minh điều nó tuyên bố không, hay chỉ pass vờ
- Tài liệu có mô tả ĐÚNG hành vi thật của code không
```

## Khối phạm vi — Gemini (Academic)

```
Đánh giá tính hợp lệ học thuật cho một luận văn đại học:
- Construct validity: benchmark có đo đúng thứ nó tuyên bố đo không
- Internal validity: split có thật sự độc lập không
- Statistical reporting: cỡ mẫu có đủ cho loại claim đang đưa ra không
- External validity: giới hạn claim đã được ghi rõ chưa
- Có chỗ nào circular validation (test guard bằng chính logic của guard) không
Ghi rõ nếu bạn KHÔNG truy cập được artifact thật ("CANNOT VERIFY").
```

## Khối phạm vi — Grok (Red-team)

```
Đánh giá độ phủ tấn công theo góc nhìn attacker:
- Family tấn công nào còn thiếu
- Holdout có thật sự mới, hay chỉ là biến thể bề mặt của development
- Có template/prefix cố định nào cho phép phân loại trivial không
- Benign counterexample có đủ khó không, hay quá dễ
- Nhãn residual-risk có trung thực không, hay đang che giấu điểm yếu
Đề xuất probe adversarial cho phase sau (không phải case mới cho benchmark đã freeze).
```
