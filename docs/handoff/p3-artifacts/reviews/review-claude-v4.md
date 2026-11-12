VERDICT: FIX
AUTHORSHIP: Claude viết v2; v3 và v4 có sửa điều phối. Claude tự chấm toàn bộ v4, không dựa vào reviewer khác. Hash file khớp `1c9f2ee9…cef18bc`. Đã diff v3→v4 trên file. Không đọc lại được code repo vì lệnh bị từ chối, nên các path kỹ thuật dựa trên đối chiếu của Codex/Muse mà plan ghi.
W1: PASS — Dev+val được lên box sau khi kiểm manifest, per-case chỉ trên dev, val trên box chỉ aggregate; holdout P2/P3 chỉ ở máy An và box chỉ nhận số aggregate, kiểm theo path/split; điểm (1) đã đóng.
W13: PASS — Có manifest dẫn xuất dev+val với hash riêng và chế độ runner không đọc/không đòi artifact holdout P2 (thiếu holdout không phải lỗi). Có test xanh trên fixture và test từ chối khi lẫn holdout, owner Codex, Claude review, cấm lấy từ `p2-output`; điểm (3) đã đóng.
W2: PASS — Per-case chỉ trên dev, được chạy trên box; val aggregate-only kể cả trên box; RATE_REPORTING_MIN_N có nhãn đề xuất. Lỗi nhỏ: dòng owner "Codex đo trên runner tại máy An" đã cũ so với v4, nên sửa câu chữ, không chặn.
W3: PASS — Trần 3 lần thử val (đề xuất, chờ An duyệt), thất bại lần 3 thì dừng và báo An, không chỉnh rule từ val, có artifact freeze đủ mục, giữ cổng go/no-go và không hạ W12; điểm (2) đã đóng. Phạm vi bộ đếm xem P3V4-NEW-02.
W4: PASS — Ledger có SPDX/URL/ngày kiểm, có dòng Semantic Judge, loại deepset; Muse soạn, An tự chấp nhận gate, Argon rà.
W5: FIX — Điểm (4) đã đóng: DROP exact và gần trùng (Jaccard ≥ 0.80, đề xuất), khóa trước freeze, log chỉ hash, bỏ dấu trước SHA và 5-gram. Còn hai lỗ: (a) không nói DROP phía nào. Phải chỉ loại ứng viên P3-holdout; dev/val đã dùng để xác nhận W3 không được đổi sau freeze, nếu không số val mất giá trị. (b) "bỏ dấu" cần ghi rõ ánh xạ đ/Đ→d, vì tách NFD rồi bỏ dấu kết hợp không xử lý được ký tự này.
W6: PASS — Giữ giới hạn "chỉ bề mặt query"; ASR theo tập outcome bảo vệ đăng ký trước; timeout/lỗi báo riêng; thêm package phải được An duyệt.
W7: PASS — Index độc riêng có rollback, query freeze có hash; attack success chỉ tính trên case retrieve-hit; giữ CC-BY-SA của BIPIA và blocker routes.
W8: PASS — Overhead Judge ON trên RAG vẫn UNKNOWN, mặc định OFF, digest để đến freeze, phải vào bundle trước one-shot nếu làm.
W9: PASS — N tách theo nhóm; p99 với N nhỏ chỉ là tham khảo; hai đề xuất N để An chọn; < 3.0s có nhãn đề xuất; không trích latency P2.
W10: FIX — Bắt buộc FPR và p95 theo W9, chỉnh ngưỡng chỉ trên dev, có ghi hạn chế tiếng Việt. Nhưng chưa rõ lần chạy val của baseline có tính vào "3 lần thử tổng cộng" của Shield hay có bộ đếm riêng, và DONE mục 2 chỉ đếm cho W3 (P3V4-NEW-02).
W11: PASS — Hàng official yêu cầu đã go, cùng tập với W10, freeze config/scorer trước W5 và cùng luật one-shot/attempt; thiếu thì chỉ exploratory, có ghi trong mục 6; điểm (5) đã đóng.
W12: PASS — Cổng official có nhãn đề xuất, không hạ cho khớp W3, FAIL vẫn công bố; có STOP khi artifact holdout P2/P3 lên box; hàng NeMo exploratory tách rõ.
DONE: PASS — Mục 2 có số lần thử val (trần 3), khử trùng DROP chỉ log hash, one-shot trên máy An; latency, so sánh và UNKNOWN đều được giữ.
LICENSE: PASS — Mục 2 phản ánh đúng các license đã kiểm: deepset xung đột nên loại, HackAPrompt MIT gated, PG2 Llama 4, LG3 1B không có tiếng Việt, Qwen3-4B apache-2.0 với digest UNKNOWN.
TIME: PASS — Giữ cả bốn ước lượng lệch nhau, không chọn số nào, lịch có nhãn đề xuất. Nên ghi thêm rằng W13 và các bước v4 cũng có sau các ước lượng này.
REGRESSION: NONE về nội dung. Có một điểm không nhất quán ở traceability: dòng Claude-W1 ở mục 7 vẫn ghi "W1 chuyển sang cây riêng trên máy An; box chỉ nhận aggregate và manifest hash", mâu thuẫn với v4 (dev+val được lên box). Dòng Muse-W1 thì đã cập nhật.
NEW: P3V4-NEW-01 (FIX, W5): ghi rõ DROP chỉ áp lên ứng viên P3-holdout, không đổi dev/val/seed đã dùng; chuẩn hóa ghi rõ đ→d. P3V4-NEW-02 (FIX, quy tắc xuyên suốt/W2/W10/DONE): định nghĩa phạm vi bộ đếm 3 lần val, gồm lần val ở W2 và lần val baseline ở W10 có tính vào trần của Shield hay không, và công bố số lần thử cho từng hệ. P3V4-NEW-03 (FIX, mục 7): cập nhật dòng Claude-W1 cho khớp v4.

---
requested_model: claude-opus-5-5 (via claude-chain)
tokrun_envelope_served_by: claude-opus-5-5
claude-chain_stderr: "served by: claude-sonnet-5-5 (fallback from claude-opus-5-5)" — disagrees with the envelope; tokens below are from the tokrun envelope for claude-opus-5-5
usage: input=10, output=6252, cache_read=190596, cache_create=41717, cost_usd_reported=0.4969352, turns=5
elapsed: 62.6s
ts: 2026-11-12T00:45:15+07:00 (Asia/Saigon)
label: p3-plan-v4-claude
