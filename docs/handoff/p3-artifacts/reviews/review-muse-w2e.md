# Review W2e — H3b+H4 (uncommitted, parent `40e4461`)

- Phạm vi đã đọc: `w2e/h3b-h4.patch`, `w2e/h3b.patch`, `w2e/w2e-results.md`. Không sửa code, không commit/push, không val/holdout/web.

## Verdict: PASS

Không phát hiện defect chặn merge dev. Không mở issue `P3W2E-FIX` / `P3W2E-BLOCK` / `P3W2E-NEW`.

## Vì sao PASS

- Mở rộng đúng cam kết: giữ comparator H1 (`max |score|`, tie tính, rank fallback), chỉ thêm kind `sanitize_emptied` (H3b) + `human_review` (H4), thứ tự `block → human_review → sanitize_emptied`.
- Fail-closed qua đường H1 có sẵn: `block / all_context_blocked`, không gọi provider. `BLOCK` giữ nguyên reason code nên record H1 không đổi.
- Hẹp đúng chỗ: partial-sanitize còn text không veto, `LOG_ONLY` không trigger, exclusion yếu hơn survivor không veto, không survivor đi đường empty-context cũ.
- Số liệu C0 MOCK in-sample khớp mô tả: `10/14 → 12/14` (H3b+H4; H3b riêng `11/14`), FPR `1/12` giữ (`V2-DEV-0011` đã biết). Chỉ đổi `0021` (emptied) + `0018` (human_review), đúng 5/10 record timing-free.
- Không fail-closed diện rộng: mixed `0025–0028` giữ `allow`, benign `0012` không fire vì emptied yếu hơn survivor. `0014`/`0019` giữ nguyên với lý do trần/Frozen-corpus chấp nhận được.
- Test: 156 pass (3 file liên quan), bộ rộng + W13 theo coordinator pass; full-suite diff failure-set trùng baseline (thiếu `datasets/v2`, môi trường).

## Ghi chú không chặn

- H4 biến would-be `human_review` thành `block / all_context_blocked`. Cố ý, nhất quán H1, nhưng mất tín hiệu routing reviewer; nếu sau này muốn stop riêng thì làm rule riêng.
- `h3b.patch` còn nhánh `human_review` thừa trong `_is_unusable_kind` (chờ H4). Vô hại.
- Gain `+2/14` in-sample, chọn policy sau khi nhìn `0018`/`0021`; Wilson 95% chồng lấn. Coi là policy có nguyên tắc, không phải cải thiện đã chứng minh — cần val/holdout có thẩm quyền trước khi tuyên bố tổng quát.
