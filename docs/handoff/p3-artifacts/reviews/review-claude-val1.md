# Review chéo VAL1-RUNBOOK.md (Claude, độc lập, tác giả runbook: Codex)

- Thời điểm: 12/11/2026, Asia/Saigon
- File được review: `VAL1-RUNBOOK.md`, 637 dòng
- Checkout dùng để đối chiếu: `/workspace/shield-team/enterprise-llm-security-framework` @ `bbb78f3318c09f44847d952027e1fe895ccb5d98`, branch `feat-p3-rag-opt`, sạch
- Phạm vi: chỉ đọc. Không chạy lệnh nào trên máy An, không CopyFromBox/CopyToBox, không push/merge/commit, không sửa runbook hay framework, không mở holdout, không glob `datasets/v2`, không đọc nội dung cases/labels validation/holdout. Lệnh đã chạy trên box: `sha256sum`/`stat` các nguồn, `sed`/`grep` hai script, `git bundle list-heads` (thư mục tạm rỗng) và `git show HEAD:datasets/v2/manifests/benchmark-v2-manifest.json | sha256sum` (chỉ lấy hash của file manifest được track, không đọc artifact nào trong đó).

## Verdict: **PASS-WITH-FIXES**

Runbook đúng ở mọi điểm quan trọng: identity, hash, đường đi C: → D:, clone `--branch`, freeze model/Ollama, Judge OFF, sáu đường dẫn literal, ngưỡng, và cả hai blocker được nêu đúng kèm STOP cứng, không có đường lách. Không có lỗi hash hay lỗi chặn nào ở cấp runbook. Có 5 mục FIX nhỏ và 1 mục NEW cần Codex/coordinator sửa trước khi trình thẻ cho An. Không mục nào đòi đổi SHA, bundle hay ngưỡng.

## Issues

### P3VAL1-BLOCK-NN

**Không có.** Runbook không có lỗi chặn. Hai blocker framework (P3VAL1-BLK-01/02) là blocker của commit `bbb78f3`, không phải lỗi runbook. Runbook nêu đúng cả hai và khóa bằng thẻ 18–20 (xem phần kiểm tra bên dưới).

### P3VAL1-NEW-01: preflight chưa kiểm official manifest được track trong checkout mới, nơi runner dev-val sẽ đọc

- **Bằng chứng (bbb78f3):** `run_v2_evaluation.py:171` đặt `OFFICIAL_V2_MANIFEST_PATH = ROOT / "datasets/v2/manifests/benchmark-v2-manifest.json"`. `verify_dev_val_manifest` (1062–1079) gọi `_official_dev_val_metadata()` (1018–1028), đọc **metadata** của file này trong chính repo chạy (`D:\DoAnThucTap\shield-p3-val1\...`). Sau đó nó đòi `source_manifest_sha256` của manifest dẫn xuất phải bằng hash của file đó, và bảng 6 entry phải khớp tập con official. Hàm này không mở artifact holdout. File được git track: trên box, `git show HEAD:…/benchmark-v2-manifest.json | sha256sum` = `c91da60b…0335a`, khớp `source_manifest_sha256`. Các file JSONL bị `.gitignore` (dòng 20–28), nên clone không chứa holdout.
- **Vấn đề:** runbook ghi "không mở official `manifests\benchmark-v2-manifest.json`". Câu này đúng với repo nguồn cũ, nhưng dễ khiến người đọc hiểu là runner tương lai không chạm official manifest. Preflight cũng chưa kiểm sớm điều kiện mà runner sẽ đòi.
- **Sửa (thêm vào cuối Lệnh 05 hoặc 15, chỉ hash/Test-Path, không đọc nội dung):**
  - `Assert-Sha256 (Join-Path $Repo 'datasets\v2\manifests\benchmark-v2-manifest.json') 'c91da60b8cc5730446568f8809290171f3e139ef3613169deb41c5284050335a'`
  - Khẳng định **không tồn tại** `$Repo\datasets\v2\cases\holdout.jsonl` và `$Repo\datasets\v2\labels\holdout.jsonl` (chỉ `Test-Path -LiteralPath`, không glob).
  - Sửa câu ở mục "Nguồn dữ liệu" cho rõ: không mở official manifest **ở repo cũ**. Runner dev-val trên checkout mới sẽ đọc metadata của file được track này. Đề xuất commit sửa BLK-02 cũng phải nêu analyzer dev-val dùng cùng ràng buộc này.

### P3VAL1-FIX-01: chưa pin `OLLAMA_KEEP_ALIVE` (và `OLLAMA_BASE_URL`) ở Lệnh 09

- Provider đọc `os.getenv("OLLAMA_KEEP_ALIVE", "30m")` (`app/services/providers/ollama.py:53`). Freeze P2 ghi `keep_alive: "30m"` (FROZEN-CONFIG JSON dòng 142). Nếu biến này đã được đặt ở cấp user/system trên máy An (người dùng Ollama hay đặt), giá trị sẽ lệch freeze. Smoke ở Lệnh 16 không phát hiện được vì metadata của sink không có `keep_alive`.
- **Sửa:** thêm `$env:OLLAMA_KEEP_ALIVE = '30m'` vào Lệnh 09. Nên thêm cả `$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'`: provider đã từ chối URL khác ở chế độ evaluation (dòng 50), nhưng pin rõ thì tránh STOP mơ hồ. Lệnh 17 kiểm lại `OLLAMA_KEEP_ALIVE -ceq '30m'`.

### P3VAL1-FIX-02: điều kiện dừng về dung lượng/RAM ở Lệnh 02 chưa quyết định được

- Câu "Dừng: … thiếu dung lượng" không có ngưỡng số, nên người duyệt không biết khi nào STOP.
- **Sửa:** ghi ngưỡng cụ thể (ví dụ C: và D: free tối thiểu bao nhiêu GiB), hoặc ghi rõ "không có ngưỡng được duyệt; trình số đo cho An quyết trước Lệnh 03". Làm tương tự với RAM free thấp hơn mốc tham chiếu 6.84 GiB của P2.

### P3VAL1-FIX-03: file phụ của preflight ghi vào staging C: mà chưa kiểm trước là không tồn tại

- Lệnh 08 trỏ `LOG_PATH` và `RETRIEVAL_DB_PATH` tới `C:\Users\ADMIN\p3-val1-transfer\p3-val1-test-audit.jsonl` và `…-test-retrieval.db`, nhưng không kiểm hai file này chưa tồn tại. Nếu đã có, dữ liệu sẽ bị append hoặc tái dùng. Lệnh 07 và 16 có kiểm cho receipt của chúng, Lệnh 08 thì không. Ngoài ra, staging lúc này không còn "đúng ba file transfer".
- **Sửa:** thêm bốn đường dẫn receipt (`p3-val1-installed-packages.txt`, `p3-val1-test-audit.jsonl`, `p3-val1-test-retrieval.db`, `p3-val1-provider-preflight.json`) vào vòng kiểm "không tồn tại" ở Lệnh 01. Cách khác là gom chúng vào một thư mục receipt mới, ví dụ `D:\DoAnThucTap\p3-val1-preflight\`, được kiểm chưa tồn tại ở Lệnh 01. Ghi rõ staging sẽ chứa thêm receipt.

### P3VAL1-FIX-04: hash receipt ở Lệnh 17 không được ghi vào nhật ký

- `Get-FileHash -LiteralPath $SmokeFile, $DependencyFile` chỉ in ra màn hình.
- **Sửa:** nối `| Format-Table -AutoSize | Out-String | Tee-Object -FilePath $Log -Append`, để log preflight bind được hash receipt.

### P3VAL1-FIX-05: câu "C0 với context bật" được gán cho APPROVAL-v6

- APPROVAL-v6 và PLAN-P3-v6 (W3, dòng 172–178) chỉ ghi ngưỡng, "AOMR không thấp hơn C3 trên cùng tập val" và "cấm đạt FPR bằng cách tắt context". Hai văn bản không ghi chữ "C0". Áp ngưỡng lên C0 là cách hiểu hợp lý, nhưng là suy luận.
- **Sửa:** ghi "theo cách hiểu của điều phối, nhất quán với APPROVAL-v6", rồi nhờ An xác nhận hàng được chấm (C0) khi duyệt thẻ analyzer trên commit mới. Không đổi ngưỡng.

### Ghi nhận (không bắt sửa)

- RESCORE P2 có gỡ `origin` sau khi clone từ bundle. Runbook không gỡ. Runner chỉ kiểm branch/commit/dirty nên không ảnh hưởng. Có thể thêm `git remote remove origin` nếu muốn giống P2.
- Lệnh 07 cần mạng tới PyPI, giống P2. Runbook đã nói rõ dependency không byte-identical với P2.

## Kiểm tra đủ theo yêu cầu

| Hạng mục | Kết quả | Bằng chứng |
|---|---|---|
| run_id `P3VAL1-20261112-bbb78f3-01` | OK | Bảng đầu, Lệnh 01, smoke. Runbook ghi đúng là CLI không có `--run-id` (đã grep: 0 kết quả). Runner tự sinh ID (`_new_run_id` 4076–4077, 4214). Runbook yêu cầu đổi run_id khi có commit mới. |
| SHA đóng băng đủ 40 ký tự | OK | `bbb78f3318c09f44847d952027e1fe895ccb5d98`, khớp checkout. Parent `40e44619…07db7` khớp ghi chú điều phối. So sánh `-cne` trên chuỗi đầy đủ ở Lệnh 04, 05, 17. |
| Lần 1/3 cap val | OK | Bảng đầu, "đếm lượt chạy, không đếm FAIL", gồm W2/W3. Thẻ 19 có "sau lượt thứ 3 dừng bất kể kết quả" và "lượt lỗi vẫn vào ledger". Khớp APPROVAL-v6 dòng 16–19. |
| Bundle sha256 `866b6419…8d59d35` | OK | Đúng trên box. Size 13,226,219 khớp. `list-heads` cho đúng `bbb78f3… refs/heads/feat-p3-rag-opt`, không có HEAD ref (giải thích vì sao bắt buộc `--branch`). Derived `25ba6502…` và SHA256SUMS `1c0d6142…` cũng khớp. |
| CopyFromBox staging `C:\Users\ADMIN\p3-val1-transfer\`, không D: | OK | Bảng đường dẫn và mục transfer. Ghi rõ "CopyFromBox không ghi được D:" và là thao tác công cụ, chưa thực hiện. Khớp RESCORE P2 mục 1 (dòng 28). |
| Clone `--branch feat-p3-rag-opt` rồi kiểm HEAD | OK | Lệnh 05: `git clone --branch feat-p3-rag-opt -- $Bundle $Repo`, `rev-parse HEAD` so đủ SHA, `branch --show-current`, status rỗng, không `.env`. Không detached HEAD. |
| Checkout mới `D:\DoAnThucTap\shield-p3-val1` | OK | Lệnh 01 STOP nếu đích đã tồn tại hoặc có reparse point. `.venv` nằm trong `.gitignore` nên Lệnh 17 không báo bẩn giả. |
| Cấm ghi shield-p2-run / p2-output / enterprise-llm-security-framework | OK | Dòng 53. Thêm cả `shield-p2-analyze`. Repo cũ chỉ được hash/copy sáu file literal. |
| Model/config/Ollama 0.40.11 giống P2, không `ollama list`, không nâng | OK (xem FIX-01) | E4B digest `ee665637…`, Q4_0, backup E2B `b3704936…`. Options 0/42/4096/512/think false/repeat 1, khớp P2 preflight và ghi chú. `/api/version` và `/api/tags` qua curl. Cấm `ollama list`, `pull`, `OllamaSetup.exe`. Backup chỉ dùng khi An duyệt riêng. |
| Judge OFF | OK | `SEMANTIC_GUARD_USE_LLM=0` ở Lệnh 09, smoke kiểm, Lệnh 17 kiểm lại. Không kéo qwen3:4b. |
| Hash 6 file + derived manifest `25ba6502…`, từng đường dẫn, không glob holdout | OK (xem NEW-01) | Lệnh 13 có 6 đường dẫn tuyệt đối literal; hash và size khớp ghi chú điều phối và bảng của manifest dẫn xuất (đã đọc manifest dẫn xuất, chỉ metadata). Lệnh 14 copy theo allowlist. Lệnh 15 re-hash, kiểm inventory đúng 4 thư mục + 7 file, metadata `derived-dev-val`/`dev-val`/6/`c91da60b…`. `Get-ChildItem -Recurse` chỉ chạy trên working set mới. Layout khớp `DEV_VAL_FROZEN_PATHS` và `DEV_VAL_MANIFEST_PATH` (runner 161–170). |
| Preflight RAM / Ollama digest / git SHA / test nhanh | OK (xem FIX-02) | Lệnh 02 CIM + nvidia-smi (RTX 4050); Lệnh 10–12 version/digest/quant; Lệnh 05/17 SHA. Lệnh 08 chạy 6 test, đã đếm tham số hóa: 3+1+4+1+2+1 = **12 passed**, khớp. Lệnh 16 smoke "pong": các attribute settings và key metadata (`options`, `think`) có trên bbb78f3 (config.py 41/88/93/94; ollama.py 125–140). |
| Lệnh PowerShell đánh số, mỗi lệnh một mục đích, có expected + stop | OK | 20 thẻ, mỗi thẻ có **Mong đợi**/**Dừng**. Quy tắc chung: exit khác 0, exception hoặc stdout rỗng thì STOP, không retry. Có quy tắc khi mất phiên. Thẻ 11 chỉ dùng khi API down. |
| Chỉ mang aggregate/records val về box | OK | Mục "Đưa kết quả về box" chỉ là kế hoạch. Allowlist literal; records validation chỉ đưa khi qua scanner và schema không có text, nếu không thì chỉ aggregate. Cấm holdout, `datasets/v2`, `p2-output`, log Ollama. |
| Ngưỡng | OK (xem FIX-05) | FPR ≤ 0.15; AOMR ≥ C3 cùng val; mismatch ≤ 0.20; coverage = 1.00; error_rate ≤ 0.05; `RATE_REPORTING_MIN_N=10`; AOMR val < 0.80 thì An quyết go/no-go trước W5, không hạ 0.80. Khớp APPROVAL-v6 dòng 25–46. |
| P3VAL1-BLK-01 nêu đúng | OK | Đã xác minh `run_v2_evaluation.py:4558–4560` (`provider_not_allowed`, return 1), `2350–2351` (preflight raise `IntegrityError`), `4561–4563` (từ chối freeze ở đường không authorization). |
| P3VAL1-BLK-02 nêu đúng | OK | Đã xác minh `analyze_v2_results.py:2333–2334` (default `datasets/v2` rồi `verify_frozen_manifest`), runner `872–924` (đòi `final`, hash mọi entry, đúng 9 artifact), `REQUIRED_FROZEN_PATHS` 148–158 gồm `cases/holdout.jsonl` và `labels/holdout.jsonl`. CLI analyzer `3508–3525` không có `--benchmark-mode`/`--benchmark-root`; `3597` gọi `analyze_results(request)` không truyền root. |
| Không lách bằng `--holdout-authorization` | OK | Runbook cấm rõ ở nhiều chỗ. Code xác nhận đường này cũng không dùng được cho val: runner 4476 và 4480–4482, analyzer `_holdout_analysis_request_from_args` đều từ chối `--split` khi có `--holdout-authorization`, và từ chối dev-val/benchmark-root ở đường holdout. Thẻ 18 STOP cứng, thẻ 19–20 mở đầu bằng `throw`, lệnh thật chỉ nằm trong comment. Runbook ghi rõ duyệt lại trên cùng `bbb78f3` không mở được STOP. |
| Hash nguồn trong bảng "Nguồn và dấu vết" | OK | 13/13 SHA-256 khớp file trên box (coordinator notes, RUN-PROCEDURE, FROZEN-CONFIG md/json, setup ps1, provider py, RESCORE, PLAN-v6, APPROVAL-v6, Argon W2e 74 dòng, runner, analyzer). |

## Kết luận cho coordinator

Runbook dùng được làm nền chuẩn bị. Cần sửa NEW-01 và FIX-01…05 trước khi trình thẻ 01–17 cho An. Không cần đổi bundle, hash hay ngưỡng. Thẻ 18 vẫn là STOP bắt buộc: val không thể chạy trên `bbb78f3` cho đến khi có commit mới xử lý P3VAL1-BLK-01 và -02, commit đó được review và An duyệt lại SHA, bundle, run_id. Chưa chạy validation; lượt val Shield đã dùng vẫn là 0/3.
