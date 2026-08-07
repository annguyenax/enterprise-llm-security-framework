# Bộ tài liệu nghiệp vụ mẫu

`scripts/seed_business_documents.py` tạo 27 tài liệu hoàn toàn giả lập để thử
nghiệm truy xuất và phân quyền của workspace proof-of-concept. Bộ dữ liệu gồm
chính sách lương, mẫu/hồ sơ hợp đồng lao động, phiếu lương, báo cáo ngân sách và
hợp đồng với đối tác giả lập.

Mỗi tài khoản demo (`superadmin`, hai leader và bốn member) có một hợp đồng lao
động cùng một phiếu lương cá nhân. Câu hỏi sở hữu như "lương của tôi" được định
tuyến thẳng tới phiếu lương `scope=user` do chính tài khoản đang hỏi sở hữu.

Metadata phân quyền được lưu ở bảng `documents`: `scope`, `audience_role`,
`department`, `owner_user_id`, `mime_type` và `guard_decision`. Nội dung Markdown
cũng có YAML front matter mô tả `document_type`, `classification` và
`synthetic_data: true` để dễ quan sát khi truy xuất.

Chạy từ thư mục gốc repository:

```powershell
.\.venv\Scripts\python.exe scripts\seed_business_documents.py
```

Script kiểm tra từng tài liệu bằng Upload Scanner và RAG Guard trước khi lưu,
đồng thời bỏ qua tên file đã tồn tại nên có thể chạy lại an toàn.

Ma trận chính:

| Scope | Audience | Ví dụ | Người được đọc |
|---|---|---|---|
| global | member | Chính sách lương | Mọi tài khoản |
| global | leader | Báo cáo chi phí nhân sự | Leader và SuperAdmin |
| global | superadmin | Hợp đồng đối tác | Chỉ SuperAdmin |
| department | member | Chính sách phụ cấp IT | Thành viên cùng phòng trở lên |
| department | leader | Ngân sách/hợp đồng phòng | Leader cùng phòng và SuperAdmin |
| user | member | Hợp đồng, phiếu lương cá nhân | Chính chủ và SuperAdmin |

Giới hạn hiện tại: tài liệu `user` chỉ cho chính chủ và SuperAdmin. Mô hình ACL
có thể cấp thêm quyền trực tiếp bằng `allowed_users` hoặc theo nhóm với
`allowed_groups`, ví dụ `HR:leader`. Quyền mở rộng được lưu trong
`document_user_grants` và `document_group_grants`; kết quả retrieval luôn được
lọc lại bằng các bảng này trước khi nội dung đi vào LLM.
