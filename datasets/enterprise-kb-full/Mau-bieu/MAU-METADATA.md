# Mẫu metadata tài liệu

```yaml
---
document_id: DOC-2026-0001
title: Tên tài liệu
department: it
owner: it.leader
classification: CONFIDENTIAL
sensitivity: confidential
workspace_department: IT
status: APPROVED
effective_date: 2026-07-01
retention_until: 2031-07-01
related_employee_id: null
allowed_users: null
approved_by: it.leader
version: 1.0
---
```

Với phiếu lương hoặc hợp đồng cá nhân, điền tài khoản vào
`related_employee_id` và danh sách phân tách bằng dấu phẩy vào `allowed_users`.
Ví dụ: `allowed_users: it.user1,hr.leader,ketoan.leader`.
