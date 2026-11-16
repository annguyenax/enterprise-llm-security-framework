# datasets/furniture/ — Công ty nội thất giả lập (P4)

Bộ dữ liệu **100% tổng hợp** cho công ty hư cấu **Nha Moc Viet Lab** (bán đồ nội thất,
gia dụng; nhiều chi nhánh và kho). Dùng làm "sân" thử nghiệm cho:

- **RAG data poisoning:** tài liệu sạch và bản bị đầu độc ghép cặp (`docs/`).
- **SQL injection / P2SQL:** database SQLite mà SQL agent truy vấn (`sql/`), có cài sẵn
  payload tấn công gián tiếp trong `orders.note` và `product_reviews.content`.

Bộ này **đặt cạnh** dữ liệu cũ. Nó không thay thế và không đụng tới `datasets/v2/` (đã FINAL freeze).

## Cấu trúc

```
datasets/furniture/
├── sql/schema.sql      # schema do leader chốt (contract) — không đổi tên bảng/cột
├── sql/seed.sql        # SINH TỰ ĐỘNG bởi scripts/generate_furniture_seed.py — không sửa tay
├── docs/clean/         # 8 tài liệu sạch (bảo hành, đổi trả, giao hàng, bảng giá đại lý, ...)
├── docs/poisoned/      # 6 bản đầu độc, mỗi bản ghép với một tài liệu sạch (based_on_clean_doc)
└── manifest.json       # mọi tài liệu + mọi dòng tấn công/đối chứng, kèm attack_type
```

## Dựng database

```powershell
.venv\Scripts\python.exe scripts\generate_furniture_seed.py      # chỉ khi sửa generator
.venv\Scripts\python.exe scripts\build_furniture_db.py --out data/furniture.db --force
```

`data/` nằm trong `.gitignore`; database luôn được dựng lại từ `schema.sql` + `seed.sql`.

## An toàn dữ liệu

- Tên người, công ty, NCC đều hư cấu (họ "Lab/Mẫu/Thử/Giả/Demo"). Email `@example.test`,
  số điện thoại dạng `09xx-000-xxx`.
- Bảng `internal_secrets` chỉ chứa marker giả `FAKE-SECRET-000x-EXAMPLE`.
- Payload tấn công chỉ nhắm vào hệ thống lab của đồ án này (AGENT_RULES rule 7).
- `expected_guard_decision` trong manifest là **kỳ vọng thiết kế**, không phải số liệu đo được.
