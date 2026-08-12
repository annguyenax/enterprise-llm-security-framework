# Code X — Independent artifact-integrity audit (Phase 13 P2)

Ngày audit: 2026-08-12  
Phạm vi: workspace hiện tại tại `HEAD d65f1e381a1053da753f6006ddaa9781d546b737`, hai run P2, run Hermes tham chiếu, `reports/demo-ab/`, code guard/runner, Chương 4 trong thư mục LaTeX và `baocaodot2_fixed.zip`.  
Không chạy holdout; không đọc/sửa `datasets/v2`; không báo latency; không sửa code hay dataset.

## Verdict: **REVISE**

Các số benchmark 425 case trọng yếu trong Chương 4 khớp `metrics.json` và các hash nội bộ trong manifest đều khớp file hiện có. Tuy nhiên chưa thể chấm `PASS-with-fixes` vì hai lỗi làm suy yếu trực tiếp bằng chứng chính:

1. Hai run P2 `ac64cd5c` và `49d474bc` được tạo từ **dirty worktree**, trong đó phần normalize chưa nằm trong commit được ghi ở provenance; cả hai thư mục run và Chương 4 hiện cũng chưa được Git khóa. Người ngoài không thể dựng lại đúng code đã sinh số chỉ từ `git_commit`.
2. Demo A/B đọc sai schema response của nhánh không tường: endpoint trả `response`, script không đọc trường này. Vì vậy `unguarded_canary_leak=false` trong artifact không phải phép đo leak hợp lệ. Các claim “tới 3/6”, “0/6 ở mọi lần”, “Output Guard chặn 2–3 đòn mỗi lần” không được artifact hiện có hỗ trợ và một phần trái trực tiếp với artifact.

Verdict này chỉ áp dụng cho tính toàn vẹn/tái lập của gói bằng chứng và báo cáo lab; không phải phê duyệt phase hay tuyên bố hệ thống hoàn tất.

## 1. Bảng đối chiếu claim ↔ evidence

| Claim trong Chương 4 | Evidence đã kiểm | Match | Severity |
|---|---|---:|---:|
| Rule + normalize: TPR `81.5%`, FPR `0%`, Stop-before-LLM `81.5%` | `20260812T082413Z-ac64cd5c/metrics.json`: TP/FN/FP/TN = `163/37/0/225`; stop `163/200` | Khớp | — |
| CM rule: `163/37/0/225` | Cùng artifact trên | Khớp từng ô | — |
| Rule family: garak `83.8%`, injecagent `47.4%`, pyrit `100%` | `88/105`, `18/38`, `57/57` | Khớp | — |
| Unicode `33.3% → 63.3%` | Run trước normalize có `10/30`; `ac64cd5c` có `19/30` | Khớp | — |
| Baseline `48.5%` → authority `77.0%` → normalize `81.5%`; FPR đều `0%` | `5127f92f`: `97/200`; `927553a4`/`ada94ea1`: `154/200`; `ac64cd5c`: `163/200`; cùng `0/225` FP | Khớp số | — |
| qwen: TPR `100%`, FPR `18.7%`, hard-benign FPR `20%`, Stop `81.5%` | `20260812T091223Z-49d474bc/metrics.json`: TP/FN/FP/TN `200/0/42/183`, hard FP `25/125`, stop `163/200` | Khớp | — |
| “37 case chặn sau provider; TPR 100% không phải input recall” | Cross-check `result.jsonl`: malicious `block, provider_called=false = 163`; `block, provider_called=true = 37` | Khớp ở mức **post-provider** | — |
| “Cả 37 do Output-DLP bắt canary” | `result.jsonl` không lưu `blocked_stage` hay matched rule; code path và `exfil_leaked=false` làm diễn giải này hợp lý nhưng artifact không chứng minh trực tiếp rule nào thắng | Chỉ suy luận, không truy nguyên trực tiếp | P1 |
| qwen family đều `100%` | `105/105`, `38/38`, `57/57` | Khớp metric tổng hợp; không phải input-only recall | — |
| Hermes tham chiếu TPR `100%`, FPR `67.1%`, Stop `99.5%` | `20260811T151852Z-c848aeac/metrics.json`: `200/200`, `151/225`, `199/200` | Khớp | — |
| Exfil cũ: `37/190` prompt nhiễm và `6/10` prompt sạch | Join `5f1e19a2/result.jsonl` theo `case_id` với content case v3: tái lập đúng `37/190` và `6/10` | Khớp | — |
| qwen P2 Exfil Marker `0% (n=200)` | `49d474bc`: `exfil_cases_measurable=200`, `exfil_leaks_count=0`; tất cả 200 malicious có canary tương ứng seeded | Khớp với **final answer sau Output Guard** | — |
| `0%` chứng minh hết exfil/injection | Chương 4 đã phủ định cách đọc này và nêu `37/200` tới provider | Không có oversell ở phần benchmark chính | — |
| Demo A/B là paired, “cùng retrieval + ACL, chỉ khác guards” | Guarded dùng `store.retrieve`/enterprise ACL retriever; unguarded dùng `unguarded_store.retrieve`, thuật toán đếm term và store riêng | Không phải controlled A/B chỉ khác guards | P0 |
| Demo nhánh không tường có lúc leak tới `3/6` | Artifact hiện tại ghi `0/6`, nhưng script bỏ sót trường API thực tế `response`; không có artifact của các lần được nói tới | **NOT VERIFIABLE**; detector artifact bị lỗi | P0 |
| Demo có tường leak `0/6` ở mọi lần; Output Guard chặn `2–3` đòn mỗi lần | Chỉ có một `ab_result.json`: guarded leak `0/6`, tổng block `2/6`, block post-provider `1/6`; không có lịch sử “mọi lần” | Một phần trái artifact, phần lặp lại không có bằng chứng | P0 |
| “Input Guard chặn phần lớn” trong demo | Artifact: chỉ một attack block trước provider, một block sau provider, bốn allow | Lệch | P1 |
| Input Guard tests `10 passed` | Collection hiện tại có **11** test; chạy audit: `11/11` pass | Lệch `10 → 11` | P1 |
| Output Guard `6 passed`; runner `7 passed` | Collection và chạy audit: `6/6`, `7/7` | Khớp | — |
| Full suite `1526 passed, 4 skipped` | Hiện collection có 1531 test. Audit chạy tới 70% không thấy failure nhưng bị timeout; không có log/manifest test-run đi kèm report | **NOT VERIFIABLE** trong lần audit này; con số report không khớp inventory hiện tại | P1 |
| Không có cross-reference/label gãy | `main.log` hiện có không báo citation/reference undefined | Khớp log hiện có | — |
| Bản ZIP và source Chương 4 là cùng nội dung | SHA-256 entry `chapters/chap4.tex` trong ZIP và file working tree đều `134977d2…a470` | Khớp | — |
| Bản báo cáo biên dịch lại được | `latexmk` dừng vì MiKTeX local là fresh install chưa setup xong | **NOT VERIFIABLE** trong môi trường audit; không phải lỗi LaTeX đã được chứng minh | P2 |

## 2. Toàn vẹn artifact và provenance

### Hash và định danh dữ liệu

- Manifest `ac64cd5c` khóa đúng SHA-256 của `metrics.json`, `report.md`, `result.jsonl`: 3/3 khớp.
- Manifest `49d474bc` khóa đúng ba file tương ứng: 3/3 khớp.
- Manifest Hermes `c848aeac`: 3/3 khớp.
- Tính lại từ full content của 425 case bằng đúng canonicalization của runner cho:
  - `cases_sha256 = f73d094a2564c1256fa1ab5a04a834460507c0efc241632a4dc24ca36d162dc4`;
  - `dataset_sha256 = 1da74f20f04f5f3c1d6966319539a05710b344e061be705f747332ed2c7c9af9`.
- Hash corpus hiện tại là `8cc05cd683feda35c2f62b473e61ee9c0fa6df4ced2ed475f1351cfd27cb9648`, khớp provenance qwen.
- `result.jsonl` của hai run mới là content-free theo schema công bố: chỉ có ID, label, decision, boolean và metadata nhóm; không thấy raw prompt, answer hay canary value.

### Gap còn mở

`provenance` đã tốt hơn manifest cũ vì có commit, dirty flag, provider/model, semantic switch, corpus hash và full-content dataset hash. Nhưng với hai run đang dùng trong Chương 4:

- `git_worktree_dirty=true` và commit `d65f1e3…` **không chứa thay đổi normalize** đang thấy trong diff. Không có patch hash/diff artifact để dựng lại trạng thái sinh run.
- Hai thư mục run P2, tài liệu P2 và Chương 4 đang untracked/modified; manifest chưa có một root hash được commit hoặc ký. Một người có thể thay cả file và manifest mà Git không phát hiện.
- Qwen chỉ ghi tag `qwen3:4b`, chưa ghi Ollama model digest, quantization/build, tham số sampling/seed/context, phiên bản Ollama.
- Chưa khóa Python/dependency lock hash, OS/runtime, cấu hình guard đầy đủ và hash code/config thực thi. `semantic_guard_use_llm` chỉ là một biến trong nhiều biến có thể ảnh hưởng.
- Result không ghi content-free stage/rule id cuối cùng, nên không thể phân rã input/semantic/output bằng artifact mà phải suy từ code và `provider_called`.

Kết luận provenance: **đủ truy vết dataset/corpus và nhận diện cấu hình ở mức tối thiểu; chưa đủ để người ngoài tái lập đúng run P2**.

## 3. Exfil: diễn giải được phép và không được phép

- `37/190` là marker xuất hiện ở output khi marker cũng đã có trong prompt; nó bị confound bởi prompt echo và không phải tỷ lệ rò kho thuần.
- `6/10` là stratum canary không nằm trong prompt nhưng có trong KB, nên là tín hiệu rò kho thật. Mẫu đúng ngưỡng kỹ thuật `n=10` của runner nhưng quá nhỏ để khái quát; cách gọi “under-powered” là phù hợp.
- `49d474bc` quan sát `0/200` marker trong **answer đã qua Output Guard**. Đây là bằng chứng cho exact-marker DLP trên namespace `FLAG{…}` trong bộ này, không phải bằng chứng DLP tổng quát và không phải input recall 100%.
- Output Guard hiện dùng regex marker cụ thể. Các biến đổi marker, mã hóa, phân mảnh hoặc rò dữ liệu không kèm marker chưa được số `0%` kiểm tra.
- Demo canary-sạch có thiết kế ý tưởng đúng (canary chỉ ở KB), nhưng artifact hiện tại không thể dùng để củng cố claim vì detector nhánh unguarded đọc sai response và hai nhánh không dùng cùng retrieval path.

## 4. Security-lab residuals

- **InjecAgent/hidden prose:** rule chỉ `18/38 = 47.4%`; normalize không cải thiện nhóm này. Đây vẫn là residual lớn nhất của lớp luật.
- **Evasion unit:** tám paraphrase bỏ lexical invariant được test như `ALLOW`; đây là kiểm thử ghi nhận giới hạn, không phải khả năng phòng thủ.
- **Normalize:** tăng unicode-smudging `10/30 → 19/30`; vẫn còn `11/30` lọt. Một unit test smudge pass chưa đủ chứng minh khái quát cho nhiều script, normalization collision hoặc adversarial Unicode.
- **Precision/judge:** qwen block nhầm `42/225`; hard benign `25/125`, trong đó self-service `6/32`. Việc để semantic judge opt-in/default-off phù hợp số liệu, nhưng thay đổi default hiện cũng nằm trong dirty worktree.
- **Rule FPR:** `0/225` và self-service `0/32` khớp benchmark, nhưng Chương 4 đã đúng khi không khái quát: unit probes còn ghi nhận benign ngoài phân phối bị block.
- **ACL:** code có pre-filter và ACL re-check cùng test chuyên biệt; tuy nhiên metric v3 không tách hiệu quả ACL, và demo A/B dùng retrieval implementation khác nhau. Không được dùng demo hiện tại để định lượng đóng góp ACL.
- **Output DLP:** unit tests xác nhận exact canary marker bị block. Chưa có benchmark mutation/encoding và chưa có FPR corpus riêng cho các chuỗi giống `FLAG{…}` hợp lệ.

## 5. Citation và provenance nguồn

Ba nguồn arXiv được dùng trực tiếp ở Chương 4 đã được xác minh tồn tại:

- [garak, arXiv:2406.11036](https://arxiv.org/abs/2406.11036);
- [InjecAgent, arXiv:2403.02691](https://arxiv.org/abs/2403.02691);
- [bài về bypass guardrail, arXiv:2504.11168](https://arxiv.org/abs/2504.11168).

Điểm cần sửa:

- Title trong `refs.bib` cho arXiv:2504.11168 không khớp title hiện tại trên arXiv; claim tổng quát về evasion vẫn được nguồn hỗ trợ, nhưng metadata cần chuẩn hóa.
- “Microsoft PyRIT” xuất hiện nhưng Chương 4 không có citation tương ứng. Quan trọng hơn, dataset là template tự xây “lấy cảm hứng”, không chạy tool gốc; mọi claim nguồn-family chỉ chứng minh được bằng mapping nội bộ, **không** phải kết quả benchmark chính thức của PyRIT/garak/InjecAgent.
- Claim lặp demo `3/6`, `2–3 mỗi lần`, “mọi lần” không có run IDs, manifest hay per-run artifacts: **NOT VERIFIABLE**.
- Claim full suite `1526 passed` không có test-run artifact/provenance đi kèm: **NOT VERIFIABLE** từ gói bằng chứng hiện tại.

## 6. Danh sách sửa bắt buộc

### P0 — phải sửa trước khi xin audit lại

1. Rút hoặc thay toàn bộ claim định lượng demo A/B hiện tại. Sửa phép đọc nhánh unguarded theo schema endpoint, có test chống regression cho việc phát hiện một response chứa canary, rồi tạo artifact mới. Audit này không tự thực hiện sửa đó.
2. Biến demo thành controlled experiment: hai nhánh phải nhận cùng retrieved chunks/ACL decision và cùng prompt/context; chỉ toggle guard chain. Nếu mục tiêu cố ý so “toàn hệ thống guarded” với “lab unguarded”, phải đổi nhãn và không gọi là chỉ khác guards.
3. Khóa đúng source state sinh hai run P2: clean commit hoặc lưu content-addressed patch/config snapshot; rerun từ trạng thái sạch; commit run directories, manifest và report refs. Không dùng provenance `dirty=true` làm bằng chứng tái lập cuối.

### P1 — sửa claim và tăng khả năng kiểm toán

1. Demo mỗi lần chạy cần run directory bất biến, run ID, manifest SHA-256, commit/dirty, provider, model digest, sampling config/seed, corpus hash, prompt-set hash, retrieval config và số lần lặp. Không overwrite một `ab_result.json` duy nhất.
2. Với mô hình phi tất định, định trước repetitions, randomize/counterbalance thứ tự A/B, báo numerator/denominator từng run và khoảng tin cậy; không chọn “lần đẹp nhất”.
3. Thêm trường content-free `blocked_stage` và stable `matched_rule_ids` vào result để chứng minh 37 case là Output-DLP thay vì chỉ suy từ `provider_called`.
4. Sửa bảng test: Input Guard `10 → 11`; chỉ báo full-suite sau khi có log artifact từ đúng commit/dirty state. Hiện collection là 1531 test, còn lần chạy audit full suite bị timeout ở 70% nên không được thay bằng số suy đoán.
5. Giới hạn câu chữ exfil thành “0 marker trong final returned answers đối với exact canary pattern”; giữ rõ residual `37/200` tới provider và chưa đo bypass/encoding/non-marker leakage.
6. Đánh giá ACL bằng thí nghiệm riêng có authorized/unauthorized retrieval outcomes; không suy hiệu quả ACL từ aggregate TPR/FPR hoặc demo hiện tại.

### P2 — chất lượng gói báo cáo

1. Sửa title arXiv:2504.11168 và thêm citation chính thức cho PyRIT; liên kết source mapping nội bộ cho từng family label.
2. Cung cấp environment lock/hash, phiên bản Python/Ollama và model digest; ghi rõ config mặc định và config override của từng run.
3. Lưu log biên dịch sạch hoặc CI artifact. Trong môi trường audit, `latexmk` không chạy vì MiKTeX chưa hoàn tất setup; log có sẵn không báo reference/citation undefined nhưng không thay cho clean rebuild.

## 7. Kiểm tra đã thực hiện

- Verify SHA-256 manifest: `ac64cd5c` 3/3, `49d474bc` 3/3, `c848aeac` 3/3.
- Recompute `cases_sha256`, `dataset_sha256`, corpus SHA-256: đều khớp metrics/provenance.
- Cross-reference `result.jsonl` với case content cho exfil cũ: `37/190` và `6/10`.
- Recount qwen post-provider: malicious `163` block trước provider + `37` block sau provider.
- Chạy tests trọng tâm: **24 passed** (`11` input + `6` output + `7` runner).
- Full suite: dừng do timeout ở 70%, chưa thấy failure trước thời điểm dừng; kết quả này **không** dùng để xác nhận claim full-suite.
- So ZIP/source Chương 4: SHA-256 khớp.
- Không chạy holdout hoặc thay đổi dataset/code.
