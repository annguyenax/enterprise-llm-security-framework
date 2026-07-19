# Phase 12E.4 Final Reconciled Holdout Plan

> **Trạng thái: KẾ HOẠCH ĐÃ ĐƯỢC ĐỐI CHIẾU (reconciled). CHƯA TRIỂN KHAI.**
> **Holdout VẪN CHƯA ĐƯỢC PHÊ DUYỆT.**
>
> Tài liệu này là kế hoạch ràng buộc cho Phase 12E.4. Nó không phải là kết quả,
> không chứa số liệu đánh giá nào, và không cho phép chạy holdout. Việc chạy
> holdout chỉ diễn ra sau khi đủ chuỗi gate ở §"Trình tự thực thi holdout" và
> có văn bản uỷ quyền của người duy trì.

**Kế hoạch này được viết ở bước DOCUMENTATION ONLY.** Không có file Python,
PowerShell, test, benchmark, app code hay guard nào bị sửa khi tạo nó.

---

## 1. Candidate Identity

| Mục | Giá trị |
|---|---|
| Branch | `phase-12e-4-holdout-planning` |
| Baseline HEAD | `c0b8f6d6fb9fb5faa24f58610368fdc50ca41b62` |
| Working tree khi lập kế hoạch | clean |
| Phase 12E.3 implementation identity | `c6d91c78e11009e96a76db08c0dfbb710504c227` (ancestor của baseline) |
| Phase 12E.3 verdict | **CLOSED — PASS** (`code-x-phase-12e-3-validation-artifact-closure.md`) |
| Gemini methodology verdict cho kế hoạch này | **PASS** (xem `gemini-phase-12e-4-methodology-review.md`) |

Schema và chính sách hiện hành, đọc trực tiếp từ code:

| Hằng số | Giá trị | Vị trí |
|---|---|---|
| `RESULT_SCHEMA_VERSION` | 2 | `scripts/run_v2_evaluation.py:67` |
| `RESULT_MANIFEST_SCHEMA_VERSION` | 1 | `scripts/run_v2_evaluation.py:68` |
| `SUPPORTED_SPLITS` | `("development", "validation")` | `scripts/run_v2_evaluation.py:69` |
| `CONFIG_REGISTRY_VERSION` | 1 | `scripts/run_v2_evaluation.py:71` |
| `ANALYSIS_SCHEMA_VERSION` | 1 | `scripts/analyze_v2_results.py:30` |
| `ANALYSIS_MANIFEST_SCHEMA_VERSION` | 1 | `scripts/analyze_v2_results.py:31` |
| `CSV_SCHEMA_VERSION` | 1 | `scripts/analyze_v2_results.py:33` |
| `RATE_REPORTING_MIN_N` | 10 | `scripts/analyze_v2_results.py:34` |
| `latency_reportable` | `False` | `scripts/analyze_v2_results.py:544, 1491, 1787` |
| `repetitions` / `warmup` | 2 / 0 | `scripts/run_v2_evaluation.py:2272-2273` |
| Test hiện có | 17 + 54 + 23 = **94** | `tests/test_guard_profile.py`, `tests/test_v2_evaluation_runner.py`, `tests/test_v2_result_analyzer.py` |

---

## 2. Binding Decisions

Toàn bộ adjudication của người duy trì được tiếp nhận nguyên văn và có hiệu lực
ràng buộc:

1. **Latency: chọn L2.** Không có claim latency nào được báo cáo.
2. **Vai trò:** Claude Code là primary implementer; Code X là plan reconciler và
   artifact-integrity auditor (**không** implement).
3. **Split:** `SUPPORTED_SPLITS` giữ nguyên `("development", "validation")`.
   Không thêm holdout. Không tạo `AUTHORIZED_SPLITS` hợp nhất ngầm hai đường.
4. **Holdout dùng request path riêng và request type riêng**, kèm loader riêng
   nhận capability đã xác minh. Không dùng
   `load_split_benchmark(..., authorized=True)`.
5. **Authorization** là canonical JSON nghiêm ngặt, file ngoài repository.
6. **Thứ tự fail-closed** cố định (§7).
7. **One-shot theo thủ tục**, retry chỉ qua lineage `supersedes`.
8. **Schema holdout tách riêng** khỏi schema development/validation.
9. **Không chạy lại validation.**
10. **Mock Provider only.**
11. **Trusted-maintainer threat model.**
12. **Holdout vẫn chưa được phê duyệt.**

### Ba khiếm khuyết trong bản kế hoạch trước đã được sửa

| Đề xuất cũ (bị bác) | Vì sao sai | Thay bằng |
|---|---|---|
| `AUTHORIZED_SPLITS` | Hợp nhất ngầm đường thường và đường holdout; một tập hợp trở thành ranh giới an toàn duy nhất | Request type riêng (`HoldoutRunRequest`) |
| `load_split_benchmark(..., authorized=True)` | Một tham số bool trở thành ranh giới an toàn duy nhất | Loader riêng nhận capability đã xác minh |
| Chặn thẳng `attempt > 1` | Buộc phải **xoá evidence** để retry — đi ngược mục tiêu giữ bằng chứng | Retry có kiểm soát qua `supersedes_authorization_sha256` |

---

## 3. L2 Latency Decision

**Chọn L2. Không có latency reportable trong Phase 12E.**

### Nội dung quyết định

- **Gỡ RQ4 khỏi danh sách research question có thể báo cáo.**
- **H5 được phân loại lại thành kỳ vọng mô tả, không báo cáo** (descriptive,
  non-reportable).
- `latency_reportable` giữ nguyên `false`.
- `p50` và `p95` giữ nguyên `null`.
- **Không** đổi hành vi determinism repetition để phục vụ latency.
- **Không** thêm latency mini-gate.
- **Không** yêu cầu máy đo latency chuyên dụng.
- Timing lúc chạy **chỉ được giữ làm chẩn đoán determinism**.

### Bằng chứng dẫn tới L2

| Bằng chứng | Vị trí |
|---|---|
| `latency_reportable: False` đã hard-code ở ba nơi | `analyze_v2_results.py:544, 1491, 1787` |
| `repetitions: 2, warmup: 0` | `run_v2_evaluation.py:2272-2273` |
| Mẫu latency là **sản phẩm phụ** của kiểm tra determinism | `_merge_repetition_latency:1980` |
| Determinism là mục đích thật của hai lần lặp | `validate_repetition_determinism:1960` |
| Analyzer bắt buộc đúng hai mẫu timing mỗi case hoàn thành | `analyze_v2_results.py:776-777` |
| Grok "Latency Decision B (binding)" | `grok-phase-12e-3-analyzer-plan.md:452-470` |
| Code X closure xác nhận latency non-reportable, p50/p95 null | `code-x-phase-12e-3-validation-artifact-closure.md:57` |

Nói ngắn gọn: hai lần lặp tồn tại để chứng minh **quyết định của pipeline là tất
định**, không phải để đo thời gian. Mẫu thời gian chỉ được gom kèm. Đó không
phải một giao thức đo latency khoa học, và không được trình bày như vậy.

### L1 — phương án bị bác, giữ lại kèm lý do

L1 (giữ latency reportable, thêm latency mini-gate được audit riêng) bị bác cho
Phase 12E, vì bốn lý do:

1. **Máy đo không hợp lệ.** Kế hoạch gốc §16 đòi máy không chạy song song việc
   khác. Máy phát triển hiện tại là laptop Windows dùng chung, có chạy model
   local (Ollama) với `keepAlive`. Số latency đo trong điều kiện đó không phòng
   thủ được trước phản biện học thuật.
2. **L1 đụng vào phần vừa PASS.** `_merge_repetition_latency` và ràng buộc "đúng
   hai mẫu" (`analyze_v2_results.py:776-777`) nằm giữa hợp đồng determinism đã
   được audit. Sửa chúng để lấy latency là đánh đổi bằng chứng determinism đang
   có lấy một số đo dù sao cũng yếu.
3. **RQ4 không phải research question trung tâm.** RQ1/RQ2/RQ3/RQ5 (AOMR, FPR,
   tính cần thiết/dư thừa của từng lớp, residual risk) đều đo được và đã chạy
   validation thành công. Chúng đủ cho phạm vi luận văn security.
4. **Guard là rule-based tất định.** H5 của chính kế hoạch gốc dự đoán latency
   chủ yếu đến từ `retrieval`, không từ guard. Kết quả latency, nếu có, nhiều
   khả năng chỉ xác nhận điều đã hiển nhiên.

L1 có thể được xem xét lại trong một phase sau, nhưng chỉ khi có máy đo cô lập
và một gate latency độc lập — và đó sẽ là một adjudication riêng, không thuộc
Phase 12E.4.

---

## 4. Threat Model

**Trusted-maintainer, dựa trên thủ tục và filesystem.**

### Điều quy trình này làm được

- Giảm khả năng chạy holdout **do nhầm lẫn** (gõ nhầm lệnh, quên trạng thái).
- Ngăn chạy lại **vô tình** trên cùng một attempt root.
- Ngăn **ghi đè** bằng chứng đã có.
- Ngăn CLI **vô tình** chạm tới holdout trong lúc phát triển.
- Ngăn analyzer **trộn** nhiều attempt.
- Ngăn agent **tự ý** chạy holdout khi chưa có uỷ quyền.
- Làm cho mọi attempt được giữ lại đều **audit được**.

### Điều quy trình này KHÔNG làm được

> **Quy trình này không ngăn chặn về mặt toán học hay mật mã việc một quản trị
> viên cục bộ có ác ý xoá bằng chứng. Nó làm giảm về mặt thủ tục khả năng thực
> thi do nhầm lẫn hoặc không được phép, và làm cho các attempt được giữ lại trở
> nên audit được, dưới mô hình trusted-maintainer.**

Cụ thể, mô hình này **không** phòng thủ trước: người có quyền admin cục bộ xoá
attempt root rồi chạy lại · tự sửa và tự ký file authorization · sửa code rồi
commit lại · chỉnh sửa mtime hoặc hash thủ công. Bảo đảm one-shot là **thủ tục**,
không phải mật mã.

---

## 5. Authorization Schema

Định danh schema: **`phase12e4-holdout-authorization-v1`**

Canonical JSON nghiêm ngặt. **File nằm ngoài repository, không bao giờ commit.**

| Khoá | Ràng buộc |
|---|---|
| `schema_version` | `1` |
| `authorization_id` | UUID, duy nhất cho mỗi lần uỷ quyền |
| `issued_at_utc` | ISO-8601, hậu tố `Z` |
| `issued_by` | `maintainer:annguyenax` |
| `purpose` | `phase12e4_holdout_c0_c7` |
| `execution_branch` | khớp chính xác branch thực thi |
| `execution_commit` | full lowercase SHA-1, khớp chính xác commit implementation |
| `benchmark_manifest_sha256` | khớp manifest FINAL 9 artifact |
| `provider_id` | `mock` (giá trị duy nhất được chấp nhận) |
| `config_ids` | đúng 8 mục C0–C7, đúng thứ tự |
| `config_hashes` | map 8 mục, khớp `CONFIG_REGISTRY` |
| `result_schema_version` | khớp schema holdout |
| `result_manifest_schema_version` | khớp schema holdout |
| `analysis_schema_version` | khớp schema holdout |
| `analysis_manifest_schema_version` | khớp schema holdout |
| `analysis_contract_sha256` | khớp hợp đồng analyzer |
| `mapping_sha256` | khớp family mapping |
| `output_root` | đường dẫn tuyệt đối, **ngoài repository** |
| `attempt` | số nguyên ≥ 1 |
| `supersedes_authorization_sha256` | `null` khi `attempt = 1`; bắt buộc khi `attempt > 1` |
| `holdout_authorized` | `true` |

### Artifact được phép lưu

`authorization_id` · SHA-256 của file authorization · định danh attempt ·
contract identity an toàn.

### Artifact TUYỆT ĐỐI KHÔNG được lưu

Nội dung file authorization · `output_root` tuyệt đối · query thô · answer ·
retrieved content · secret/canary · bất kỳ đường dẫn đặc thù máy nào.

Đây là cùng một hợp đồng an toàn mà Phase 12E.3 closure đã kiểm chứng: quét đệ
quy toàn bộ result/analysis JSON cùng 208 dòng CSV, không tìm thấy trường thô,
canary, retrieved content, answer hay đường dẫn tuyệt đối nào.

**Chữ ký GPG không bắt buộc** dưới mô hình trusted-maintainer đã khai báo.

---

## 6. Runner Design

Mọi thay đổi dưới đây là **phạm vi triển khai tương lai**, chưa được thực hiện.

| # | File · function | Thay đổi | Lý do | Positive test | Negative test | Failure mode | Auditor độc lập |
|---|---|---|---|---|---|---|---|
| R1 | `run_v2_evaluation.py:69` `SUPPORTED_SPLITS` | **Giữ nguyên** `("development","validation")` | Mở tập này sẽ mở đồng thời cả sáu gate (runner ba, analyzer ba) | `test_supported_splits_exactly_dev_val` | `test_holdout_never_in_supported_splits` | Đổi một hằng số làm holdout reachable ngay từ CLI | Grok |
| R2 | mới: `HoldoutAuthorization` (frozen dataclass) + `parse_holdout_authorization()` | Parse canonical JSON nghiêm ngặt, exact-keys | Uỷ quyền phải là vật chứng verify được, không phải một cờ CLI | `test_valid_authorization_parses` | `test_malformed_authorization_rejected`; `test_extra_or_missing_keys_rejected`; `test_wrong_schema_version_rejected` | Parser lỏng cho phép authorization giả đi lọt | Grok |
| R3 | mới: `HoldoutRunRequest` (**tách hẳn khỏi `RunRequest`**) | Type riêng, **không có** field `split` | Không hợp nhất đường thường và đường holdout | `test_holdout_request_type_is_distinct` | `test_runrequest_cannot_carry_holdout` | Một bool trở thành ranh giới an toàn duy nhất | Grok |
| R4 | mới: `load_authorized_holdout_benchmark(capability)` | Loader riêng, chỉ nhận capability đã xác minh | `load_split_benchmark` không bao giờ chạm holdout | `test_authorized_loader_with_verified_capability` | `test_direct_loader_call_without_capability_fails` | Gọi trực tiếp từ script khác đọc được holdout | Grok |
| R5 | mới: `holdout_preflight()` | Áp dụng đúng thứ tự fail-closed §7 | Không đọc holdout và không ghi output trước khi xác minh xong | `test_preflight_writes_receipt_before_reading_records` | `test_unauthorized_fails_before_any_read_or_write` | Đọc holdout rồi mới phát hiện sai uỷ quyền | Grok |
| R6 | `_validate_output_root:593` (mở rộng cho holdout) | Attempt root phải **chưa tồn tại**; claim atomic bằng `mkdir(exist_ok=False)` | Chống race và chống ghi đè | `test_atomic_claim_succeeds_once` | `test_concurrent_claim_second_fails`; `test_existing_root_rejected`; `test_root_is_file_rejected`; `test_repository_local_root_rejected`; `test_symlink_containment_escape_rejected` | Hai lần chạy ghi chung một root | Grok |
| R7 | mới: `write_start_receipt()` | Ghi receipt an toàn ngay sau khi claim root | Có dấu vết ngay cả khi tiến trình chết giữa chừng | `test_start_receipt_written_before_records` | `test_receipt_contains_no_forbidden_field` | Crash sớm không để lại dấu vết audit | Code X |
| R8 | `build_parser:2528` | Thêm `--holdout-authorization FILE`; holdout mode **từ chối** `--split`; bắt buộc đủ C0–C7; provider chỉ `mock`; **không có** `--force` | CLI thường không bao giờ vô tình chạm holdout | `test_holdout_cli_with_authorization_accepted` | `test_normal_split_holdout_rejected`; `test_holdout_mode_with_split_rejected`; `test_holdout_partial_config_set_rejected`; `test_holdout_non_mock_provider_rejected`; `test_no_force_flag_exists` | `--split holdout` trần được chấp nhận | Grok |
| R9 | `run_v2_evaluation.py:2417, 2502` | Giữ nguyên no-overwrite; áp dụng cho holdout | Một lần là một lần | `test_no_overwrite_behavior_preserved` | `test_holdout_destination_exists_fails` | Ghi đè bằng chứng đã có | Code X |

---

## 7. Order of Operations (fail-closed, thứ tự bắt buộc)

```
1. Parse authorization nghiêm ngặt (canonical JSON, exact keys)
2. Xác thực branch / commit / clean-tree khớp chính xác
3. Xác thực provider / config / contract identity
4. Verify FINAL benchmark manifest (9 artifact)
5. Xác thực external output root
6. Claim attempt root một cách atomic
7. Ghi start receipt an toàn
8. CHỈ KHI ĐÓ mới nạp holdout records
```

**Yêu cầu tuyệt đối:** mọi request không hợp lệ phải fail **trước khi đọc bất kỳ
holdout record nào** và **trước khi ghi bất kỳ output nào**.

---

## 8. Analyzer Design

| # | File · function | Thay đổi | Positive test | Negative test | Failure mode | Auditor độc lập |
|---|---|---|---|---|---|---|
| A1 | `analyze_v2_results.py:2135` | Giữ nguyên gate split hiện tại; holdout đi đường riêng | `test_analyzer_dev_val_path_unchanged` | `test_analyzer_split_holdout_rejected` | Analyzer tự mở đường holdout | Grok |
| A2 | mới: `--holdout-authorization FILE` | Analyzer **tự xác thực lại** authorization, không tin artifact của runner | `test_analyzer_revalidates_authorization` | `test_analyzer_missing_authorization_rejected`; `test_analyzer_wrong_authorization_rejected`; `test_analyzer_wrong_authorization_hash_rejected` | Analyzer tin mù metadata artifact | Grok |
| A3 | mới: `validate_single_attempt()` | Chấp nhận **đúng một** attempt C0–C7 hoàn chỉnh | `test_analyzer_accepts_one_complete_attempt` | `test_analyzer_rejects_mixed_attempts`; `test_analyzer_rejects_partial_matrix` | Trộn attempt làm số liệu vô nghĩa | Code X |
| A4 | khối metric policy | **Không đổi một hằng số nào** | `test_12e3_metric_policy_constants_unchanged` | `test_abr_macro_f1_pvalue_family_percentage_absent` | Policy trôi âm thầm, vi phạm 12E.3 | **Gemini** |

---

## 9. Schema Versioning

| Artifact | Development / Validation (giữ nguyên) | Holdout (mới) |
|---|---|---|
| result | `RESULT_SCHEMA_VERSION = 2` | `HOLDOUT_RESULT_SCHEMA_VERSION = 1` |
| result-manifest | `RESULT_MANIFEST_SCHEMA_VERSION = 1` | `HOLDOUT_RESULT_MANIFEST_SCHEMA_VERSION = 1` |
| analysis | `ANALYSIS_SCHEMA_VERSION = 1` | `HOLDOUT_ANALYSIS_SCHEMA_VERSION = 1` |
| analysis-manifest | `ANALYSIS_MANIFEST_SCHEMA_VERSION = 1` | `HOLDOUT_ANALYSIS_MANIFEST_SCHEMA_VERSION = 1` |

**Khoá bổ sung trong holdout result:**
`authorization_id` · `holdout_authorization_sha256` · `attempt` ·
`supersedes_authorization_sha256` · `holdout_authorized = true`.

**Không** thêm khoá latency nào. Schema development/validation hiện hành **được
giữ nguyên không đổi**.

### Chính sách metric Phase 12E.3 — giữ nguyên tuyệt đối

AOMR là allowed-outcome metric **duy nhất** · **không ABR** · **không macro** ·
**không F1** · `RATE_REPORTING_MIN_N = 10` · Wilson 95% **không** continuity
correction, chỉ áp dụng cho AOMR/FPR đủ điều kiện · family **chỉ raw counts** ·
**không** family percentage · **không** p-value.

Kiểm chứng: `analyze_v2_results.py:34, 539, 545, 549, 1487-1497, 1783-1789`.
Phase 12E.4 **không được** sửa bất kỳ hằng số nào trong khối này.

---

## 10. One-Shot and Retry Contract

### One-shot

- Attempt root **phải chưa tồn tại**.
- Claim root một cách **atomic**.
- **Không ghi đè, không chạy lại âm thầm, không có đường `--force`.**
- Một attempt **fatal hoặc partial vẫn được giữ nguyên**, không xoá.

### Retry — không chặn thẳng `attempt > 1`

Chặn thẳng `attempt > 1` sẽ buộc người dùng phải **xoá bằng chứng** để thử lại,
đi ngược mục tiêu giữ evidence. Thay vào đó, một lần retry hợp lệ đòi hỏi **đủ
sáu điều kiện**:

1. Uỷ quyền mới, tường minh, từ người duy trì.
2. `authorization_id` mới.
3. External output root mới.
4. `attempt` tăng.
5. `supersedes_authorization_sha256` trỏ tới authorization trước đó.
6. Implementation commit, provider, configs, manifest, mapping, metric contract
   và analysis contract **không đổi** — trừ khi được re-adjudicate riêng.

**Analyzer không bao giờ trộn attempt.**

> Bảo đảm one-shot là **thủ tục và dựa trên filesystem** dưới mô hình
> trusted-maintainer. Nó không phòng thủ trước một quản trị viên cục bộ có ác ý
> xoá bằng chứng.

---

## 11. Exact Allowed Future Implementation Files

Đây là **phạm vi triển khai TƯƠNG LAI**, sẽ do **Claude Code** thực hiện sau khi
kế hoạch này được review và commit. **Không file nào trong danh sách này bị sửa
ở bước documentation-only hiện tại.**

```
scripts/run_v2_evaluation.py
scripts/analyze_v2_results.py
scripts/verify_phase.ps1
tests/test_v2_holdout_authorization.py          (mới)
tests/test_v2_evaluation_runner.py
tests/test_v2_result_analyzer.py
docs/ai-collaboration/00_PROJECT_STATE.md
docs/ai-collaboration/01_AGENT_ROLES.md
docs/ai-collaboration/04_DECISIONS.md
docs/ai-collaboration/05_OPEN_QUESTIONS.md
docs/ai-collaboration/06_PHASE_12E_MASTER_PLAN.md
docs/ai-collaboration/07_PHASE_12E4_HOLDOUT_PLAN.md
docs/modernization-final-plan.md
CLAUDE.md
```

**`scripts/verify_phase.ps1` KHÔNG bị sửa ở bước documentation-only này.** Nó nằm
trong danh sách vì bước triển khai tương lai sẽ cần cập nhật `$FocusedModules` để
thêm `tests/test_v2_holdout_authorization.py`.

---

## 12. Exact Forbidden Files

```
datasets/v2/**              9 artifact FINAL freeze — đổi một byte là benchmark v3
app/**                      guard và pipeline không đổi trong 12E.4
scripts/build_v2_benchmark.py
scripts/validate_v2_benchmark.py
scripts/freeze_v2_benchmark.py
requirements.txt            không cài gói mới
redteam/**
reports/evaluation/**       artifact v1, không ghi đè
report-latex-template/**
tests/test_guard_profile.py 12E.1 đã PASS, không đụng
```

Mọi file authorization và artifact holdout nằm **ngoài repository** và **không
được track**.

---

## 13. Required Tests

Toàn bộ dùng **fixture tổng hợp**. **Không đọc case hay label holdout thật.**

### Positive (10)

Authorization hợp lệ parse thành công · holdout CLI với authorization hợp lệ ·
loader với capability đã xác minh · atomic claim thành công một lần · start
receipt được ghi trước records · analyzer chấp nhận đúng một attempt hoàn chỉnh ·
hành vi development/validation **không đổi** · chính sách metric 12E.3 **không
đổi** · determinism hai lần lặp giữ nguyên · `latency_reportable=false`,
`p50`/`p95` null.

### Negative (24+)

Authorization malformed · thừa khoá · thiếu khoá · sai `schema_version` · sai
branch · sai commit · dirty tree · sai benchmark manifest hash · provider khác
`mock` · config thiếu / trùng / lạ · sai config hash · sai result contract
version · sai analysis contract version · output root nằm trong repository ·
root là file thay vì thư mục · root đã tồn tại · authorization/root mismatch ·
replay authorization · concurrent atomic claim (cái thứ hai fail) · symlink hoặc
resolved-path containment escape (nơi hệ điều hành hỗ trợ) · gọi trực tiếp
holdout loader không có capability · `--split holdout` bị từ chối · holdout mode
kèm `--split` bị từ chối · analyzer thiếu hoặc sai authorization · analyzer trộn
attempt · analyzer partial matrix · analyzer sai authorization hash · raw-field
và absolute-path suppression.

---

## 14. Validation Policy — KHÔNG CHẠY LẠI

**Validation của Phase 12E.3 đã được quan sát và khoá lại. Không được chạy lại.**

Xác minh triển khai của Phase 12E.4 gồm đúng những mục sau:

- unit test và negative test tổng hợp;
- focused suite;
- full suite;
- benchmark validator;
- frozen-manifest verification;
- development-only C0–C7 smoke;
- **không validation;**
- **không holdout.**

Mọi lần chạy lại validation trong tương lai đều đòi hỏi một lần re-adjudication
tường minh riêng của người duy trì.

---

## 15. Mechanical Verification

`.\scripts\verify_phase.ps1` — script, không phải LLM. Bước triển khai tương lai
sẽ thêm `tests/test_v2_holdout_authorization.py` vào `$FocusedModules`.

Yêu cầu để qua: focused suite PASS · full suite PASS (94 + N) ·
`validate_v2_benchmark.py` PASS · `freeze_v2_benchmark.py verify` 9 file FINAL
không drift · `git diff --check` clean · scope invariants clean.

---

## 16. Development-Only Smoke

C0–C7 trên **development**, Mock Provider, output root ngoài repository, chạy
trong **worktree sạch riêng**. **Không validation. Không holdout.**

Mục đích: chứng minh đường development/validation không hồi quy sau khi thêm
đường holdout.

---

## 17. Grok Audit Gate — Technical / Security

Độc lập, đọc commit trực tiếp. Phạm vi: đường holdout có thật sự tách khỏi đường
thường không · sáu gate hiện có còn nguyên vẹn không · thứ tự fail-closed có đúng
không · có bypass nào không (biến môi trường, request field, gọi hàm trực tiếp,
symlink) · authorization có replay được không · atomic claim có race không · CLI
có vô tình chạm holdout không.

---

## 18. Gemini Audit Gate — Methodology / Claims

Phạm vi: chính sách metric 12E.3 còn nguyên vẹn không (AOMR only, no ABR/macro/
F1, `MIN_N=10`, Wilson 95% no continuity correction, family raw counts, no family
percentage, no p-value) · L2 được ghi nhận đúng, RQ4 đã gỡ và H5 đã phân loại
lại · kiểm soát claim · giới hạn Mock Provider được khai báo rõ · không có claim
production hay claim nhân quả.

---

## 19. Code X Integrity Gate

**Code X là plan reconciler và artifact-integrity auditor. Code X KHÔNG
implement.**

Sau khi chạy holdout: tái lập độc lập 8 `result.json` + 8 `result-manifest.json`
(SHA-256 và byte size), bộ ba analysis, experiment identity; quét forbidden-field
trên toàn bộ JSON và CSV. Khuôn mẫu:
`code-x-phase-12e-3-validation-artifact-closure.md`.

---

## 20. Human Authorization Boundary

Chỉ **người duy trì** cấp uỷ quyền holdout. **Không agent nào — kể cả Claude
Code — được tạo, sửa hoặc tự ký file authorization.** Không agent nào được chạy
holdout khi chưa có file uỷ quyền do người duy trì cấp.

---

## 21. Holdout Execution Sequence

```
 1  Triển khai (Claude Code; GitHub Copilot hỗ trợ chiến thuật dưới review của Claude)
 2  Qwen / Hermes pre-audit (advisory, không phát hành verdict)
 3  scripts/verify_phase.ps1                    → SCRIPT, không LLM
 4  Development-only smoke C0-C7                → không validation, không holdout
 5  Grok technical/security audit               → PASS bắt buộc
 6  Gemini methodology/claims audit             → PASS bắt buộc
 7  NGƯỜI DUY TRÌ cấp authorization             → văn bản, ghim commit
 8  Holdout C0-C7 chạy đúng MỘT LẦN             → Mock only, root ngoài repo, worktree riêng
 9  Analyzer chạy một lần                       → tự xác thực lại authorization
10  Code X closure audit                        → artifact integrity
11  Gemini claim gate                           → duyệt câu chữ luận văn
```

Không được nhảy bước. Bước 7 **không thể** uỷ quyền cho agent.

---

## 22. Failure Evidence Retention

Một attempt fatal hoặc partial: **giữ nguyên toàn bộ** artifact, transcript và
start receipt. **Không xoá.** Ghi vào `04_DECISIONS.md`. Analyzer từ chối partial
matrix, nhưng bằng chứng vẫn tồn tại trên đĩa.

Rollback dùng `git revert`, **không** `reset --hard`.

Tiền lệ: Phase 12E.3 attempt 1 kết thúc bằng lỗi `manifest_missing_artifact` và
đã được **giữ lại và ghi nhận**, không bị xoá.

---

## 23. Artifact Closure

8 `result.json` + 8 `result-manifest.json` (SHA-256 và byte size) ·
`analysis.json` / `analysis-table.csv` / `analysis-manifest.json` · experiment
identity tái lập độc lập · quét forbidden-field trên toàn bộ JSON và CSV.

Artifact **không được track** trong git.

---

## 24. Branch and Commit Strategy

- Kế hoạch này commit lên `phase-12e-4-holdout-planning` (commit tài liệu).
- Triển khai: branch riêng rẽ từ commit kế hoạch.
- Holdout chạy trong **git worktree riêng**, branch execution riêng, artifact
  nằm ngoài repository và không track — đúng khuôn mẫu Phase 12E.3
  (`D:\p12e3-wt-c6d91c7`).

---

## 25. Claims bị cấm

Không tuyên bố "hệ thống chặn X% tấn công **trong thực tế**" · không tuyên bố
"DLP ngăn rò rỉ dữ liệu" (Mock Provider không echo retrieved context) · không
trình bày tổng các delta biên như một phép phân hoạch cộng tính · không báo cáo
phần trăm theo từng family · không tuyên bố "có ý nghĩa thống kê" ở cỡ mẫu này ·
**không claim latency nào dưới L2** · không tuyên bố "sẵn sàng production" ·
không claim nhân quả vượt ra ngoài so sánh trong phạm vi benchmark.

---

## 26. Trạng thái cuối của kế hoạch

**Holdout vẫn CHƯA ĐƯỢC PHÊ DUYỆT.**

Tài liệu này là kế hoạch, không phải kết quả. Không có số liệu đánh giá nào được
tạo ra. Không có claim luận văn nào được đưa ra. Việc triển khai sẽ do Claude
Code thực hiện sau khi kế hoạch được review và commit; việc chạy holdout chỉ diễn
ra sau khi đủ chuỗi gate §21 và có văn bản uỷ quyền của người duy trì.
