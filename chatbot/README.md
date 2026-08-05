# Shield AI Chatbot

Giao diện chatbot web kết nối với **LLM Security Gateway** trong workspace.
Hỗ trợ tài khoản local, hội thoại SQLite, Markdown/code, phản hồi, dừng hiển
thị, kho TXT/Markdown được quét và bảng audit cho quản trị viên.

## Chạy ứng dụng

Mở hai terminal từ thư mục `E:\TTTN`:

```powershell
cd enterprise-llm-security-framework
powershell -ExecutionPolicy Bypass -File scripts/run_ollama.ps1
```

```powershell
cd chatbot
python server.py
```

Sau đó mở http://127.0.0.1:5500.

Database mẫu có các role `superadmin`, `leader`, `member` cho hai phòng IT/HR.
Xem tài khoản demo và ma trận quyền trong
`..\enterprise-llm-security-framework\docs\rbac-workspace.md`. Chỉ sử dụng dữ
liệu tổng hợp cho bản PoC.

`server.py` phục vụ giao diện và chuyển tiếp `/api/chat` tới
`http://127.0.0.1:8000/v1/gateway/chat`, nhờ đó không cần cấu hình CORS.
