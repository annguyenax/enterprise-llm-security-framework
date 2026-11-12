VERDICT: PASS  
AUTHORSHIP: Claude viết phần lớn v2; v3 và v4 chỉ có sửa tối thiểu do điều phối; review này tự chấm toàn bộ v4, không nương nhẹ phần kế thừa hay dựa reviewer khác.  
W1: PASS — Dev per-case được phép trên box, val vẫn aggregate-only, holdout P2/P3 chỉ ở máy An; nguồn và trách nhiệm khôi phục rõ.  
W13: PASS — Yêu cầu manifest dẫn xuất dev+val có hash, runner không đọc/đòi holdout, có test chấp nhận/từ chối và owner Codex.  
W2: PASS — Chẩn đoán chỉ trên dev, có tử/mẫu số, val aggregate-only kể cả trên box và không dùng holdout.  
W3: PASS — Tune chỉ dev, val tối đa 3 lần tổng cộng, thất bại lần 3 phải dừng báo An; freeze và go/no-go rõ.  
W4: PASS — Đủ ledger và dữ liệu đầu ra, Muse phụ trách license/data, An tự chấp nhận gate; blocker và phụ thuộc rõ.  
W5: PASS — Bỏ dấu tiếng Việt trước exact/5-gram, gần trùng bắt buộc DROP khóa trước freeze, log chỉ hash; one-shot và ngoại lệ hạ tầng được giới hạn.  
W6: PASS — Giữ giới hạn chỉ bề mặt query, outcome đăng ký trước, mẫu số ASR rõ và lỗi/timeout báo riêng.  
W7: PASS — Index độc tách biệt có rollback, query freeze và ba chỉ số retrieval rõ, không tính không-retrieve thành phòng vệ thành công.  
W8: PASS — Judge-on-RAG và overhead còn UNKNOWN, mặc định OFF, phải freeze hook trước W5 nếu triển khai; owner và blocker phù hợp.  
W9: PASS — Đủ per-stage/e2e, N riêng từng nhóm, phân biệt cold/warm và p99 tham khảo; ngưỡng, cỡ mẫu đều chờ An duyệt.  
W10: PASS — Bắt buộc FPR/p95, tune baseline chỉ trên dev, giữ hạn chế tiếng Việt và yêu cầu freeze/one-shot khi vào bảng official.  
W11: PASS — NeMo official phải freeze config/scorer trước W5 và tuân luật one-shot; thiếu điều kiện chỉ được exploratory.  
W12: PASS — Giữ nguyên cổng official, đủ chỉ số so sánh, owner đúng vai và có STOP khi lộ holdout, tắt context hoặc chưa được go.  
DONE: PASS — Đủ đầu ra bắt buộc, mục 2 công bố số lần thử val với trần 3, giữ Judge UNKNOWN khi chưa hoàn tất và yêu cầu An duyệt ngưỡng.  
LICENSE: PASS — Phản ánh đúng các kết luận đã kiểm, đặc biệt xung đột [deepset](https://huggingface.co/datasets/deepset/prompt-injections/raw/main/README.md) và license nguồn riêng của [BIPIA](https://raw.githubusercontent.com/microsoft/BIPIA/main/LICENSE), đồng thời giữ gate do An chấp nhận.  
TIME: PASS — Giữ cả bốn ước lượng cùng mức bất định, không chọn một số làm sự thật và chưa chốt lịch.  
REGRESSION: NONE  
NEW: NONE

---
model: gpt-6.1-sol (OpenAI Codex v0.163.0)
usage: total=76428 (tokrun, real)
elapsed: 266.2s
ts: 2026-11-12T00:48:40+07:00 (Asia/Saigon)
label: p3-plan-v4-codex
