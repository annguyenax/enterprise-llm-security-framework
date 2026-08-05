# datasets/enterprise-kb/

Cơ sở tri thức doanh nghiệp tổng hợp, mang **metadata phân quyền** mà
`datasets/clean/` và `datasets/poisoned/` không có. Đây là dữ liệu đầu vào cho
Enterprise Retriever (Slice 2) và cho ACL Guard.

> **Trạng thái: DRAFT.** `manifest_status` là `"draft"`, chưa qua audit độc lập
> nào. Đây **không** phải artifact đã đóng băng và không được đối xử như
> `datasets/v2/` (9 file FINAL freeze, tuyệt đối không sửa).

## Quan hệ với các dataset khác

| Thư mục | Vai trò | Được sửa? |
|---|---|---|
| `datasets/v2/` | Benchmark đánh giá, 9 artifact FINAL freeze | **KHÔNG** |
| `datasets/clean/`, `datasets/poisoned/` | Fixture cho guard, Phase 3 | Hạn chế |
| `datasets/enterprise-kb/` | KB có phân quyền, phục vụ retriever | Có, khi còn draft |

Thư mục này **không** đụng tới `datasets/v2/`. `verify_phase.ps1` kiểm hash của
v2 mỗi lần chạy và vẫn PASS.

## Cấu trúc

```
datasets/enterprise-kb/
├── corpus/documents.jsonl                   # 12 tài liệu, canonical JSONL — KHÔNG được git track
└── manifests/enterprise-kb-manifest.json    # hash + thống kê phân bố
```

## Corpus không nằm trong git — đây là chủ ý

`.gitignore` loại trừ `*.jsonl` trên toàn repo và **ghi rõ không được thêm rule
un-ignore**, để split holdout của benchmark không bị lộ ra git như tác dụng phụ
của đóng gói. `datasets/v2/corpus/documents.jsonl` cũng không được track vì lý
do đó (`git ls-files datasets/v2/corpus/` trả về rỗng).

Nên corpus ở đây theo đúng pattern của v2: **builder tất định được commit,
artifact thì không, toàn vẹn kiểm bằng manifest SHA-256.**

```powershell
.venv\Scripts\python.exe scripts/build_enterprise_kb.py           # sinh lại
.venv\Scripts\python.exe scripts/build_enterprise_kb.py --check   # phát hiện lệch
```

Nguồn sự thật là `scripts/build_enterprise_kb.py`. Sửa tay
`corpus/documents.jsonl` là vô nghĩa — lần build sau ghi đè, và `--check` cùng
manifest hash sẽ báo lệch trước.

## Vì sao JSONL chứ không phải YAML

Kế hoạch ban đầu ghi `manifest.yaml`. Đã đổi sang JSON/JSONL vì:

1. **PyYAML cố ý không có trong `requirements.txt`** (AGENT_RULES rule 11). Bộ
   parser frontmatter hiện có trong `app/services/dataset_loader.py` là bản
   hand-rolled chỉ đọc được `key: value` phẳng — không đọc được mảng, mà
   `access_roles` và `access_departments` đều là mảng.
2. `datasets/v2/corpus/documents.jsonl` **đã dùng đúng convention này** (JSONL,
   `sort_keys=True`, `ensure_ascii=False`).
3. Canonical JSON cho hash tái lập được — điều kiện cần nếu sau này muốn freeze.

## Schema mỗi dòng

Khoá bắt buộc, đúng 12, không thừa không thiếu:

| Khoá | Kiểu | Ghi chú |
|---|---|---|
| `document_id`, `external_id` | `str` | Phải trùng nhau |
| `title`, `content` | `str` | ≤ 300 / ≤ 20.000 ký tự |
| `language` | `str` | `"vi"` |
| `source_key` | `str` | Luôn là `"enterprise_kb"` |
| `sensitivity` | `str` | `public` \| `internal` \| `confidential` \| `restricted` |
| `access_roles` | `list[str]` | Đã sắp xếp, không trùng, thuộc `{member, leader, superadmin}` |
| `access_departments` | `list[str]` | Đã sắp xếp; `["*"]` = toàn tổ chức |
| `owner_department` | `str` | Phải nằm trong `access_departments` (trừ khi `*`) |
| `valid_from`, `valid_to` | `str \| null` | UTC, giây, `YYYY-MM-DDTHH:MM:SS+00:00` |

**Cố ý KHÔNG có** `trust_level`, `classification`, `source_type`, `is_poisoned`,
`expected_decision`. Những trường đó do server gán
(`app/core/source_policy.py`), y hệt cách `IngestionDocument` được thiết kế.
Validator từ chối dòng nào chứa chúng.

## `sensitivity` KHÔNG phải `classification`

Đây là ràng buộc quan trọng nhất của schema này.

`app/guards/provenance_guard.py` có allow-list đóng băng
`ALLOWED_CLASSIFICATIONS = {"internal"}`. Nếu đổ `sensitivity: confidential`
vào trường `classification`, **mọi chunk sẽ bị Provenance Guard từ chối** và
pipeline dừng ở `STOP_ALL_REJECTED_PROVENANCE`.

Vì vậy `sensitivity` là **trục độc lập**, do ACL Guard xử lý
(`app/retrieval/acl.py`). Trục trust giữ nguyên như các phase đã audit.

## Độ phủ của 12 tài liệu

Corpus được soạn để chạm mọi nhánh quyết định của `evaluate_acl`:

- 4 mức `sensitivity` (public 1, internal 5, confidential 4, restricted 2)
- Giới hạn theo phòng ban (`["it"]`) và toàn tổ chức (`["*"]`)
- Giới hạn theo vai trò: mọi vai trò / chỉ leader+superadmin / chỉ superadmin
- Cửa sổ hiệu lực: không có, đã hết hạn (`ekb-doc-0008`), chưa hiệu lực
  (`ekb-doc-0007`), đang trong hạn (`ekb-doc-0009`)

## Ghi chú thiết kế cần xác nhận ở Slice 2

`evaluate_acl` **không có đường tắt cho superadmin**: phòng ban được kiểm tra
cho mọi vai trò. Trong khi đó `store.accessible_documents` hiện cho superadmin
thấy tất cả. Corpus này xử lý bằng cách liệt kê tường minh `workspace` (hoặc
`*`) trong `access_departments` của những tài liệu superadmin cần đọc.

Đây là lựa chọn có chủ ý — allow-list im lặng cho qua thì không còn là
allow-list — nhưng nó khác mô hình quyền hiện tại, nên **cần người duy trì xác
nhận** trước khi Slice 2 nối dây.

## An toàn dữ liệu

100% hư cấu, công ty giả định *Northwind Retail Group*, thống nhất với
`datasets/clean/`. Không có dữ liệu cá nhân thật, không có secret thật.

## Kiểm tra

```powershell
.venv\Scripts\python.exe scripts/validate_enterprise_kb.py
.venv\Scripts\python.exe -m pytest tests/test_enterprise_kb_schema.py -q
```
