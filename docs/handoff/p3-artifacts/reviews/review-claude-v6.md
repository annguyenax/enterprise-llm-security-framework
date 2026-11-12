VERDICT: PASS
AUTHORSHIP: Claude viết v2; v3–v6 có sửa điều phối. Claude review toàn bộ v6 và tự chấm, không dựa vào reviewer khác và không nương nhẹ phần mình đã viết. Đã kiểm sha256 của file khớp 45b55302…2c0e. Đã đọc diff v5→v6: chỉ đổi ở mục đầu, W2, W3, W5 (MinHash), W10, W12 (cột), mục 5, mục 6 và mục 7.
W1: PASS — Dev+val được lên box sau khi kiểm manifest; holdout P2/P3 chỉ ở máy An, box chỉ nhận aggregate; Pass kiểm theo path/split mà không mở nhãn holdout; owner Muse/An đúng; blocker là thiếu `datasets/v2`.
W13: PASS — Có manifest dẫn xuất chỉ gồm dev+val, hash riêng. Runner không đọc và không đòi artifact holdout. Có test từ chối khi lẫn path holdout. Codex làm code, Claude review, Muse kiểm manifest; phụ thuộc W1 đúng.
W2: PASS — Per-case chỉ trên dev. Val W2 là aggregate-only, tính vào trần 3 lần chạy của Shield và không có pass/fail. RATE_REPORTING_MIN_N=10 có nhãn chờ An duyệt. Lưu ý không chặn: nếu W2 dùng hết 3 lần val thì W3 không còn lượt xác nhận và phải dừng chờ An. Hành vi này đúng luật nhưng nên nói rõ để đội biết mà dành lượt.
W3: PASS — Đóng đủ P3V5-NEW-01: trần đếm số lần chạy, không đếm thất bại; tối đa 3 lần cho mỗi hệ; trần Shield gồm cả val W2; lần xác nhận W3 dùng ngưỡng W3; dừng sau lần chạy thứ 3 bất kể kết quả; tất cả có nhãn "đề xuất, chờ An duyệt". Artifact freeze đủ. Không hạ W12 cho khớp W3.
W4: PASS — Ledger có SPDX, URL, ngày kiểm và dòng Semantic Judge. deepset bị loại khỏi bảng chính thức. Chỉ An chấp nhận tập gated; Muse soạn, Argon rà.
W5: PASS — MinHash được ghi đúng là ước lượng Jaccard và ngưỡng ≥0.80 áp trên ước lượng đó. DROP chỉ áp lên ứng viên P3-holdout, có ánh xạ đ/Đ→d, log chỉ ghi hash, luật failed attempt giữ nguyên. Gợi ý không chặn: nên ghi num_perm/seed của MinHash vào artifact freeze.
W6: PASS — ASR theo tập outcome bảo vệ đăng ký trước; mẫu số là probe hoàn tất; timeout/lỗi báo riêng. Giữ nguyên giới hạn "chỉ bề mặt query"; offline, venv riêng.
W7: PASS — Index độc tách riêng có rollback, query được freeze. Định nghĩa rõ retrieve-hit, context-to-provider và attack success chỉ trên case đã retrieve-hit. BIPIA tuân CC-BY-SA-4.0.
W8: PASS — Overhead Judge-on-RAG vẫn giữ UNKNOWN; digest UNKNOWN đến khi freeze. Mặc định Judge OFF ở cổng official; nếu làm W8 thì phải vào bundle trước one-shot.
W9: PASS — Đo trên máy An với env cố định, N riêng từng nhóm. Không cộng percentile từng tầng. p99 e2e với N nhỏ chỉ là tham khảo. Ngưỡng <3.0s và N có nhãn chờ An duyệt.
W10: PASS — Mỗi baseline có trần riêng 3 lần chạy val, không pass/fail, dừng sau lần 3 bất kể kết quả. Bắt buộc có FPR và p95 theo W9. Ngưỡng PG2 chốt trước. Ghi rõ PG2/LG3 không hỗ trợ tiếng Việt chính thức.
W11: PASS — Spike độc lập. Hàng NeMo official chỉ khi config/scorer đã freeze trước W5 và theo luật one-shot; nếu thiếu thì chỉ là hàng exploratory. Trần val NeMo được quy tắc xuyên suốt bao phủ.
W12: PASS — Đã có cột số lần thử val của từng hệ, có nhãn chờ An duyệt. Cổng official và các cổng dừng giữ nguyên. Lưu ý chữ không chặn: cột ghi "số lần thử" còn chỗ khác ghi "số lần chạy" (nên thống nhất một từ). W12 không có dòng Blocker riêng, nhưng mục "Cổng dừng" đã đóng vai trò đó; điểm này có từ trước, không phải hồi quy.
DONE: PASS — Mục 5 phản ánh đúng trần đếm số lần chạy, val W2 không có pass/fail, lần W3 dùng ngưỡng W3, dừng sau lần 3, MinHash là ước lượng Jaccard; vẫn yêu cầu mọi ngưỡng được An duyệt và số thật hoặc UNKNOWN.
LICENSE: PASS — Mục 2 không đổi so với v5 và phản ánh đúng các license đã kiểm: deepset xung đột nên bị loại; HackAPrompt MIT, gated; PG2 Llama 4; LG3 1B Llama 3.2, không có tiếng Việt; Qwen3-4B apache-2.0 với digest UNKNOWN.
TIME: PASS — Giữ bốn ước lượng không khớp nhau, không chọn số nào làm sự thật; lịch là đề xuất chờ An duyệt.
REGRESSION: NONE
NEW: NONE

---
requested_model: claude-opus-5-5 (via claude-chain)
tokrun_envelope_served_by: claude-opus-5-5
claude-chain_stderr: "served by: claude-sonnet-5-5 (fallback from claude-opus-5-5)" — disagrees with the envelope; tokens below are from the tokrun envelope for claude-opus-5-5
usage: input=4, output=4311, cache_read=52370, cache_create=37067, cost_usd_reported=0.393246, turns=2
elapsed: 43.5s
ts: 2026-11-12T00:54:17+07:00 (Asia/Saigon)
label: p3-plan-v6-claude
