VERDICT: FIX — không chặn. Plan dùng để làm việc được. Còn một chỗ mơ hồ về cách đếm trần val, cần sửa ở vòng sau.
AUTHORSHIP: Claude viết v2; v3–v5 có sửa điều phối. Claude tự review toàn bộ v5 và không dựa vào reviewer khác. sha256 của file khớp f6b34e0a…696f. Đã đọc đủ 438 dòng và diff với v4.
W1: PASS — dev+val được lên box sau khi kiểm manifest; holdout P2 và P3 ở lại máy An; box chỉ nhận aggregate; có blocker (thiếu nguồn chính thức) và owner Muse/An đúng vai.
W13: PASS — manifest chỉ gồm dev+val, có hash riêng; chế độ runner không đọc hay đòi artifact holdout; có test fail khi lẫn holdout; cấm lấy từ `p2-output`; owner Codex code, Claude review, Muse kiểm dữ liệu.
W2: PASS — per-case chỉ trên dev; val aggregate-only; val Shield ở W2 tính vào trần của Shield; câu "Codex đo trên runner tại máy An" đã bỏ, thay bằng "runner W13 trên box hoặc máy An khi cần GPU". Còn mơ hồ ở P3V5-NEW-01 (W2 không định nghĩa val "đạt/không đạt").
W3: FIX — ngưỡng có nhãn đề xuất và có cổng go/no-go. Nhưng câu "trần 3 lần, gồm mọi lần val" (đếm số lần chạy) mâu thuẫn với "dừng sau lần thất bại thứ 3" (đếm số lần thất bại): nếu lần val ở W2 không có tiêu chí đạt/không đạt, câu chữ hiện tại cho phép Shield chạy val lần thứ 4. Lỗi này có từ v4 nhưng rõ hơn ở v5 vì W2 nay tính vào trần.
W4: PASS — ledger có SPDX/URL/ngày kiểm và dòng Qwen3-4B; deepset bị loại; An tự chấp nhận các tập gated, Muse chỉ soạn; owner đúng.
W5: PASS — DROP chỉ áp lên ứng viên P3-holdout; dev/val/seed đã đóng băng không bị viết lại, xóa hay thay; ánh xạ đ/Đ → d ghi tường minh, kèm lý do NFD không xử lý được chữ này; một chuẩn hóa dùng cho cả SHA-256 và 5-gram; log chỉ ghi hash; Jaccard 0.80 có nhãn đề xuất; có luật failed attempt. Lưu ý nhỏ: MinHash chỉ ước lượng Jaccard, nên cần ghi rõ DROP dựa trên Jaccard ước lượng hay tính lại chính xác.
W6: PASS — giữ giới hạn "chỉ bề mặt query"; tập outcome bảo vệ đăng ký trước; mẫu số ASR rõ; timeout/lỗi báo riêng; chạy offline.
W7: PASS — index độc tách riêng, có rollback; query freeze có hash; có đủ retrieve-hit, context-to-provider và attack success trên các case đã retrieve-hit; ghi nguồn và share-alike CC-BY-SA.
W8: PASS — overhead Judge-on-RAG vẫn để UNKNOWN; repo mặc định OFF; nếu làm W8 thì phải vào bundle trước one-shot; cổng official mặc định Judge OFF.
W9: PASS — báo N riêng từng nhóm; không cộng percentile các tầng; không ghi 0 cho tầng bỏ qua; p99 với N nhỏ gắn nhãn tham khảo; N=200 hay N=100 để An chọn; ngưỡng 3.0s có nhãn đề xuất.
W10: FIX — mỗi baseline có trần riêng 3 lần là đúng, FPR và p95 là bắt buộc, có ghi hạn chế tiếng Việt. Nhưng plan không định nghĩa thế nào là một lần val baseline "không đạt" (baseline không có ngưỡng pass), nên luật dừng sau lần thất bại thứ 3 không áp dụng được (P3V5-NEW-01).
W11: PASS — hàng NeMo official cần go, cùng tập so sánh, freeze trước W5 và cùng luật one-shot; thiếu điều kiện nào thì chỉ là hàng exploratory.
W12: PASS — cổng AOMR ≥ 0.80 có nhãn đề xuất, không hạ cho khớp W3; FAIL vẫn công bố; có các điều kiện STOP. Nên thêm cột hoặc chú thích số lần thử val của từng hệ để khớp DONE mục 2. Đây là việc nhỏ, chưa thành FIX.
DONE: PASS — mục 2 đã cập nhật số lần thử theo từng hệ, trần Shield gồm W2, và DROP chỉ trên ứng viên P3-holdout có ánh xạ đ/Đ → d; Judge ON để UNKNOWN nếu W8 chưa xong; mọi ngưỡng chờ An duyệt.
LICENSE: PASS — bảng license phản ánh đúng các kết luận đã kiểm: xung đột deepset được giữ, HackAPrompt MIT/gated với README trả 401, PG2 Llama 4 và LG3 không có tiếng Việt, Qwen3-4B apache-2.0 với digest UNKNOWN. Vòng này không kiểm lại online.
TIME: PASS — giữ cả bốn ước lượng kèm độ tin cậy, nêu rõ chúng lệch nhau, không chọn số nào làm sự thật, lịch để An duyệt.
REGRESSION: NONE — mọi dòng bị xóa so với v4 đều được thay bằng nội dung tương đương hoặc chặt hơn. Câu Claude-W1 kiểu cũ ("box chỉ nhận aggregate và manifest hash") và câu owner W2 kiểu cũ đã được bỏ.
NEW: P3V5-NEW-01 — Cần định nghĩa thống nhất cho trần val: trần đếm mọi lần chạy val của một hệ, bất kể đạt hay không, và dừng ngay ở lần chạy thứ 3 (không phải lần thất bại thứ 3). Đồng thời cần nêu tiêu chí đạt/không đạt cho val ở W2 (chẩn đoán) và val của baseline ở W10, hoặc nói rõ các lần đó chỉ tính vào số lần chạy, không có pass/fail. Mức FIX, áp cho mục đầu, W2, W3, W10 và mục 5.

---
requested_model: claude-opus-5-5 (via claude-chain)
tokrun_envelope_served_by: claude-opus-5-5
claude-chain_stderr: "served by: claude-sonnet-5-5 (fallback from claude-opus-5-5)" — disagrees with the envelope; tokens below are from the tokrun envelope for claude-opus-5-5
usage: input=6, output=4958, cache_read=94364, cache_create=36427, cost_usd_reported=0.4094728, turns=3
elapsed: 48.5s
ts: 2026-11-12T00:50:58+07:00 (Asia/Saigon)
label: p3-plan-v5-claude
