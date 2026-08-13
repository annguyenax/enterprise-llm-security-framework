# Ma trận phân quyền tổng quát

Ký hiệu: `X` xem, `T` tạo/cập nhật, `D` duyệt, `Q` cấp quyền giới hạn, `K` không truy cập.

| Vai trò | Kho chung | Phòng mình | Phòng khác | Kho quản trị |
|---|---|---|---|---|
| Superadmin | X/T/D/Q | X/T/D/Q | X/T/D/Q | X/T/D/Q |
| Leader | X/T | X/T/D/Q | X khi được cấp đích danh | K |
| Member | X | X/T theo nhiệm vụ | K | K |

Leader chỉ cấp quyền trong phòng mình. Tài liệu lương, hợp đồng, hồ sơ cá nhân
không kế thừa quyền đọc của cả phòng; chúng dùng grant trên từng hồ sơ.

Lưu ý: code hiện vẫn cho `superadmin` đọc mọi tài liệu để phục vụ vận hành demo.
Chính sách “break-glass” cho dữ liệu tối mật là mục tiêu quản trị, chưa phải một
workflow phê duyệt riêng trong ứng dụng.
