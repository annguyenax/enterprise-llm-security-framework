VERDICT: FIX
W1: FIX — Chưa chốt nơi chạy (box hay máy An) và câu "không copy holdout lên box nếu không cần" để ngỏ đường copy holdout P2, cần cấm tuyệt đối và ghi rõ runner đo ở đâu.
W2: FIX — Ngưỡng n<10 thiếu nhãn "đề xuất, chờ An duyệt" và thiếu blocker An-duyệt trong khi W5/W12 gán RATE_REPORTING_MIN_N=10 cho An, cần gắn nhãn và thống nhất một ngưỡng.
W3: PASS — Đủ output patch-branch, ngưỡng dev/val gắn nhãn đầy đủ, owner Codex/Claude đúng, cấm xem P2 để viết rule và cấm giảm FPR bằng tắt context.
W4: PASS — Ledger và tập con khớp card mục 2 (deepset loại khỏi bảng chính, gated chờ An), owner Muse/Argon đúng thế mạnh, đủ blocker và song song W1.
W5: PASS — One-shot có freeze threshold/contract trước khi chạy, 1 attempt ủy quyền, cấm flag diagnostic lúc tune, P2 gắn USED kèm tử/mẫu và hash, khai hạn chế trùng tác giả.
W6: PASS — Harness garak/PyRIT ghi rõ giới hạn chỉ bề mặt query và cấm tuyên bố đã đo indirect injection, owner Codex/Claude đúng, đủ blocker package và API.
W7: PASS — Chỉ tính success khi tài liệu độc vào context (không retrieve thì out-of-scope), blocker API không nhận context tùy ý đã kiểm đúng (RagQueryRequest extra=forbid, chỉ query+top_k).
W8: PASS — Giữ overhead Judge-on-RAG là UNKNOWN, cấm tuyên bố số Judge ON trước khi xong, ghi rõ fail-closed/open và blocker VRAM 6GB, đúng thứ tự trước W9 Judge ON.
W9: PASS — Dùng latency_ms có sẵn đã kiểm trong rag_query.py, cấm cộng percentile và cấm trích số P2 (latency_reportable=false), N e2e để An chọn một chứ không chốt trước.
W10: FIX — Owner "Muse (chấp nhận license gated)" mâu thuẫn Blocker "An phải accept Llama Community/HF", cần sửa thành An chấp nhận còn Muse chỉ chuẩn bị ledger.
W11: FIX — Phụ thuộc "W10 xong hoặc song song sau spike 1 ngày" mơ hồ, cần chốt một quy tắc (spike độc lập, hàng baseline chờ tập so sánh W10).
W12: PASS — Cổng official trên P3-holdout gắn nhãn đề xuất, FAIL vẫn công bố không chạy lại cùng holdout, bốn cổng STOP bao phủ blocker (xem P2, tắt context, deepset, OOM).
DONE: PASS — 7 điều kiện bao phủ P2-USED, freeze+one-shot, giới hạn query-surface, indirect qua retrieval, latency real-or-UNKNOWN, bảng so sánh license-đã-kiểm, toàn bộ chờ An duyệt.
LICENSE: PASS — Card 12 mục ghi đúng xung đột deepset, Llama Community phi-OSI, PG2/LG3 không hỗ trợ VI chính thức, checkpoint 1.12GB, và được W4/W10/W12 phản ánh đúng.
TIME: PASS — Trình đủ 4 ước lượng kèm độ tin cậy, nêu rõ mâu thuẫn ngày-vs-tuần, không chốt lịch và giao lịch chi tiết cho An duyệt.
NEW: NONE
