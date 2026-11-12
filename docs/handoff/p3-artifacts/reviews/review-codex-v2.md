VERDICT: FIX  
SWAP: Claude là tác giả v2, không review; Codex stand-in cho issue của Claude.

Codex-W5: FIX — Đã bao phủ các tập và freeze lại khi có W8, nhưng hash văn bản chuẩn hóa chưa đủ phát hiện gần trùng; cần phương pháp và tiêu chí gần trùng cụ thể.  
Codex-W6: PASS — W6 đã định nghĩa thành công theo outcome bảo vệ đăng ký trước, scorer, mẫu số và cách báo lỗi riêng.  
Codex-W7: PASS — Đã tách retrieve-hit trước guard với context-to-provider sau guard, giữ mẫu số attack success trên các case retrieve-hit.  
Codex-W9: PASS — Đã yêu cầu N riêng từng nhóm và gắn nhãn tham khảo cho p99 e2e LLM ở N=100–200.  
Codex-W10: FIX — FPR đã bắt buộc, nhưng W10 vẫn chưa yêu cầu đo p95 baseline theo protocol W9; cột p95 ở W12 không đóng thiếu sót này.  
Codex-LICENSE: PASS — Đã bỏ ngoại lệ An duyệt dùng deepset khi xung đột license chưa được làm rõ.

Claude-W1: PASS — Đã xác định W2/W3 chạy trên máy An, kiểm working set theo manifest và cấm tuyệt đối đưa artifact holdout P2 lên box.  
Claude-W3: FIX — Freeze và khoảng lệch AOMR đã được xử lý, nhưng W2 vẫn chẩn đoán val trước khi W3 sửa rule nên chưa bảo đảm xác nhận độc lập.  
Claude-W5: PASS — Đã bổ sung đối chiếu hash giữa các tập, luật failed attempt với tối đa một lần chạy lại không đổi bundle và mặc định official Judge OFF.  
Claude-W6: PASS — ASR đã có định nghĩa và scorer riêng, block-rate không thay thế ASR, payload phải chuẩn bị trước để chạy offline.  
Claude-W7: PASS — Đã có corpus/index riêng, kiểm rollback, nghĩa vụ CC-BY-SA và query freeze có hash trước khi đo.  
Claude-W8: PASS — Đã nêu model, license, digest phải cố định khi freeze và yêu cầu freeze lại bundle sau thay đổi W8 trước one-shot.  
Claude-W10: PASS — Đã khóa ngưỡng PG2 trước tập so sánh, ghi hạn chế tiếng Việt của cả hai baseline và cho phép P3 one-shot với config freeze.  
Claude-W12: PASS — Đã cho phép baseline chạy P3 theo luật W5 và giữ cổng AOMR ≥ 0.80 cùng quyết định go/no-go khi val chưa đạt.  
Claude-NEW-01: PASS — W1 đã xác định nơi chạy W1–W3/W9–W10, luồng aggregate về box và cam kết holdout P2 không rời máy An.  
Claude-NEW-02: FIX — Chưa có quy tắc xuyên W2/W3/W10 bảo vệ val: W2 dùng val để chẩn đoán trước sửa rule, còn W10 gọi đây là “bảng lặp” mà chưa cấm dùng phản hồi để điều chỉnh cấu hình.  
Claude-NEW-03: PASS — W5 đã yêu cầu đối chiếu hash giữa W4, dev/val và P3-holdout; hạn chế phát hiện gần trùng được giữ mở tại Codex-W5.  
Claude-NEW-04: PASS — Mục 2 đã có dòng Semantic Judge với tên, license và digest UNKNOWN phải được cố định lúc freeze.  
Claude-NEW-05: PASS — Đã ghi nhận đối chiếu path trên ff41f92; đây không phải lỗi plan cần mở lại.

REGRESSION: NONE  
NEW: NONE

Ghi chú: Mục 7 ánh xạ sai **Claude-NEW-03** sang luật sự cố hạ tầng; issue gốc là chống rò rỉ chéo bằng hash. Kết quả trên chấm theo nội dung W5, không theo dòng ánh xạ sai.

SHA-256 của file khớp giá trị được cung cấp.

---
model: gpt-6.1-sol (OpenAI Codex v0.163.0)
usage: total=46201 (tokrun, real)
elapsed: 234.5s
ts: 2026-11-12T00:32:11+07:00 (Asia/Saigon)
label: p3-plan-v2-codex
