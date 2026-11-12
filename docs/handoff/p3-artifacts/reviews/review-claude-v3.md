VERDICT: FIX. Không có mục nào bị BLOCK. Còn hai điểm FIX nhỏ (W2, W3), sửa ở vòng plan sau. W1 và W4 bắt đầu được ngay. Plan khớp sha256 `69840a0d…9329`. Tôi đã đọc toàn bộ v3 và diff với v2.
AUTHORSHIP: Claude viết phần lớn v2; v3 có sửa tối thiểu do điều phối (đóng Codex-W5, Codex-W10, Claude-W3, Claude-NEW-02 và sửa ánh xạ Claude-NEW-03). Claude tự review toàn bộ v3, không nương tay vì là tác giả v2.
W1: PASS — W1 có cây riêng trên máy An và kiểm manifest theo split. Box chỉ nhận aggregate và hash, và lệnh cấm tuyệt đối với artifact holdout P2 được nêu đủ; owner Muse/Codex/An đúng vai, blocker nêu rõ.
W2: FIX — W2 giao phân tích per-case trên dev cho Claude, nhưng cùng mục lại ghi "box chỉ nhận aggregate". Plan không nói per-case dev chạy ở đâu: qua gói dev+val đã kiểm manifest của W1 đưa lên box, hay An tự làm trên máy mình. Cần ghi rõ để không ai phải đoán hoặc vô tình đưa dữ liệu lên box (NEW-06).
W3: FIX — Quy tắc dev/val đã đóng Claude-W3 và NEW-02. Nhưng câu "val fail → về dev sửa → chạy val lại" không có giới hạn số lần, nên kết quả aggregate của val vẫn gián tiếp lái việc chỉnh rule. Điều này mâu thuẫn với "không dùng kết quả val để điều chỉnh". Đề xuất thêm trần số lần thử val (vd. ≤3, chờ An duyệt), và quy định khi vượt trần thì gắn nhãn val là "đã tiêu hao" (NEW-07). Các ngưỡng còn lại đã có nhãn, có cổng go/no-go và không hạ cổng W12.
W4: PASS — Ledger có SPDX/URL/ngày kiểm và dòng Semantic Judge, deepset bị loại khỏi bảng chính thức; An tự chấp nhận các gate, Muse chỉ soạn ledger.
W5: PASS — Codex-W5 đã đóng: exact SHA-256 cộng MinHash/Jaccard trên char 5-gram, ngưỡng ≥0.80 có nhãn chờ duyệt, chạy offline, báo riêng exact và gần trùng; luật failed attempt và freeze lại bundle vẫn còn. Lưu ý: chọn "loại hay gắn cờ" phải chốt trước khi chạy, và chuẩn hóa nên cân nhắc thêm bản bỏ dấu tiếng Việt.
W6: PASS — Phạm vi "chỉ bề mặt query" được giữ; ASR theo tập outcome bảo vệ đăng ký trước, mẫu số rõ, timeout/lỗi báo riêng, probe cần mạng thì bỏ.
W7: PASS — Index độc tách riêng có rollback, query freeze có hash, retrieve-hit và context-to-provider định nghĩa rõ, attack success chỉ tính trên case đã retrieve-hit; ghi nguồn CC-BY-SA cho phần BIPIA.
W8: PASS — Overhead Judge-on-RAG vẫn giữ UNKNOWN, mặc định OFF, digest để freeze sau. Nếu làm thì W8 phải vào bundle trước one-shot, và phải ghi rõ fail-closed hay fail-open.
W9: PASS — N ghi riêng từng nhóm, không cộng percentile từng tầng, p99 nhỏ gắn nhãn tham khảo, không trích latency P2; ngưỡng <3.0s có nhãn chờ duyệt và ghi rõ chưa có số đo.
W10: PASS — Codex-W10 đã đóng: bắt buộc FPR và p95 theo protocol W9, chỉ chỉnh trên dev, val chỉ xác nhận, ngưỡng PG2 chốt trước; hạn chế tiếng Việt và luật one-shot giống Shield vẫn được giữ.
W11: PASS — Spike độc lập, go/no-go bằng văn bản; hàng NeMo chỉ vào bảng official khi đã go và chạy cùng tập với W10.
W12: PASS — Cổng official có nhãn chờ duyệt, không hạ cho khớp W3, FAIL vẫn công bố; các cổng STOP (lộ P2, tắt context, deepset, OOM, AOMR val <0.80) đủ.
DONE: PASS — Bảy tiêu chí của mục 5 bám đúng W1–W12, giữ giới hạn garak/PyRIT, Judge ON để UNKNOWN nếu chưa xong, p95 baseline theo W9. Nên bổ sung "công bố số lần thử val" vào mục 2 của tiêu chí cho đồng bộ với W3.
LICENSE: PASS — Bảng license đã kiểm được phản ánh đúng (deepset xung đột và bị loại; HackAPrompt MIT gated; PG2 Llama 4; LG3 không hỗ trợ VI; BIPIA có phần CC-BY-SA; Qwen3-4B apache-2.0, digest UNKNOWN).
TIME: PASS — Bốn ước lượng lệch nhau được trình bày song song kèm độ tin cậy tự khai, không chọn số nào làm sự thật, và có ghi rằng chúng có trước các bước mới; lịch vẫn chờ An duyệt.
REGRESSION: NONE — diff v2→v3 chỉ là phần bổ sung (quy tắc dev/val, phương pháp gần trùng, p95 cho baseline, cột "Kỳ" ở mục 7); không xóa ràng buộc nào của v2.
NEW: NEW-06 (W2: không nói per-case dev chạy ở đâu so với "box chỉ nhận aggregate"); NEW-07 (W3: không giới hạn số lần thử val, nên val vẫn gián tiếp lái việc chỉnh rule)

---
requested_model: claude-opus-5-5 (via claude-chain)
tokrun_envelope_served_by: claude-opus-5-5
claude-chain_stderr: "served by: claude-sonnet-5-5 (fallback from claude-opus-5-5)" — disagrees with the envelope; tokens below are from the tokrun envelope for claude-opus-5-5
usage: input=6, output=4842, cache_read=102059, cache_create=16307, cost_usd_reported=0.2477318, turns=3
elapsed: 47.4s
ts: 2026-11-12T00:40:56+07:00 (Asia/Saigon)
label: p3-plan-v3-claude
note: first attempt at 00:35:59+07 failed (rc=1) because the prompt was only on stdin and claude-chain does not forward stdin; that attempt's token count is UNKNOWN (stderr was truncated after total_cost_usd=0.4389042). The figures above are from the successful rerun, which passed --output-format json before -- and the prompt as an argv argument.
