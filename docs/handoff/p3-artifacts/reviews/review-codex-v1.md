VERDICT: FIX
W1: PASS — Có output kiểm manifest, owner dữ liệu phù hợp và điều kiện loại holdout khỏi working set.
W2: PASS — Có giả thuyết cần kiểm, tử/mẫu số, phụ thuộc W1 và giới hạn dev/val; ngưỡng n được bao phủ bởi nhãn đề xuất chung.
W3: PASS — Có patch, ngưỡng đề xuất chờ An duyệt, review độc lập và cấm dùng P2 hoặc tắt context để đạt FPR.
W4: PASS — Có ledger, tập nhập local, owner đúng thế mạnh và blocker chấp nhận gate; deepset được loại khỏi bảng chính khi chưa rõ.
W5: FIX — Cần quy định kiểm trùng/phơi nhiễm P3 với dev/val và seed W6/W7/W10, đồng thời freeze toàn bộ cấu hình đánh giá thay vì chỉ nêu W3 khi W8 còn có thể đổi pipeline.
W6: FIX — Giới hạn query được giữ đúng, nhưng ASR chưa có tiêu chí thành công, scorer và cách tính mẫu số/lỗi; block-rate không đủ thay thế ASR.
W7: FIX — Cần xác định retrieve-hit trước guard và phân biệt context được kiểm với context tới provider để tránh loại các lượt guard chặn đúng khỏi mẫu số.
W8: PASS — Có output tích hợp, owner code/review phù hợp, blocker VRAM và giữ overhead Judge-on-RAG là UNKNOWN trước khi đo.
W9: FIX — Cần chốt N cho từng nhóm báo cáo và cách thể hiện độ bất định p99 e2e; N micro không bảo đảm chất lượng ước lượng đuôi latency LLM.
W10: FIX — Cách ghi lệch nhiệm vụ và giới hạn tiếng Việt phù hợp, nhưng output thiếu p95 theo protocol chung và lựa chọn “hoặc ASR” có thể bỏ FPR mà W12 yêu cầu.
W11: PASS — Spike có quyết định go/no-go, owner phù hợp, blocker dependency và cách xử lý no-go rõ ràng.
W12: PASS — Có bảng tổng hợp, owner Argon phù hợp, ngưỡng đề xuất chờ An duyệt và cổng cấm tune/chạy lại cùng holdout sau FAIL.
DONE: PASS — Đủ các đầu ra đánh giá bắt buộc, cho phép công bố FAIL trung thực và giữ ngoại lệ UNKNOWN rõ ràng cho Judge ON.
LICENSE: FIX — [Xung đột metadata deepset](https://huggingface.co/datasets/deepset/prompt-injections/raw/main/README.md) được phản ánh đúng, nhưng ngoại lệ An duyệt sử dụng ở mục 2 chưa thống nhất với gate loại khỏi bảng chính đến khi làm rõ tại W4/W12.
TIME: PASS — Giữ riêng bốn ước lượng và độ tin cậy, công khai bất đồng và không chọn một lịch làm sự thật.
NEW: NONE
