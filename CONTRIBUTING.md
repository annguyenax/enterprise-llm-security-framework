# Hướng dẫn phối hợp (An × Nghĩa)

Tài liệu này quy định cách hai thành viên làm việc song song với **ít conflict nhất**.
Ràng buộc kỹ thuật chi tiết của các "khớp nối" (interface) xem
`docs/decisions/ADR-004-collaboration-interfaces.md`.

## 1. Chia vai & quyền sở hữu thư mục (thay cho CODEOWNERS)

> Ghi chú: dự án dùng **release allowlist đóng (schema 4)**. File `CODEOWNERS` (không có
> đuôi) sẽ bị phân loại `unclassified_tracked_path` và làm hỏng cổng release, nên bảng
> ownership được đặt tại đây (`.md` hợp lệ). Nếu muốn dùng tính năng CODEOWNERS của GitHub,
> phải thêm một luật `exact_path` vào `release/release-allowlist.json` trong một PR riêng
> có review.

| Miền | Chủ sở hữu | Thư mục / tệp |
|---|---|---|
| **Gateway & Guards** | **An** | `app/guards/**`, `app/core/**`, `app/api/**`, `app/services/{gateway.py,rag_query.py,audit_logger.py}`, `app/schemas/**`, `tests/` (phần guard/gateway), `scripts/*evaluation*`, `redteam/**` |
| **LLM providers** | **Nghĩa** | `app/services/providers/**` *(mới)* |
| **Kho tri thức & truy xuất** | **Nghĩa** | `app/retrieval/**` (impl mới), `app/services/ingestion.py`, `app/knowledge_base/**` *(mới)*, `datasets/enterprise-kb/**` *(mới)* |
| **Kiến trúc & triển khai DN** | **Nghĩa** | `docs/architecture/**` *(mới)*, `docker/**` |
| **Đóng băng — KHÔNG ai sửa** | — | `datasets/v2/**` (hash-locked), `release/**` (allowlist đã audit) |

## 2. Hai "khớp nối" bắt buộc tuân theo (freeze)

Nghĩa xây phần thật **sau hai interface đã có**, không sửa file dùng chung của An:

1. **LLM:** kế thừa `BaseLLMProvider` (`app/services/llm_provider.py`), implement
   `generate()`; **đăng ký** bằng `register_provider("<tên>", <factory>)` trong module của
   mình dưới `app/services/providers/`. **Không** sửa hàm `get_llm_provider`.
2. **Truy xuất/kho tri thức:** implement ABC `Retriever` (`app/retrieval/base.py`); đăng ký
   qua `register_retriever(...)` (`app/retrieval/registry.py`).

Muốn đổi chữ ký của hai interface ⇒ phải làm **PR riêng, bàn chung, review** — không đổi lén.

## 3. Nhánh & quy trình

- `main`: ổn định, **bảo vệ**; chỉ vào bằng PR + review chéo.
- Nhánh ngắn: An `feat/gw-*`; Nghĩa `feat/llm-*`, `feat/kb-*`.
- **Mỗi ngày** `git pull --rebase origin main` để conflict nhỏ, phát hiện sớm.
- PR nhỏ, merge sớm; xóa nhánh sau merge.

## 4. Điều kiện trước khi merge (bắt buộc)

1. `git pull --rebase origin main` và tự xử lý conflict trên nhánh mình (**không force lên main**).
2. Test xanh: `scripts\verify_phase.ps1 -Focused` và `pytest` (dùng `--basetemp` NGẮN trên Windows).
3. `scripts\freeze_v2_benchmark.py verify` OK; `git status` sạch.
4. Người còn lại **review + duyệt** PR. Chỉ khi đó mới merge.

## 5. Phụ thuộc (dependencies)

- **Tách file** để tránh conflict: `requirements.txt` = gateway (An);
  `requirements-kb.txt` = LLM/kho tri thức (Nghĩa). Không đổi tên `requirements.txt`
  (CI/`run_dev.ps1`/`verify_phase.ps1` đang tham chiếu).
- Không cài `httpx2` (gói mồi nhử). Cảnh báo Starlette về nó là bình thường.

## 6. Dữ liệu (quan trọng)

- `*.jsonl` (benchmark v2, holdout) **không** lên git (gitignored). Khi Nghĩa clone repo sẽ
  **không** có các file này → phải nhận qua kênh riêng (bundle/sealed), **không** commit lên git.
- **Không** mở nội dung `datasets/v2/cases/holdout.jsonl` / `labels/holdout.jsonl`.
- Kho tri thức doanh nghiệp là **dữ liệu tổng hợp mới** (`datasets/enterprise-kb/`), tách khỏi benchmark cũ.

## 7. Chỉ tổng kết & đánh giá sau khi review từng phần

Không đánh giá kết quả giữa chừng. Sau mỗi giai đoạn có review + merge; chỉ khi các phần đã
được duyệt mới tổng hợp số liệu và viết báo cáo/đánh giá.
"""