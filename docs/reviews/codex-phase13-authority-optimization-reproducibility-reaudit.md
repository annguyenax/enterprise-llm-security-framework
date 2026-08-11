# Tái audit Phase 13: authority-impersonation, reproducibility và Chương 4

**Ngày audit:** 2026-08-11  
**Vai trò:** Artifact-integrity & methodology auditor; không implement  
**Commit được xem:** `2793459`, `b691c90`, `8e9e388`, `7c04062`  
**Không thực hiện:** không chạy holdout, không sửa dataset, không commit/push, không báo latency.

## 1. Verdict tóm tắt

| Hạng mục | Verdict | Kết luận ngắn |
|---|---|---|
| Toàn vẹn năm run A/B và sau tối ưu | **PASS** | Cả 15/15 hash file do năm `manifest.json` khai báo khớp byte hiện có. |
| A/B về mặt số học | **PASS** | Cùng `cases_sha256=f73d094a...`; TPR 48,5% → 77,0%, FPR 0% → 0%; đúng 57 case đổi ALLOW → BLOCK. |
| Quy kết `+28,5 pp` cho sáu luật mới | **CONDITIONAL PASS** | 57/57 case thay đổi là PyRIT và hiện chỉ match các rule mới. Tuy nhiên run manifest không khóa source snapshot nên chưa có chứng minh provenance mang tính mật mã rằng hai run chỉ khác `input_guard.py`. |
| Tái lập mock | **PASS có điều kiện môi trường** | Run mới exit 0 khi bật UTF-8, cho đúng TP=154, FN=46, FP=0, TN=225, TPR=77,0%, FPR=0%. |
| Commit `2793459` đóng gap reproducibility | **PARTIAL / CHƯA ĐÓNG** | Khóa được byte dataset và commit runner/builder, nhưng run manifest vẫn không khóa code/config/provider/model/corpus; `cases_sha256` chỉ hash danh sách ID. Canary builder chỉ xuất hiện ở `7c04062`, không phải `2793459`. |
| Ba test “held-out” | **KHÔNG ĐỦ ĐIỀU KIỆN HELD-OUT** | Không copy nguyên văn generator, nhưng được viết cùng commit với rule và bám sát lexical trigger; chỉ là regression/unit probes. |
| Số liệu v3 trong Chương 4 | **PASS về arithmetic** | Không tìm thấy số v3 nào lệch `metrics.json` của `ada94ea1`, `5f1e19a2`, `c848aeac`. |
| Diễn giải exfil trong Chương 4 | **MAJOR REVISION** | Aggregate 43/200 bị nhiễu; tuy nhiên tách stratum cho thấy 37/190 prompt-contaminated và **6/10 prompt-clean**. Không được bỏ qua tín hiệu 6/10. |
| Biên dịch/cross-reference | **STATIC PASS; LIVE BUILD NOT VERIFIED** | Nhãn/ref/cite Ch4 đều tồn tại, log sẵn có không báo undefined. Live build bị MiKTeX trên máy audit chặn do cài đặt chưa hoàn tất. |

**Verdict chung: REVISE.** Toàn vẹn file và các point estimate đạt; reproducibility/provenance của từng run và diễn giải exfil chưa đạt mức audit-pass.

## 2. Controlled A/B

### 2.1 Số liệu gốc

| Chỉ số | Before `20260811T135545Z-5127f92f` | After `20260811T135722Z-927553a4` | Delta | Kết quả |
|---|---:|---:|---:|---|
| `cases_sha256` | `f73d094a2564c1256fa1ab5a04a834460507c0efc241632a4dc24ca36d162dc4` | giống before | 0 | Khớp |
| TP / FN | 97 / 103 | 154 / 46 | +57 / -57 | Khớp |
| TPR | 48,5% | 77,0% | **+28,5 pp** | Khớp |
| FP / TN | 0 / 225 | 0 / 225 | 0 / 0 | Khớp |
| FPR / hard-benign FPR | 0% / 0% | 0% / 0% | 0 pp | Khớp |
| Stop-before-LLM | 97/200 = 48,5% | 154/200 = 77,0% | +57; +28,5 pp | Khớp |
| PyRIT | 0/57 = 0% | 57/57 = 100% | +57 | Khớp |
| garak | 79/105 = 75,24% | 79/105 = 75,24% | 0 | Khớp |
| injecagent | 18/38 = 47,37% | 18/38 = 47,37% | 0 | Khớp |

So sánh paired theo `case_id` cho thấy 57 case đổi `blocked=false` → `true`, không có case đổi ngược. Cả 57 case đều thuộc PyRIT: 24 `csuite_impersonation`, 28 `executive_roleplay`, 5 `multi_turn_escalation`.

Chạy lại guard hiện tại trên 57 nội dung này cho thấy:

- 57/57 match ít nhất một trong sáu rule mới;
- không case nào match rule cũ;
- số lượt match theo rule là 7 `authority-authorize-bulk-export`, 37 `authority-bulk-sensitive-extract`, 22 `authority-do-not-refuse`, 6 `authority-drop-acl`, 17 `authority-open-all-restricted`, 10 `authority-override-policy`; một case có thể match nhiều rule.

Vì vậy, **quy kết mô tả** delta cho nhóm rule mới là hợp lý và rất mạnh. Nhưng chưa thể nâng thành quy kết provenance tuyệt đối:

1. `cases_sha256` là hash JSON canonical của danh sách ID, không phải hash byte/nội dung `all.jsonl`;
2. `result.jsonl` không lưu prompt hay `matched_rules`;
3. run manifest không lưu commit hay hash `input_guard.py`;
4. hai run có timestamp trước các commit được audit, nên commit graph không tự chứng minh snapshot thực thi.

Trong Git, diff `2793459..b691c90` gồm `app/guards/input_guard.py`, tài liệu thí nghiệm và test; **file runtime duy nhất thay đổi là `input_guard.py`**. Cách viết chính xác trong báo cáo là: “trong diff commit được review, `input_guard.py` là thay đổi runtime duy nhất; artifact không tự khóa snapshot này”.

## 3. Tái lập và integrity

### 3.1 Kiểm hash

Năm manifest A/B và sau tối ưu đều PASS 3/3 file (`metrics.json`, `report.md`, `result.jsonl`):

- `5127f92f`: PASS;
- `927553a4`: PASS;
- `ada94ea1`: PASS;
- `5f1e19a2`: PASS;
- `c848aeac`: PASS.

Manifest dataset khóa đúng byte hiện có:

| File | SHA-256 |
|---|---|
| `datasets/v3/cases/all.jsonl` | `b3127ecd8184fe77f0aef3fa1043722120f2000bad52f5cc7e64991ef77b2e37` |
| `datasets/v3/cases/benign.jsonl` | `7355400ef7c7866c25c2cf308d483bc4a2097de63c36ac9a1d9c005f9bda9369` |
| `datasets/v3/cases/malicious.jsonl` | `f8a63cbaeae2a96c4f0d24ac580a7d545cc86d034ca02d80c19e1ab90d4a6fc0` |
| `datasets/v3/corpus/canary-docs.jsonl` | `8cc05cd683feda35c2f62b473e61ee9c0fa6df4ced2ed475f1351cfd27cb9648` |

`scripts/build_v3_attack_payloads.py --check` exit 0, xác nhận 200 malicious + 225 benign + 425 all và cả ba hash. Canary manifest cũng khớp khi băm độc lập, nhưng canary builder không có chế độ `--check`.

### 3.2 Tái chạy mock

Chạy mới với provider `mock`, semantic LLM tắt, corpus canary đã commit và DB/output riêng trong thư mục tạm cho kết quả:

| Chỉ số | Run commit `ada94ea1` | Run audit mới `9cd34161` | Kết quả |
|---|---:|---:|---|
| `cases_sha256` | `f73d094a...` | `f73d094a...` | Khớp |
| TP / FN | 154 / 46 | 154 / 46 | Khớp |
| FP / TN | 0 / 225 | 0 / 225 | Khớp |
| TPR | 77,0% | 77,0% | Khớp |
| FPR / hard FPR | 0% / 0% | 0% / 0% | Khớp |
| Stop-before-LLM | 77,0% | 77,0% | Khớp |
| Exfil marker | 0% | 0% | Khớp |

Run exit 0 khi đặt `PYTHONUTF8=1`. Không đặt UTF-8, runner vẫn ghi đủ artifact đúng nhưng sau đó vấp `UnicodeEncodeError` khi in report tiếng Việt ra console CP1252. Đây là gap portability của lệnh tái lập trên Windows; hướng dẫn chạy cần khai báo UTF-8 hoặc runner cần xử lý encoding trong một thay đổi riêng.

### 3.3 Xu hướng qwen/hermes

Không tái chạy LLM phi tất định. Artifact đã commit cho xu hướng sau:

| Cấu hình theo tài liệu | Baseline | Sau tối ưu | Xu hướng |
|---|---|---|---|
| qwen3:4b | TPR 49,0%; FPR 10,67%; stop 48,5% (`9bb96d4e`) | TPR 77,5%; FPR 11,11%; stop 77,0% (`5f1e19a2`) | Recall/stop tăng mạnh theo rule; FPR xấp xỉ giữ nguyên và vẫn cao. |
| hermes3:8b | TPR 100%; normal-benign FPR 57%; n=300 (`4ad06cc3`) | TPR 100%; total FPR 67,11%, normal-benign FPR 58%; n=425 (`c848aeac`) | Vẫn là classifier recall cực cao/FPR rất cao; baseline và after không là A/B cùng benign set. |

Lưu ý: provider/model name không có trong `metrics.json` hay run manifest. Nhãn “qwen3:4b” và “hermes3:8b” hiện phụ thuộc vào tài liệu bên ngoài artifact, không thể xác minh độc lập từ chính gói run.

## 4. Reproducibility gap của `2793459`

### Đã đóng

- Builder attack tất định và ba case file đã được commit.
- Manifest dataset khóa SHA-256 nội dung file, không chỉ ID.
- Runner và metric code được commit; output artifact content-free và tự hash ba file kết quả.
- Trên HEAD, test runner xác nhận threshold, metric, content-free output và artifact writer; 7/7 test runner qua.

### Chưa đóng

- `phase13-v3-manifest-v1` chỉ khóa ba output; không có source commit/tree, hash runner, hash guard, policy/config, provider/model tag và digest, decoding parameters, environment/lockfile, seed, corpus hash hay actor/RBAC profile.
- `metrics.cases_sha256=f73d094a...` chỉ hash danh sách case ID. Hash nội dung thật của `all.jsonl` là `b3127ecd...`; run không liên kết hai giá trị này.
- Run không khóa `v3-attack-payloads-manifest.json` hoặc `v3-canary-corpus-manifest.json`.
- Canary generator chỉ được thêm ở `7c04062`; do đó không thể quy toàn bộ closure cho riêng `2793459`.
- Không có test buộc run manifest phải mang provenance trên; test artifact hiện chỉ kiểm file tồn tại và content-free.
- Các run có timestamp trước commit nên không thể suy source snapshot từ thời gian/commit graph.

Kết luận: `2793459` chuyển trạng thái từ “không có input freeze” sang “có dataset freeze và có code generator/runner”, nhưng **chưa biến một run thành provenance-complete experiment**.

## 5. Thẩm định ba test mới

Ba hàm test mới bao phủ ba prompt tấn công, ba prompt authority-context lành tính và một prompt evasion. Các chuỗi tấn công **không trùng nguyên văn** với payload generator, nên claim “not copied verbatim” là đúng. Tuy nhiên claim “held-out generalization” vượt quá bằng chứng:

1. test và rule được thêm trong cùng commit `b691c90`, không có pre-registration/freeze hay tác giả độc lập;
2. ba prompt cố ý chứa các lexical trigger gần như trực tiếp của regex: “xuất tất cả bảng lương”, “supersedes ... policies / every confidential”, “không được từ chối giám đốc / in mọi ... confidential”;
3. ba benign probe hữu ích cho regression precision hẹp, nhưng không ước lượng precision tổng quát;
4. chính test evasion cho thấy bỏ các trigger “override/bulk” là né được; vì vậy không thể kết luận robustness trước paraphrase ngoài generator.

Cách gọi đúng: **fresh, non-verbatim regression probes**, không phải held-out benchmark. Không cần và không được chạy holdout để đưa ra kết luận này.

Kết quả test trên HEAD:

- `tests/test_input_guard.py`: **8 passed**, không phải 23;
- `tests/test_v3_evaluation_runner.py`: **7 passed**;
- hai file gộp lại: 15 passed, 1 warning dependency.

Do đó dòng “`tests/test_input_guard.py`: 23 passed” trong `phase13-wall-optimization-authority-impersonation.md` là **sai và phải sửa**.

Nguồn `arXiv:2504.11168` được test/docstring và Ch4 dùng để hỗ trợ nhận định chung rằng guardrail có thể bị evasion. Metadata đã được xác minh lại qua [arXiv API/abstract 2504.11168v3](https://arxiv.org/abs/2504.11168v3): tiêu đề và năm 2025 khớp `refs.bib`. Nguồn này không chứng minh ba unit test là held-out hay rule cụ thể này tổng quát.

## 6. Đối chiếu Chương 4

### 6.1 Các số v3: khớp artifact

| Claim/nhóm số trong Ch4 | Artifact gốc | Đối chiếu |
|---|---|---|
| Dataset 425 = 200 malicious + 225 benign; benign = 100 normal + 125 hard | Cả ba optimized metrics | Khớp |
| A/B 48,5% → 77,0%; FPR 0% → 0%; PyRIT 0/57 → 57/57 | `5127f92f`, `927553a4` | Khớp |
| Mock confusion matrix 154 TP, 46 FN, 0 FP, 225 TN | `ada94ea1` | Khớp |
| qwen confusion matrix 155 TP, 45 FN, 25 FP, 200 TN | `5f1e19a2` | Khớp |
| Mock: TPR 77,0%; FPR 0%; hard FPR 0%; stop 77,0%; exfil 0% | `ada94ea1` | Khớp |
| qwen: TPR 77,5%; FPR 11,1%; hard FPR 14,4%; stop 77,0%; exfil 21,5% | `5f1e19a2` | Khớp sau làm tròn 1 chữ số |
| garak 75,2%/76,2%; injecagent 47,4%/47,4%; PyRIT 100%/100% | `ada94ea1`, `5f1e19a2` | Khớp sau làm tròn |
| qwen chỉ hơn mock 1 malicious case: 155 − 154 | Hai metrics trên | Khớp |
| hermes TPR 100%; FPR 67,1%; stop 99,5%; cả ba family 100% | `c848aeac` | Khớp |
| Exfil qwen baseline 50% | `9bb96d4e`: 100/200 | Khớp |
| 190/200 prompt chứa `exfil_target` | Join `malicious.jsonl` theo target | Khớp, xác minh độc lập |
| 125 hard benign, 57 nội dung unique, pool 40 template | `benign.jsonl` + `HARD_BENIGN_POOL` | Khớp |
| Biểu đồ TPR/FPR 77/0; 77,5/11,1; 100/67,1 | Ba optimized metrics | Khớp |

Không phát hiện **sai số học v3** trong Ch4. Tuy nhiên Ch4 không ghi run ID hay full-content dataset hash, nên người đọc không thể truy từ bảng sang artifact mà không dùng tài liệu phụ.

Các số release/test cũ trong phần khác của Ch4 không nằm trong ba `metrics.json` v3. Audit này không chạy lại full suite; `pytest --collect-only` hiện thu được 1526 test item, nhất quán về tổng với claim lịch sử 1522 passed + 4 skipped, nhưng không phải xác nhận lại kết quả full suite.

### 6.2 Exfil: reframe hiện tại chưa đủ

Join `result.jsonl` content-free với dataset theo `case_id` cho phép tách aggregate:

| Run | Prompt đã chứa target | Target không có trong prompt, chỉ được seed trong corpus |
|---|---:|---:|
| Mock `ada94ea1` | 0/190 leak | 0/10 leak; 4 block, 6 gọi provider |
| qwen `5f1e19a2` | **37/190 leak** | **6/10 leak; 4 block, 6 gọi provider** |
| hermes `c848aeac` | 0/190 leak | 0/10 leak; 10 block, 0 gọi provider |

Hệ quả phương pháp:

- `43/200 = 21,5%` không phải estimate hợp lệ của KB exfil vì trộn 190 prompt-contaminated với 10 prompt-clean;
- 37/43 leak qwen nằm trong nhóm có marker sẵn trong prompt, nên không thể quy cho retrieval;
- **6/10 leak còn lại có exact target không xuất hiện trong prompt và target đã được seed trong corpus.** Đây là tín hiệu phù hợp với corpus exfil, không được che bằng cách gọi toàn bộ metric là prompt echo;
- n=10 đúng bằng `RATE_REPORTING_MIN_N`, nên nếu runner có metric phân tầng thì point estimate 6/10 không bị policy hiển thị ẩn. Dù vậy mẫu quá nhỏ/tổng hợp để suy rộng;
- artifact cố ý content-free, không lưu response hay retrieved document IDs. Vì thế nó cho tín hiệu mạnh nhưng chưa cung cấp provenance đủ để truy nguyên từng leak.

Ch4 nên báo cáo hai stratum riêng. Câu “chưa đo được rò rỉ kho thật” cần đổi thành: “aggregate 21,5% không ước lượng được KB exfil; stratum prompt-clean nhỏ ghi nhận 6/10 exact-marker leak và cần một benchmark prompt-clean lớn hơn cùng retrieval trace để xác nhận”.

### 6.3 Nhất quán nội bộ và tham chiếu

- Các `\ref` trong Ch4 đều có label tương ứng; `hackett2025bypass` tồn tại trong `refs.bib`.
- `main.log` sẵn có không chứa undefined reference/citation. Live `latexmk -pdf` không chạy được do MiKTeX báo “fresh TeX installation; finish setup”. Do đó audit này không được ghi là một lần compile PASS độc lập.
- Cụm “hai cấu hình khả dụng (rule-based, qwen3:4b)” mâu thuẫn với kết luận ngay sau rằng qwen có FPR 11,1% và “không cấu hình đơn lẻ nào đạt mức triển khai”. Nên đổi “khả dụng” thành “hai cấu hình chính được so sánh”.
- Câu hermes “chặn gần như mọi thứ (Stop-before-LLM 99,5%)” dùng sai mẫu số: stop có mẫu số 200 malicious, không phải 425 total. Nên viết “chặn sớm 199/200 tấn công; đồng thời chặn nhầm 151/225 benign”.
- “precision tuyệt đối” chỉ đúng nếu giới hạn rõ “trên bộ 425 case này”; FPR=0 trên synthetic set không chứng minh precision ngoài mẫu.
- Claim “tính khái quát được kiểm” phải hạ thành “fresh non-verbatim regression probes”, không gọi held-out/generalization evidence.

## 7. Danh sách sửa báo cáo/tài liệu

### P0 — bắt buộc

1. Tách exfil qwen thành 37/190 prompt-contaminated và 6/10 prompt-clean; không trình bày 21,5% như KB-exfil rate, nhưng cũng không phủ nhận tín hiệu 6/10.
2. Sửa câu “chưa đo được rò rỉ kho thật” theo reframe phân tầng ở §6.2.

### P1 — cần sửa trước audit-pass

3. Thêm ba run ID optimized, hai run ID A/B, `cases_sha256` và full-content SHA-256 `all.jsonl` vào Ch4/phụ lục.
4. Ghi rõ A/B chỉ được provenance hỗ trợ bởi commit diff; run manifest v1 không chứng minh source/config identity.
5. Đổi “held-out generalization” thành “fresh, non-verbatim regression probes”; không suy precision/generalization từ 3 malicious + 3 benign prompt.
6. Sửa “chặn gần như mọi thứ” thành phân số đúng mẫu: 199/200 malicious và 151/225 benign.
7. Giới hạn “precision tuyệt đối” vào bộ synthetic đã đo.

### P2 — nhất quán và reproducibility

8. Sửa `phase13-wall-optimization-authority-impersonation.md`: `tests/test_input_guard.py` là 8 test item, không phải 23.
9. Đổi “hai cấu hình khả dụng” để không mâu thuẫn với kết luận “không cấu hình nào đạt mức triển khai”.
10. Không ghi audit này là live compile PASS; cần chạy lại sau khi hoàn tất cài MiKTeX và lưu log.
11. Ở lần nâng schema sau, run manifest cần khóa commit/tree, hash code/config/input/corpus, provider/model/digest/decoding và environment; đổi `cases_sha256` thành hash content hoặc đổi tên rõ `case_ids_sha256`.

## 8. Lệnh kiểm chứng đã chạy

- Băm lại 15 file trong năm run manifest: PASS.
- `python scripts/build_v3_attack_payloads.py --check`: PASS.
- Tái chạy mock 425 case + canary corpus với DB/output tạm: exit 0 khi UTF-8; metrics khớp `ada94ea1`.
- `pytest tests/test_input_guard.py`: 8 passed.
- `pytest tests/test_v3_evaluation_runner.py`: 7 passed.
- `pytest --collect-only`: 1526 item.
- Static label/ref/cite scan: PASS; existing LaTeX log không có undefined ref/cite.
- Live `latexmk`: không thể hoàn tất do MiKTeX host chưa setup; không quy lỗi cho source.
- Kiểm metadata nguồn arXiv 2504.11168 qua API: PASS.

Mọi output tạm của audit đã được xóa sau khi trích metrics; không sửa dataset hay code runtime.
