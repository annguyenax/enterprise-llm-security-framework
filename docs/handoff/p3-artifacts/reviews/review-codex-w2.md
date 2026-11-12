**Verdict: PASS** cho W2 `f47dfec`, parent đúng `464218b`. Không phát hiện issue cần gán `P3W2-FIX`, `P3W2-BLOCK` hoặc `P3W2-NEW`.

- **Không fold `LOG_ONLY`:** đúng phạm vi context từng chunk và aggregate; vẫn giữ kết quả trong stage/audit. Input Guard và Output Guard giữ cách fold hiện tại. Các nhánh chặn context vẫn hoạt động. Xem [rag_query.py:146](/workspace/shield-team/enterprise-llm-security-framework/app/services/rag_query.py:146).
- **Ngưỡng `0.5`:** so sánh độ lớn score phù hợp SQLite BM25 âm. Chunk `SANITIZE` dưới ngưỡng bị loại trước aggregate/provider; bằng ngưỡng vẫn được sanitize và fold. Score không so sánh an toàn thì giữ hành vi cũ. Context rỗng vẫn trả `BLOCK`. Xem [rag_query.py:158](/workspace/shield-team/enterprise-llm-security-framework/app/services/rag_query.py:158), [nhánh loại chunk:777](/workspace/shield-team/enterprise-llm-security-framework/app/services/rag_query.py:777).

Đã đọc after trong `/workspace/shield-data/v2-dev-runs/after-f47dfec`; commit, split development và hash kết quả khớp manifest. Đếm lại theo định nghĩa metric hiện có:

| Metric | Before | After |
|---|---:|---:|
| C0 AOMR | 4/14 | **8/14** |
| C0 mismatch | 10/14 | **6/14** |
| C0 FPR | 7/12 | **4/12** |
| C0 coverage | 30/30 | **30/30** |
| C3 FPR | 4/12 | **4/12** |

After C0 không có error, timeout hoặc skipped case.

**Ghi chú không chặn:** `0.5` vẫn là heuristic trên dev, chưa chứng minh tối ưu hoặc phù hợp scorer khác. FPR ở đây tính theo outcome mismatch: ba ca benign còn `SANITIZE` vẫn trả lời, một ca lệch kỳ vọng `no_hits`; không nên diễn giải thành bốn request bị chặn. Kết quả chỉ thuộc dev/in-sample/MOCK.

`git diff --check` sạch. Kết quả **147 + 79 passed** theo coordinator; tôi không chạy lại tests, không chạy val, không đọc holdout/`cases/validation.jsonl`, không sửa hay ghi file.
