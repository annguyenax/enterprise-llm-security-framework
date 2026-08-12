# Code X — Verify reproducibility and artifact integrity at `91e6956`

Ngày kiểm: 2026-08-12  
Commit kiểm: `91e6956b21b4fb0671d0b799b8a50f5388efb4e4`  
Phạm vi: v3 mock reproduction, committed v3 artifacts, clean-canary system-level A/B, Chương 4 và phụ lục. Không chạy holdout; không sửa code/dataset; không commit.

## Verdict: **PASS-with-fixes**

Verdict này chỉ dành cho gói bằng chứng được kiểm, **không phải phase PASS**. Lỗi schema A/B chặn kết luận ở vòng trước đã được sửa và số benchmark chính tái lập/đối chiếu được. Các fix còn lại là lỗi claim/provenance mức P1–P2, không làm đổi các tử số/mẫu số đã ghi trong artifact.

## Điểm tái lập cập nhật: **8.0/10**

| Thành phần | Điểm | Lý do |
|---|---:|---|
| Mock v3 tất định | 9.5/10 | Chạy lại đủ 425 case từ source/data byte-equal `91e6956`, tái lập đúng CM và full-content dataset hash. Trừ điểm vì CLI không kết thúc sạch khi `--output` nằm ngoài repo. |
| Toàn vẹn v3 artifact | 9.0/10 | 16 `result.jsonl` đã tracked; mọi file được manifest khai báo đều hiện diện và khớp SHA-256. |
| A/B demo | 6.5/10 | Schema detector đã đúng, run có ID/reps/manifest và số tự cộng khớp; nhưng model/environment chưa khóa, provenance là dirty source, transcript không content-free, hai retrieval path khác nhau và reps không phải independent experimental units theo nghĩa thống kê. |
| Báo cáo | 7.0/10 | Số Chương 4 khớp; phụ lục và tài liệu phương pháp còn test-count cũ, claim content-free/independent cần hạ mức. |

## 1. Khớp/lệch từng số và claim

| Claim | Evidence kiểm trực tiếp | Kết quả | Severity |
|---|---|---:|---:|
| Mock 425: TPR `81.5%`, FPR `0%`, TP `163` | Rerun tại `91e6956`: TP/FN/FP/TN `163/37/0/225`, TPR `0.815`, FPR `0.0`, errors `0` | **Khớp** | — |
| Stop-before-LLM mock `81.5%` | Rerun: `163/200` | **Khớp** | — |
| `dataset_sha256` ổn định | Rerun: `1da74f20f04f5f3c1d6966319539a05710b344e061be705f747332ed2c7c9af9`; bằng `ac64cd5c`, `49d474bc` và clean-commit reproduction trước | **Khớp** | — |
| `cases_sha256` | Rerun: `f73d094a2564c1256fa1ab5a04a834460507c0efc241632a4dc24ca36d162dc4` | **Khớp** | — |
| Chương 4 rule run `ac64cd5c`: TPR/FPR `81.5%/0%`, CM `163/37/0/225` | Committed `metrics.json` của `20260812T082413Z-ac64cd5c` | **Khớp** | — |
| Chương 4 qwen run `49d474bc`: `100%/18.7%`, CM `200/0/42/183`, Stop `81.5%` | Committed `metrics.json` của `20260812T091223Z-49d474bc` | **Khớp** | — |
| Qwen `37/200` tới provider, không phải input recall 100% | Committed result: 163 malicious block với `provider_called=false`, 37 block với `provider_called=true` | **Khớp** | — |
| A/B run ID `20260812T095917Z`, reps `3`, attack trials `18` | Committed `ab_result.json` | **Khớp** | — |
| A/B unguarded `12/18`, theo rep `3/6`, `4/6`, `5/6` | Recount 18 attack rows trong artifact | **Khớp** | — |
| A/B guarded leak `0/18`, blocked `9/18` | Recount artifact: 0 leak, 9 decision block/human-review | **Khớp** | — |
| A/B đọc đúng field `response` | `_extract_unguarded_answer()` ưu tiên `response`; regression test chạy `2 passed` | **Khớp; lỗi vòng trước đã đóng** | — |
| A/B artifact “content-free” | `ab_result.json` không chứa raw answer/prompt/canary value; nhưng `transcript_content_free.txt` chứa nguyên văn 21 prompt | **Lệch đối với toàn run directory** | P1 |
| A/B là thí nghiệm “cấp hệ thống”, không phải same-retrieval guard ablation | Script/report ghi rõ guarded dùng workspace retrieve/ACL, unguarded dùng `unguarded_store` | **Khớp và không còn oversell cũ** | — |
| `--reps` là “lặp độc lập” | Ba rep dùng cùng sáu prompt, cùng thứ tự, cùng model service; không có seed/randomization/counterbalancing | **Claim quá mạnh**; đây là repeated stochastic trials | P1 |
| Chương 4 full-suite inventory `1533 collected`, không claim passed | `pytest --collect-only`: `1533 tests collected` | **Khớp và trung thực** | — |
| Chương 4 focused counts `11/6/7/2` | Input/output/runner collection `11/6/7`; A/B schema test `2 passed` | **Khớp** | — |
| Phụ lục nhất quán với Chương 4 | Phụ lục vẫn ghi `1526 passed, 0 failed, 4 skipped, 1 warning` | **Lệch; claim passed không có artifact mới** | P1 |
| Tài liệu authority-impersonation nhất quán test count mới | Dòng 159–166 vẫn ghi `10 passed` và full suite `1524 passed` | **Lệch/stale** | P2 |
| Cross-reference Ch4/phụ lục | Các label được tham chiếu đều có định nghĩa; log hiện có không báo undefined reference/citation | **Khớp theo log hiện có** | — |

## 2. Tái lập mock từ `91e6956`

Trước khi chạy, `git diff 91e6956 -- app scripts datasets/v3` không có output: source và v3 data dùng trong phép chạy byte-equal commit. Cấu hình được đặt tường minh:

```text
LLM_PROVIDER=mock
LLM_MODEL_NAME=mock-rag-guard-v1
SEMANTIC_GUARD_USE_LLM=0
```

Kết quả thực đo:

```text
total=425; malicious=200; benign=225; errors=0
TP=163; FN=37; FP=0; TN=225
TPR=0.815; FPR=0.0; Stop-before-LLM=0.815
dataset_sha256=1da74f20f04f5f3c1d6966319539a05710b344e061be705f747332ed2c7c9af9
git_commit=91e6956b21b4fb0671d0b799b8a50f5388efb4e4
```

Artifact và manifest đã được ghi đầy đủ. Khi output được đặt ngoài repository để không tạo file audit trong workspace, runner sau đó trả exit 1 ở câu in `run_dir.relative_to(REPO_ROOT)`. Nếu không đặt `PYTHONUTF8=1`, console Windows cp1252 còn có thể lỗi khi in báo cáo tiếng Việt. Hai lỗi xảy ra **sau khi** artifact hoàn chỉnh được ghi và không đổi metric, nhưng cho thấy lệnh CLI chưa portable cho output ngoài repo/môi trường console chưa khóa.

### Diễn giải `git_worktree_dirty=true`

Tôi **đồng ý có điều kiện**, không đồng ý nếu chỉ dựa vào boolean trong metrics:

- Clean-commit reproduction chứng minh số mock có thể sinh từ code đã commit, nên số `81.5%` không còn phụ thuộc vào normalize chưa commit.
- Ở lần audit này, source/data liên quan không có diff so với `91e6956`; dirty state đến từ artifact/unrelated working-tree state, nên về mặt nhân quả không ảnh hưởng metric.
- Nhưng `_git_provenance()` chỉ ghi `bool(git status --porcelain)`. Nó không phân biệt source/config modified, tracked artifact deleted hay untracked output. Workspace hiện tại thậm chí có nhiều **tracked deletions** dưới `reports/v3/_eval-documents`, nên câu “dirty chỉ do untracked artifact” là quá tuyệt đối.
- Artifact clean-reproduction `7e259bd` không lưu snapshot/digest danh sách dirty paths. Do đó nguyên nhân lịch sử của cờ dirty không thể được chứng minh từ metrics một mình.

Cách khóa đúng: ghi riêng `tracked_source_dirty`, `tracked_non_source_dirty`, `untracked_dirty`, cùng hash của patch/source tree hoặc danh sách path đã chuẩn hóa; tốt nhất chạy từ clean worktree và ghi artifact ngoài worktree bằng code không giả định output nằm dưới repo.

## 3. A/B schema fix và mức tái lập

### Đã đạt

- Detector đọc đúng API field `response`; hai regression tests pass.
- Run directory, `run_id`, `reps`, numerator/denominator từng rep và aggregate đều có.
- Manifest khóa `ab_result.json` và transcript; hash và byte count đều khớp 2/2.
- Run directory và manifest đã được Git track tại `91e6956`.
- `ab_result.json` là content-free theo nghĩa không lưu raw prompt, raw answer hoặc giá trị canary cụ thể.
- Báo cáo đã reframe đúng thành **system-level comparison** với hai retrieval implementation khác nhau; không dùng nó để suy riêng hiệu quả ACL/BM25 hay Output Guard.

### Chưa đạt tái lập đầy đủ

- Provenance của chính run `095917Z` ghi commit `d65f1e3…`, `git_worktree_dirty=true`. Schema fix lúc chạy là code chưa commit; commit sau này lưu artifact/script nhưng không cung cấp patch hash của source state thực thi.
- Chỉ ghi tag `qwen3:4b`, chưa có Ollama model digest/quantization, Ollama version, generation options, seed hay environment lock.
- Ba rep là các lần gọi lặp trên cùng prompt set và thứ tự; không phải ba mẫu độc lập. `12/18` chỉ nên là mô tả artifact, không dùng CI hay suy rộng tỷ lệ quần thể.
- `transcript_content_free.txt` chứa raw synthetic prompts. Nó không chứa raw answers/canary value, nhưng tên file và claim “artifact content-free” vẫn sai.
- Timestamp đến cấp giây là run ID hữu ích, nhưng không phải identity nội dung; identity thực nằm ở committed manifest/hash.

Kết luận: **workflow A/B hiện tái chạy được và artifact hiện tại kiểm tra integrity được; exact numerical reproduction của `12/18` chưa được bảo đảm** vì mô hình phi tất định và provenance model/environment/source chưa khóa.

## 4. `result.jsonl` và split exfil từ clone sạch

- `git ls-files` xác nhận **16** `reports/v3/*/result.jsonl` đã commit, nhiều hơn ngưỡng “14+”.
- Kiểm toàn bộ tracked run: không thiếu manifest/file và không có SHA-256 mismatch.
- `5f1e19a2/result.jsonl` và `datasets/v3/cases/all.jsonl` byte-equal tree `91e6956`.
- Join theo `case_id`, phân tầng bằng việc `exfil_target` có/không có trong case content, tái lập:

```text
prompt-canary contaminated: 37 leaks / 190 cases
clean prompt:               6 leaks / 10 cases
```

Vì cả result và case content đều tracked, người nhận clone sạch có thể kiểm lại split. `6/10` vẫn under-powered và không được suy rộng.

## 5. Fix còn lại

### P1

1. Sửa Chương 4: thay “artifact content-free” bằng mô tả chính xác rằng JSON là content-free còn transcript chứa synthetic prompts; hoặc không phát hành transcript trong evidence package content-free.
2. Sửa phụ lục dòng full suite: đồng bộ thành `1533 collected` và không claim passed nếu không có full-run artifact đúng commit.
3. Đổi “lặp độc lập” thành “ba repetition/call lặp”; giữ `12/18` là thống kê mô tả. Nếu cần ước lượng, định trước sampling/seed/order và experimental unit.
4. Với demo phát hành tiếp theo, chạy từ clean commit và ghi model digest, full generation config, environment/lock hash, corpus/prompt-set hash.

### P2

1. Cập nhật test count cũ `10`/`1524 passed` trong tài liệu authority-impersonation.
2. Tách dirty provenance theo loại và lưu source/patch digest thay vì một boolean.
3. Làm runner hỗ trợ absolute output path và UTF-8 console cleanly để audit có thể ghi artifact ngoài repo mà vẫn exit 0.

## Kết luận

Ba mục cốt lõi đã được xác nhận: mock `81.5%/0%/TP163` tái lập từ committed code; A/B schema fix cho ra artifact tự nhất quán `12/18`; và split exfil `37/190` + `6/10` kiểm được từ clone sạch. Chưa nên gọi provenance “đầy đủ”: model digest, environment lock, exact dirty-source identity và ngôn ngữ thống kê của demo vẫn cần chỉnh.
