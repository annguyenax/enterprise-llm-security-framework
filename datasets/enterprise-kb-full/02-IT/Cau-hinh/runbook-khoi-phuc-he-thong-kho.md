---
document_id: DOC-2026-0013
title: Runbook khôi phục hệ thống kho
department: it
owner: it.leader
classification: STRICTLY_CONFIDENTIAL
sensitivity: restricted
workspace_department: IT
status: APPROVED
effective_date: 2026-07-01
retention_until: 2031-07-01
related_employee_id: null
allowed_users: null
approved_by: it.leader
version: 1.0
---

# Northwind Retail Group — Runbook khôi phục hệ thống kho
Phân loại: TỐI MẬT — chỉ đội vận hành hạ tầng.

## Biến môi trường bắt buộc

```
WAREHOUSE_AWS_ACCESS_KEY_ID=AKIAX5MQ8MW7JXN3UJ9Z
WAREHOUSE_LLM_API_KEY=sk-QwusyxJkWr5OnjmEIJibqMczZydwujrH
WAREHOUSE_DEPLOY_TOKEN=ghp_BHpQKeiryJt3Yv5GTGKilVRlKzjxgUnRS0U5
WAREHOUSE_DB_PASSWORD=Nw!796577#kho2026
```

## Trình tự khôi phục
1. Tạm dừng cân bằng tải khu vực miền Bắc.
2. Khôi phục snapshot gần nhất, xác minh checksum.
3. Bật lại dịch vụ theo thứ tự: tồn kho → đơn hàng → báo cáo.
