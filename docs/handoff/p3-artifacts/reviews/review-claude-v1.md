VERDICT: FIX

W1: FIX — Owner, blocker và phụ thuộc đều hợp lý, nhưng còn hai lỗ hổng. (1) Câu "không copy holdout lên box nếu không cần" để ngỏ ngoại lệ; phải đổi thành cấm tuyệt đối. Pass cũng cần thêm bước kiểm working set không chứa holdout ID theo manifest mà không phải mở nhãn. (2) Output ghi dev/val "chỉ trên máy An", trong khi W2 và W3 do Claude/Codex làm trên box/runner. Chưa rõ dữ liệu chạy ở đâu và đi theo đường nào.

W2: PASS — Các giả thuyết, tử/mẫu số, quy tắc n<10, owner và phụ thuộc vào W1 đều đúng. Holdout P2 không được dùng.

W3: FIX — Ngưỡng đã có nhãn "đề xuất". Còn ba vấn đề. (1) Tune và kiểm cùng trên dev+val thì val không còn là kiểm tra độc lập; nên tune trên dev và xác nhận trên val. (2) Pass chỉ yêu cầu "AOMR ≥ C3", trong khi C3 trên P2 là 11/28. Cổng W12 đòi AOMR ≥ 0.80 nhưng W3 không có mục tiêu AOMR tương ứng, nên có thể freeze một bản gần như chắc FAIL. (3) Thiếu định nghĩa artifact freeze (commit, config, GuardProfile).

W4: PASS — Owner và người rà đúng thế mạnh, xung đột license của deepset được ghi, có cấm upload. Ghi chú: ledger cần ghi rằng README của HackAPrompt chưa đọc được (401), và ghi mục đích từng tập (đo TPR hay FPR; Gandalf chỉ có câu tấn công; XSTest đo over-refusal an toàn, không phải injection).

W5: FIX — Thiếu ba thứ. (1) Kiểm tách biệt, ví dụ khử trùng bằng hash, giữa P3-holdout và các tập ngoài, dev/val đã dùng ở W2/W3/W10. (2) Quy tắc khi lần chạy one-shot hỏng vì hạ tầng (OOM, crash) thì có tính là "1 attempt" hay không. (3) Chưa nói P3-holdout chạy với Judge ON hay OFF (liên quan W8). Ngưỡng và hạn chế về người giữ holdout đã ghi đúng.

W6: FIX — Giới hạn "chỉ bề mặt query" được giữ đúng. Nhưng Pass "chạy xong" không đo được, và chưa định nghĩa ASR/block-rate: lấy theo detector của garak trên output hay theo `final_decision` của Shield. Cũng cần ghi probe nào cần tải payload, vì yêu cầu là offline.

W7: FIX — Có ghi blocker về API, tiêu chí retrieve-hit đúng. Còn thiếu ba điều. (1) Poisoned docs phải nằm trong corpus/index tách riêng, có cách rollback, để không làm bẩn corpus dev/val/holdout. (2) Cần ghi ràng buộc CC-BY-SA khi tạo tài liệu phái sinh từ BIPIA. (3) Query phải được chốt trước, không được thiết kế để tối đa hoá retrieve-hit.

W8: FIX — Trạng thái UNKNOWN của Judge-on-RAG được giữ đúng. Còn hai lỗ hổng. (1) Model judge chưa được nêu tên và không có trong bảng license ở mục 2. (2) W8 sửa đường RAG, nhưng thứ tự với freeze W3 và one-shot W5 không xác định, nên không rõ code nào được đánh giá trên holdout.

W9: PASS — Ngưỡng và N đều có nhãn chờ An chọn. Plan cấm cộng percentile, ghi stage bỏ qua là N/A, cấm trích latency P2. Ghi chú: với N e2e từ 100 đến 200 thì p99 không ổn định, nên đánh dấu là chỉ để tham khảo. Cũng cần ghi số latency đo trên commit nào (bản freeze của W3).

W10: FIX — License và giới hạn của Llama Guard 3 1B đã phản ánh đúng. Còn ba thiếu sót. (1) Ngưỡng phân loại của Prompt Guard 2 phải chốt trước, không tune trên tập so sánh. (2) Không lặp lại cảnh báo Prompt Guard 2 không có tiếng Việt cho phần nội bộ tiếng Việt. (3) Chưa rõ baseline có chạy trên P3-holdout hay không; nếu có thì mỗi baseline cũng phải one-shot với config đã freeze.

W11: PASS — Spike có quyết định go/no-go bằng văn bản và không trộn với hàng regex. Owner hợp lý.

W12: FIX — Ngưỡng có nhãn, có quy tắc FAIL thì không chạy lại, các cổng dừng đúng. Còn hai vấn đề. (1) Phải nói rõ các hàng baseline trên P3-holdout có được chạy hay không, và nếu có thì theo luật one-shot nào. (2) Cổng AOMR ≥ 0.80 không khớp tiêu chí của W3 (xem W3).

DONE: PASS — Đủ 7 điều kiện; cho phép Judge ON = UNKNOWN; giữ giới hạn của garak/PyRIT; chấp nhận P3 FAIL như một lựa chọn có nhãn chờ An duyệt. Ghi chú: nên thêm "quyết định go/no-go W11 đã có văn bản" và "ledger W4 đã khép".

LICENSE: PASS — Bảng license phản ánh đúng các kết luận đã kiểm: deepset có xung đột, chưa dùng; HackAPrompt là MIT nhưng gated, README chưa đọc; Prompt Guard 2 và Llama Guard 3 dùng Llama Community, không có tiếng Việt; BIPIA có phần CC-BY-SA. Bất đồng giữa các nguồn nghiên cứu được giải quyết đúng. Hai điểm cần kiểm lại: bảng gộp ngôn ngữ của Prompt Guard 2 86M và 22M dù hai card có thể khác nhau; license của Llama Guard 3 8B chỉ "theo nghiên cứu", chưa kiểm card.

TIME: PASS — Giữ cả bốn ước lượng, nêu rõ chúng không khớp nhau và không chốt lịch.

NEW-01: Phải định nghĩa chỗ chạy và luồng dữ liệu dev/val (máy An, box hay runner) cho W1–W3 và W9–W10, kèm cam kết holdout không bao giờ rời máy An.
NEW-02: Cần quy tắc tách dev (tune) với val (xác nhận) dùng chung cho W2, W3 và W10.
NEW-03: Cần kiểm chống rò rỉ chéo (dedupe hash) giữa tập ngoài ở W4, dev/val và P3-holdout.
NEW-04: Mục 2 thiếu một dòng cho model Semantic Judge (tên, digest, license).
NEW-05: Mình không kiểm được các tham chiếu code trong plan (`app/api/routes.py`, `latency_ms` trong `app/services/rag_query.py`, `_normalize_for_detection`, khoá L2 `latency_reportable`, `--include-holdout-diagnostic`, `RATE_REPORTING_MIN_N`). Lệnh đọc checkout bị chặn vì thư mục nằm ngoài phạm vi được phép. Cần một người khác đối chiếu với `ff41f92` trước khi bắt đầu W6, W8 và W9. Hash plan đã kiểm, khớp c170e2ee…b0c7.
