# Nhiệm vụ dành cho Claude Code (Tối ưu Kiến trúc & UI/UX)

**Mục tiêu:** Cải tiến UI/UX Chatbot và tối ưu mã nguồn.

**Lệnh bắt buộc:**
Trước khi làm gì, bạn phải đọc 3 file sau để không làm hỏng kiến trúc hiện tại: 
1. `CLAUDE.md`
2. `docs/ai-collaboration/00_PROJECT_STATE.md`
3. `TASK_BOARD.md`

**Nhiệm vụ cụ thể:**
1. Thiết kế lại UI/UX cho frontend (`chatbot/`) theo hướng hiện đại (glassmorphism, thêm animations mượt mà).
2. Hiển thị Semantic Rank Score trên tin nhắn của chatbot.
3. Thêm tính năng/nút "Appeal" (Kháng cáo) cho các tin nhắn bị hệ thống block.
4. Đọc file `walkthrough.md` để nắm các thay đổi gần đây nhất và tiếp tục triển khai.
5. Tuyệt đối tuân thủ `AGENT_RULES.md` (không tự ý gọi API ngoài, chỉ dùng mock/local provider).

---

# Nhiệm vụ dành cho Grok CLI (Chuyên Red Teaming & Security)

**Mục tiêu:** Nâng cấp kịch bản Red Team và khả năng phòng vệ của Gateway.

**Lệnh bắt buộc:** 
Bạn phải phân tích kỹ file `scripts/run_redteam_ollama.py` và kiến trúc luồng dữ liệu trong `app/services/gateway.py` trước khi thực hiện.

**Nhiệm vụ cụ thể:**
1. Xây dựng thêm ít nhất 20 kịch bản tấn công (Jailbreak, Prompt Injection, Data Exfiltration, Roleplay) bằng tiếng Việt siêu lắt léo vào script Red Team (`run_redteam_ollama.py`).
2. Tối ưu hàm `evaluate_input_semantic` trong `app/guards/semantic_guard.py` để nhận diện chính xác các câu hack này mà không làm tăng đáng kể độ trễ (latency).
3. Cải tiến script Red Team để sinh ra báo cáo tự động (Markdown format) sau mỗi lần chạy, giúp so sánh điểm số bảo mật dễ dàng.
