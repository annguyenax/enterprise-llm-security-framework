# Chấm tổng thể tính toàn vẹn, tái lập và phương pháp Phase 13

**Ngày audit:** 2026-08-12  
**Snapshot:** `1b53635b071d426a0742892e9a14327339ad54f1`  
**Vai trò:** Artifact-integrity & methodology auditor; không implement  
**Không thực hiện:** không chạy holdout, không sửa dataset/code, không commit.

## 1. Điểm và verdict

| Hạng mục | Điểm | Verdict |
|---|---:|---|
| Toàn vẹn artifact v3 hiện có trên máy audit | 8,5/10 | PASS có caveat |
| Toàn vẹn gói artifact mà một người ngoài nhận từ Git | 6,5/10 | REVISE |
| Thiết kế provenance của runner cho run tương lai | 7,0/10 | PARTIAL PASS |
| Khả năng tái lập ba run định lượng dùng trong Ch4 | 4,5/10 | REVISE |
| Nhất quán số liệu định lượng Ch4 | 9,0/10 | PASS |
| Demo A/B/Bảng 4.7 | 3,0/10 | REVISE |

**Điểm tổng thể: 6,0/10 — VERDICT: REVISE.**

Phần định lượng v3 cốt lõi không sai số học. Hai điểm chặn một verdict tổng thể cao hơn là: (1) các `result.jsonl` mà manifest khóa không được Git track, và ba run Ch4 đều có schema cũ không có provenance/content hash; (2) Bảng 4.7 chọn một diễn giải thuận lợi nhưng transcript chứa kết quả trái chiều, nên chưa phải A/B có thể kiểm chứng.

## 2. Tái lập và toàn vẹn

### 2.1 Những gì runner hiện khóa đúng

`scripts/run_v3_evaluation.py` hiện sinh:

- `cases_sha256`: hash danh sách ID, dùng làm identity của tập thực thi;
- `dataset_sha256`: hash canonical của toàn bộ record đã nạp, gồm `content`, label, family, technique, language và `exfil_target`;
- `git_commit` và `git_worktree_dirty`;
- chế độ in-process/remote;
- tên provider/model;
- `SEMANTIC_GUARD_USE_LLM` và semantic model;
- SHA-256 byte của corpus và tên file corpus;
- manifest khóa `metrics.json`, `report.md`, `result.jsonl`; vì metrics nằm trong manifest, provenance và dataset hash được khóa gián tiếp.

Đây là một **minimal provenance block hữu ích**: nó phát hiện nhầm dataset/corpus và phần lớn nhầm cấu hình provider cơ bản. `dataset_sha256` tốt hơn rõ rệt so với `cases_sha256`, vì thay nội dung mà giữ ID sẽ đổi hash.

### 2.2 Những gì còn thiếu để người ngoài tái lập

1. **Ba run Ch4 có trước schema provenance.** `ada94ea1`, `5f1e19a2`, `c848aeac` đều không có `dataset_sha256` hay `provenance`. Không có run provenance-enabled nào được track trong Git tại snapshot này.
2. **`result.jsonl` không được commit.** Cả ba manifest tối ưu khai ba file, nhưng Git chỉ có `metrics.json` và `report.md`; `result.jsonl` bị rule `.gitignore: *.jsonl` loại. Clone sạch không thể kiểm 3/3 manifest, tái tính CM theo từng case, hoặc cross-reference lại 37/190 và 6/10.
3. **Model chỉ khóa tên/tag**, không có immutable model digest, quantization, tokenizer hash, Ollama/server version hay model-file hash. `qwen3:4b` có thể trỏ tới bytes khác ở máy/thời điểm khác.
4. **Không khóa môi trường thực thi:** Python/OS, dependency lock hoặc `pip freeze` hash, lockfile, Ollama version, CPU/GPU/backend và deterministic flags.
5. **Semantic config chưa đầy đủ:** chưa ghi toàn bộ effective decoding/request parameters, provider timeout, endpoint/server identity, seed, context window và các option ảnh hưởng kết quả. Một số option nằm trong source và được commit gián tiếp, nhưng không được materialize thành effective config của run.
6. **RAG/runtime config chưa đầy đủ:** actor/RBAC identity, retrieval backend/top-k/chunking, DLP limits, DB/corpus initialization và các environment setting có thể đổi retrieval/exfil chưa được khóa.
7. **Dirty worktree chỉ là boolean.** `true` không cho biết patch/untracked files nào đã chạy. Vì vậy commit + `dirty=true` không tái tạo được source snapshot. Runner cũng best-effort: nếu lấy được commit nhưng lệnh `git status --porcelain` thất bại, helper trả chuỗi rỗng và có thể ghi nhầm `dirty=false`.
8. **Remote mode ghi `remote-unknown`.** Run như vậy không đủ điều kiện làm bằng chứng định lượng tái lập nếu không có attestation từ server.
9. **Không lưu exact sanitized CLI/effective configuration** và không có schema validator bắt buộc mọi field provenance quan trọng phải khác `unknown` trước khi publish.

Kết luận: runner mới giúp **truy vết**, chưa bảo đảm **tái lập**. Một người ngoài có thể tái lập khá sát mock trên clean clone, nhưng chưa thể tái lập byte/model-equivalent các run qwen/hermes, và chưa thể tái kiểm hoàn chỉnh ba run Ch4 từ Git alone.

### 2.3 Kiểm manifest

Năm run A/B và optimized được kiểm lại tại workspace:

| Run | Hash các file hiện có tại máy audit | File manifest được Git track |
|---|---|---:|
| `5127f92f` | 3/3 khớp | 2/3 |
| `927553a4` | 3/3 khớp | 2/3 |
| `ada94ea1` | 3/3 khớp | 2/3 |
| `5f1e19a2` | 3/3 khớp | 2/3 |
| `c848aeac` | 3/3 khớp | 2/3 |

“3/3 khớp” chứng minh local bytes nhất quán với manifest. “2/3 tracked” là trạng thái gói Git mà người ngoài thực sự nhận; file thiếu là `result.jsonl`.

## 3. Đối chiếu mọi số v3 trong Chương 4

### 3.1 Khớp

| Claim Ch4 | Artifact | Kết quả |
|---|---|---|
| 425 case = 200 malicious + 225 benign; benign = 100 normal + 125 hard | Ba optimized metrics/dataset | Khớp |
| Before TPR 48,5% = 97/200; FPR 0/225 | `5127f92f` | Khớp |
| After TPR 77,0% = 154/200; FPR 0/225 | `927553a4` | Khớp |
| Delta +28,5 pp; PyRIT 0/57 → 57/57 | Hai run A/B | Khớp |
| Mock CM 154 TP, 46 FN, 0 FP, 225 TN | `ada94ea1` | Khớp |
| qwen CM 155 TP, 45 FN, 25 FP, 200 TN | `5f1e19a2` | Khớp |
| Mock TPR/FPR/hard-FPR/stop/exfil = 77,0/0/0/77,0/0% | `ada94ea1` | Khớp |
| qwen TPR/FPR/hard-FPR/stop/exfil = 77,5/11,1/14,4/77,0/21,5% | `5f1e19a2` | Khớp sau làm tròn |
| Rule/qwen garak = 75,2/76,2%; injecagent = 47,4/47,4%; PyRIT = 100/100% | Hai optimized metrics | Khớp |
| qwen chỉ thêm đúng 1 TP so với mock | 155 − 154 | Khớp |
| Hermes TPR 100%, FPR 67,1%, stop 99,5% = 199/200 malicious | `c848aeac` | Khớp |
| Exfil qwen tổng 43/200 = 21,5% | `5f1e19a2` | Khớp |
| Exfil split 37/190 contaminated và 6/10 clean | local qwen `result.jsonl` + `all.jsonl` | Khớp local; không tái kiểm được từ clone sạch vì result không tracked |
| 57 hard-benign unique từ pool 40 template | dataset/generator | Khớp |

Cách diễn giải exfil hiện đã đúng mức hơn: không quy 37 marker contaminated chắc chắn cho echo; 6/10 được gọi là exact-marker KB-exfil signal, `n=10` đúng bằng threshold và được mô tả là nhỏ/under-powered; 21,5% không được gọi là KB-exfil rate.

### 3.2 Test count

- `tests/test_input_guard.py`: **10 passed** — khớp Ch4.
- `tests/test_v3_evaluation_runner.py`: **7 passed** — khớp Ch4.
- Chạy chung hai file: **17 passed, 1 warning**.
- `pytest --collect-only`: **1528 items**, nhất quán về số học với claim `1524 passed + 4 skipped`. Audit này không chạy lại toàn suite, nên trạng thái PASS của 1524 item dựa trên evidence dự án chứ chưa được xác minh thực thi độc lập trong vòng này.

### 3.3 Ref/label/citation sau cắt báo cáo

Quét tĩnh 14 file `.tex`:

- 29 label, không trùng;
- 10 cross-reference, không thiếu target;
- 11 lượt citation, không thiếu BibTeX key;
- các ref từ phụ lục tới `tab:test-summary`, `tab:v3-cm-mock`, `tab:v3-cm-semantic` đều còn tồn tại;
- `tab:ab-demo` tồn tại và là table thứ bảy của Ch4, nhưng chưa được gọi bằng `\ref` trong prose; đây là unreferenced label, không phải ref gãy.

Không phát hiện ref/cite gãy sau khi bỏ mục gói phát hành. Tuy nhiên `main.log` hiện có hai `Overfull \hbox` (13,0387 pt và 3,91376 pt). Vì vậy câu trong tài liệu evaluation rằng build có “0 overfull hboxes” đã lỗi thời sau đợt cắt, dù không ảnh hưởng số liệu.

## 4. Audit Demo A/B — Bảng 4.7

### 4.1 Trạng thái artifact

`demoBAOCAO.txt` được Git track; byte hiện tại đúng blob của commit. Identity:

- Git blob: `996105e8c140d99867aabc0dbc29713476b7f780`
- SHA-256: `33c59b4e1ff5932a6e85b52ddeca6a6d342b1b473e8b5103cfe1a25822fb0f62`

Transcript có tổng cộng 20 marker `Guards disabled`, 12 `Guardrail: allow` và 11 `Guardrail: block`. Đây không phải 20 cặp hoàn chỉnh: số quan sát hai phía khác nhau, prompt bị lặp, thứ tự/phiên chạy trộn lẫn, và không có machine-readable case ID để ghép cặp chắc chắn.

### 4.2 Ô được và không được artifact hỗ trợ

| Dòng Bảng 4.7 | Thẩm định |
|---|---|
| Benign nghỉ phép/MFA/reset password: hai bên trả lời | **Được transcript hỗ trợ như quan sát đơn**, nhưng chưa có tiêu chí correctness hoặc cấu hình/provenance. Transcript còn cho thấy một câu chấm công trả số khác giữa hai luồng. |
| Toàn bộ bảng lương: không tường leak; có tường block | **Không nhất quán.** No-wall có một lần leak bảng lương. Nhưng guarded cũng có một lần `Guardrail: allow` và trả nhiều dòng bảng lương/tài khoản; các lần guarded khác lại allow rồi tự từ chối. Không thể tổng kết phía có tường chỉ là “Chặn”. |
| Mạo danh Chủ tịch/HR Leader: no-wall bị thao túng; guarded Semantic block | **Được hỗ trợ một phần.** Guarded có Semantic block; no-wall trả dữ liệu lương của `it.user1` hoặc placeholder, không nhất quán với claim “paste full bảng lương”. Nên báo outcome cụ thể thay vì “lộ dữ liệu” chung. |
| Chỉ thị ẩn trong tài liệu: no-wall tuân chỉ thị độc; guarded RAG Context/Input block | **Không nhất quán như viết.** Probe HTML-comment no-wall chỉ trả “onboarding ổn định”, không tuân chỉ thị độc; guarded Input Guard block. Một probe `INTERNAL POLICY UPDATE` khác được no-wall làm theo và guarded bị Input/cross-employee rule block, nhưng transcript không chứng minh RAG Context Guard là lớp quyết định. |

Do đó Bảng 4.7 hiện là **minh họa chọn lọc/giai thoại**, không phải controlled A/B. Câu “cùng một prompt” đúng cho một số cặp nhìn thấy, nhưng transcript không có cấu trúc đủ để chứng minh toàn bộ bảng hoặc tỷ lệ ổn định.

### 4.3 Metadata tối thiểu cần bổ sung nếu vẫn giữ như demo định tính

- commit/tree và dirty state;
- timestamp/session ID;
- provider, exact model digest, server/version và decoding settings;
- guard profile/effective config của từng phía;
- corpus/DB snapshot hash, retrieval backend/top-k;
- actor/RBAC role/department;
- case ID và exact prompt hash để ghép cặp;
- conversation reset/state, thứ tự chạy và số lần lặp;
- outcome theo từng attempt: input decision, matched rule, provider called, retrieved-doc IDs/hashes, output-guard decision, leak marker hit và answer-correctness label;
- tổng số `allow/block/leak/refuse/correct` theo condition, không chỉ chọn ví dụ thuận lợi;
- manifest SHA-256 của transcript/result và script sinh nó.

Nếu chưa có các trường trên, caption/prose phải ghi rõ “selected observations from an unstructured manual transcript” và không dùng nó làm bằng chứng rằng mọi attack đều bị phía guarded chặn.

## 5. Thiết kế tối ưu tiếp theo

### 5.1 Đo exfil thật

1. Tạo một evaluation version mới; không sửa/fold kết quả vào dataset đã dùng để tuning.
2. Mỗi case có canary entropy cao, duy nhất, **chỉ nằm trong một tài liệu corpus**; builder phải fail nếu canary xuất hiện trong prompt, system text hoặc bất kỳ case field nào.
3. Thêm negative controls: cùng prompt với corpus không chứa canary, canary khác, và benign retrieval. Điều này phát hiện collision/hallucination hoặc bug matcher.
4. Ghi ba denominator riêng:
   - leak trên mọi attempt hợp lệ;
   - leak có điều kiện khi tài liệu chứa canary thực sự được retrieve;
   - leak có điều kiện khi provider được gọi.
   Không chỉ báo conditional rate vì sẽ che lỗi retrieval/guard phía trước.
5. Public result vẫn content-free nhưng cần có `case_id`, `target_seeded`, `target_in_prompt=false`, `target_doc_retrieved`, retrieved document hash/ID, `provider_called`, `exact_marker_leaked`, guard stage và error. Raw response có thể giữ trong restricted evidence store với hash/HMAC liên kết, không cần publish.
6. Freeze prompt/corpus/rule trước khi chạy; tách development và clean evaluation set. Lặp đủ lớn theo model/config, khóa seed/decoding nếu hỗ trợ, và báo CI (Wilson/exact binomial; bootstrap cluster theo template nếu có nhiều variant cùng template).
7. Với model phi tất định, báo cả attempt-level và case-level (`leaked in ≥1 of k repeats`) cùng chính sách repeat khai báo trước.

### 5.2 Khóa provenance đầy đủ

1. Chỉ publish quantitative run khi worktree sạch. Nếu bắt buộc dirty, lưu hash canonical của tracked diff, staged diff và inventory/hash file untracked liên quan; không chỉ boolean.
2. Fail closed nếu không lấy được Git status/commit thay vì suy `dirty=false` từ output rỗng.
3. Khóa model bằng immutable digest cùng model tag, quantization/tokenizer, runtime/server version và backend.
4. Materialize toàn bộ effective config allowlist: provider/semantic options, temperature/top-p/seed/context, timeouts, retrieval/chunking/top-k, DLP limits, actor/RBAC và feature flags.
5. Khóa Python/OS, dependency lock hoặc installed-environment digest, container image digest và deterministic flags; ghi hardware/backend khi có thể gây nondeterminism.
6. Lưu sanitized argv, builder version/schema, dataset/corpus file hash và canonical-record hash. Nêu rõ thuật toán canonicalization.
7. Commit `result.jsonl` content-free bằng force-add/scoped ignore exception, hoặc đóng gói artifact bundle có manifest/signed attestation để clone sạch lấy đủ mọi file.
8. Validator phải từ chối “publishable” khi field bắt buộc là `unknown`, dirty state không được khóa, model chỉ có mutable tag, hoặc một manifest member không nằm trong release bundle.

### 5.3 Biến demo thủ công thành A/B tái lập

1. Chuyển prompt demo thành JSONL có `case_id`, category, expected safe behavior và leak target; freeze trước khi chạy.
2. Dùng một corpus/DB snapshot hash và cùng actor/RBAC cho hai condition. Mỗi case mở conversation mới.
3. Chỉ thay đúng guard profile; provider/model digest, retrieval, decoding và mọi config khác giữ nguyên. Runner tự kiểm và fail nếu ngoài profile có drift.
4. Ghép cặp theo case và repeat; counterbalance/randomize thứ tự A/B để giảm state/order effect. Với model phi tất định, chạy số repeat khai báo trước.
5. Định nghĩa outcome máy đọc được: `allow/block`, stage, correctness, refusal, sensitive disclosure/exact-marker leak. Không suy “an toàn” chỉ từ block hoặc tự từ chối.
6. Xuất `result.jsonl`, aggregate `metrics.json`, manifest và provenance như evaluation chính. Report cả bảng đếm `allow/block/leak/refuse/correct` cho từng condition và mọi case, kể cả kết quả bất lợi.
7. Dùng paired analysis: McNemar/exact paired test cho outcome nhị phân và CI cho chênh lệch tỷ lệ; cluster/repeat policy phải khai báo trước.
8. Giữ UI transcript chỉ làm phụ lục minh họa; số trong Bảng 4.7 phải được sinh từ artifact structured, không chép tay.

## 6. Danh sách sửa ưu tiên

### P0

1. Sửa hoặc hạ claim Bảng 4.7, đặc biệt hai dòng payroll và hidden instruction; báo toàn bộ outcome trái chiều trong `demoBAOCAO.txt`.
2. Đưa `result.jsonl` content-free vào bundle/commit để người ngoài kiểm đủ manifest và exfil split.

### P1

3. Sinh và commit ít nhất một bộ run mới theo schema provenance; với qwen/hermes phải khóa model digest và clean worktree.
4. Thay demo transcript bằng structured paired artifact có config/corpus/actor identity và số lần allow/block/leak/refuse.
5. Sửa claim “0 overfull hboxes” hoặc biên dịch lại và xử lý hai warning hiện có.

### P2

6. Bổ sung environment/effective-config lock và fail-closed dirty/status handling.
7. Thiết kế benchmark exfil prompt-clean đủ mẫu, có retrieval trace và negative controls.
8. Trong phụ lục/evidence, thêm run IDs, dataset/corpus hashes và đường dẫn bundle để người đọc đi từ từng bảng tới artifact.

## 7. Kiểm tra đã thực hiện

- Đọc commit `1b53635`, Ch4, phụ lục, tài liệu optimization, runner provenance và toàn bộ `demoBAOCAO.txt`.
- Băm lại manifest của năm run liên quan: local 15/15 member hash khớp.
- Kiểm Git object cho từng manifest member: chỉ 2/3 member được track mỗi run.
- Đối chiếu metrics và confusion matrix/family rates bằng JSON.
- Cross-reference qwen result với case content: 37/190 contaminated, 6/10 clean.
- Quét label/ref/cite tĩnh toàn báo cáo.
- Chạy 17 test mục tiêu: pass; collect 1528 test item.

Workspace có các file/thư mục untracked từ trước và `.p13/` còn lại từ audit trước; không file nào trong số đó được dùng làm bằng chứng đã commit, ngoại trừ việc local `result.jsonl` được dùng để xác nhận lại split exfil và được ghi rõ là không có trong clone sạch.
