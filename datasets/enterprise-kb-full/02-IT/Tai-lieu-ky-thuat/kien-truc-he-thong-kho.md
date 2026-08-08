---
document_id: DOC-2026-0008
title: Kiến trúc hệ thống quản lý kho
department: it
owner: it.leader
classification: CONFIDENTIAL
sensitivity: confidential
workspace_department: IT
status: APPROVED
effective_date: 2026-07-01
retention_until: 2031-07-01
related_employee_id: null
approved_by: it.leader
version: 1.0
---

# Northwind Retail Group — Kiến trúc hệ thống quản lý kho
Phân loại: MẬT — phòng IT.

- Tầng ứng dụng: dịch vụ đơn hàng, tồn kho, báo cáo, sau cân bằng tải khu vực.
- Tầng dữ liệu: cơ sở dữ liệu chính + bản sao đọc; snapshot theo giờ.
- Tích hợp: cổng thanh toán, hệ thống kế toán qua hàng đợi tin cậy.
