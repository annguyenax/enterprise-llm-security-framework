# Review W2c (uncommitted, parent `db791b4`)

**Verdict: PASS**

## Phạm vi
- Chỉ audit `0021` nhóm (a): `context_guard_sanitize_emptied`, không fold.
- 5 case nhóm (b) không sửa. Không val. Đúng ràng buộc.

## Kiểm tra
- Patch tổng quát, không logic case/family/token: thêm reason `context_guard_sanitize_emptied`, loại chunk rỗng sau SANITIZE như content exclusion, tách khỏi `aggregate_budget_exceeded`. Đúng mô tả.
- Không fold: giữ `final_decision` semantics, fail-closed qua `all_context_blocked` hiện có. Test mới cover case chỉ 1 chunk bị emptied.
- Không tăng FPR: từ chối fold vì `0012` thành FP (+0.083 FPR). Quyết định đúng, tránh overfit rank-1.
- Test assertion đổi `context_guard_sanitize` → `context_guard_sanitize_emptied` là deliberate, đã review: PASS.
- Metrics giữ nguyên AOMR 8/14, FPR 1/12; `0021` vẫn mismatch nhưng chỉ sửa audit reason: đúng kỳ vọng.

## Issue
- Không có `P3W2C-FIX/BLOCK/NEW`.

## Ghi chú không chặn
- `0021` còn mismatch là residual đã ghi nhận, không phải defect mới.
- Nhóm (b) (`0014/0015/0016/0018/0019`) là retrieval/label/corpus artefact, đề xuất maintainer-only, không thuộc W2c.
