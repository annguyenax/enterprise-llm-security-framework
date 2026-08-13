# Kho tri thức doanh nghiệp

Kho mẫu phục vụ demo truy hồi có RBAC. Tài liệu được chia theo vùng nghiệp vụ,
nhưng quyền thực tế vẫn lấy từ metadata của từng file và được thực thi khi seed
vào workspace.

## Cấu trúc

- `00-Dung-chung`: nội quy, hướng dẫn và biểu mẫu dùng toàn công ty.
- `01-Ke-toan`: chứng từ, hóa đơn, tài chính, thuế, ngân sách, công nợ và thanh toán lương.
- `02-IT`: hướng dẫn, kiến trúc, mã nguồn, cấu hình và nhật ký kỹ thuật.
- `03-Nhan-su`: hồ sơ, hợp đồng, tuyển dụng, chấm công, đánh giá và lương.
- `04-Quan-tri`: chính sách quyền, nhật ký truy cập, sao lưu và kiểm toán.
- `05-Luu-tru`: tài liệu hết hiệu lực nhưng còn thời hạn lưu giữ.
- `Mau-bieu`: mẫu metadata và yêu cầu cấp quyền.

## Mức bảo mật

| `sensitivity` | Phân loại | Quyền mặc định khi seed |
|---|---|---|
| `public` | Công khai nội bộ | Toàn workspace |
| `internal` | Nội bộ phòng ban | Member cùng phòng trở lên |
| `confidential` | Mật | Leader cùng phòng trở lên |
| `restricted` | Tối mật | Leader cùng phòng; hồ sơ cá nhân dùng grant đích danh |

Phiếu lương và hợp đồng cá nhân phải có `related_employee_id` và
`allowed_users`. Không đặt mật khẩu, API key hoặc khóa production trong tài
liệu thông thường; các giá trị giống bí mật trong kho này đều là dữ liệu tổng
hợp phục vụ kiểm thử DLP.

Kho mẫu có đủ hồ sơ cá nhân cho tám tài khoản nghiệp vụ của IT, Nhân sự và Kế
toán. Mỗi tài khoản có một hợp đồng và một phiếu lương; tài khoản hệ thống
`superadmin` không được xem là nhân viên nên không có hồ sơ lao động riêng.

Sinh lại kho bằng `python scripts/build_enterprise_knowledge_base.py`; kiểm tra
tính xác định bằng tùy chọn `--check`.
