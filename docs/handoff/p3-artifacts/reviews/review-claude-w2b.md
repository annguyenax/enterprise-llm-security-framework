Đang chốt review: đã đọc patch, code fold và chạy lại `tests/test_rag_pipeline.py` (77 passed). Phần dưới là review.

# Review chéo W2b — `db791b4`

**Verdict: PASS** (không có FIX hay BLOCK; có 2 ghi chú không chặn)

Tôi đã đọc diff, `app/services/rag_query.py` quanh bước fold cuối (khoảng dòng 1156) và `w2b-results.md`. Tôi chạy lại `tests/test_rag_pipeline.py` trên HEAD `db791b4`: 77 passed. Tôi không tự chạy lại replay Mock, nên các số AOMR/FPR bên dưới là số trong báo cáo, tôi chưa kiểm chứng độc lập. Tôi cũng không động tới val, holdout hay các đường dẫn bị cấm.

## Issue
- P3W2B-FIX: không có.
- P3W2B-BLOCK: không có.
- P3W2B-NEW: không có.

## Xác nhận

**Sửa đúng nguyên nhân.**
- Trước đó caller ghi đè outcome của chunk thành `Decision.SANITIZE` khi bị clip hoặc loại vì budget.
- Outcome đó chạy vào `per_chunk_decisions` và fold vào `final_decision`, kể cả khi mọi guard tắt.
- Giờ caller giữ nguyên `context_outcomes[chunk_id][2]`, tức quyết định gốc của per-chunk guard (hoặc `ALLOW` khi `rag_context_guard` tắt).
- Chỉ reason code trong provenance đổi thành `aggregate_budget_*`.

**Hành vi fold còn lại không đổi.**
- Chunk bị loại có `accepted=False` nên không fold, như trước.
- SANITIZE thật của chunk được chấp nhận vẫn fold. Test `..._preserves_real_security_sanitize` phủ cả hai giới hạn (global và per-chunk) và cả aggregate guard bật/tắt.
- Chunk neighbour SANITIZE low-relevance vẫn bị loại sớm bằng `continue`, trước bước budget.
- Hai bước sau không bị chạm: bounding và aggregate guard vẫn kiểm tra đúng text gửi cho provider, và fail-closed ở aggregate vẫn nguyên.

**Audit trung lập.**
- Stage `context_budget` có `decision=None` và chỉ mang `chunk_id`, không có text.
- `routes.py:376` truyền `sr.decision` thẳng sang `StageResultResponse`. Tôi chưa mở schema đó, nhưng các stage `*_disabled_ablation` hiện có đã dùng `decision=None` nên chắc nó nhận được.
- Test kiểm tra audit event có `context_budget` và không lộ nội dung context.

**Không tắt context.** Không có thay đổi nào ở `GuardProfile`, rule, ngưỡng relevance hay retrieval. Chỉ sửa `rag_query.py` và test. Phần SANITIZE thật của context guard vẫn được kiểm tra.

**Không đổi AOMR để lấy FPR.**
- AOMR không đổi ở cả 8 cấu hình: C0 8/14 → 8/14, C3 5/14 → 5/14.
- Đúng 24 thay đổi `final_decision`, đều là `sanitize` → `allow` ở 0003, 0006, 0012 trong C0–C7.
- Mọi stage guard gốc, retrieval, stop, số redaction và hash của context/answer gửi provider đều giữ nguyên.
- FPR giảm (C0 4/12 → 1/12, C3 4/12 → 1/12) vì bỏ SANITIZE sai, không phải vì thêm allow hay nới chặn.

**Không overfit từng case.** Fix nằm ở logic chung của bước budget. Test dùng dữ liệu tổng hợp, không nhúng text case chính thức. Ba case 0003/0006/0012 cùng một lỗi pipeline (0012 còn một SANITIZE thật nhưng chunk đó đã rỗng và bị loại sẵn).

## Ghi chú không chặn
1. **V2-DEV-0011 còn FP.**
   - Nhãn kỳ vọng `no_hits`, nhưng retrieval OR của SQLite trả 5 hit.
   - Giữ nguyên là đúng, ghi nhận là mismatch nhãn/retrieval.
   - Không nên báo FPR 1/12 như bằng chứng guard tốt hơn. Phần còn lại là khoảng cách retrieval/nhãn, không phải guard.
2. **Reason code `aggregate_budget_exceeded` dùng cho chunk bị cắt thành rỗng** (như chunk sanitize-rỗng của 0012). Hành vi cũ được giữ, báo cáo cũng nêu rõ. Về sau có thể tách mã riêng để telemetry không gây hiểu nhầm là cạn budget toàn cục. Không cần làm ở commit này.

Về số liệu: các số 8/14, 1/12, 160 related + 79 W13 là của báo cáo W2b. Theo CLAUDE.md, các số này chưa phải kết quả `verify_phase.ps1` hay official analyzer. Chúng chỉ là chẩn đoán development / in-sample / MOCK, không dùng làm claim validation hay hiệu quả với model thật.

Báo cáo nói test TestClient mặc định bị treo trong môi trường của họ (phải ép uvloop). Tôi chỉ chạy `test_rag_pipeline.py`, không chạy các file route. Con số 160 cho các file route vẫn dựa vào lời báo cáo.
