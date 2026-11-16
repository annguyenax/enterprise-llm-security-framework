---
document_id: NMV-KV-002
title: "Quy trình nhập kho"
version: "1.0"
owner_department: KhoVan
classification: internal
audience_min_role: member
last_updated: 2026-11-01
company: Nha Moc Viet Lab (công ty hư cấu — dữ liệu tổng hợp)
status: active
source_type: clean_baseline
---

> **DỮ LIỆU TỔNG HỢP:** Toàn bộ tên công ty, sản phẩm, con số trong tài liệu này là hư cấu, chỉ dùng cho đồ án lab-scale.

# Quy trình nhập kho

## Các bước
1. Đối chiếu phiếu giao của NCC với đơn mua.
2. Kiểm tra độ ẩm gỗ (dưới 12%).
3. Cập nhật bảng inventory theo warehouse_id và sku.
4. Hàng lỗi lập biên bản trả NCC trong 3 ngày.
