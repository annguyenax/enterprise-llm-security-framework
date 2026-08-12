# Audit cuối về tính tái lập và toàn vẹn — commit `24a9683`

Ngày kiểm: 2026-08-12  
Vai trò: Code X, kiểm toán độc lập; không triển khai, không phê duyệt phase.  
Phạm vi: v3 425 case, các artifact Chương 4, A/B demo, provenance và runner. Không đọc/chạy holdout thật; không sửa dataset/code; không commit.

## Verdict

**REVISE trước khi nộp.** Các số chính 97%/0% và ba ma trận nhầm lẫn đều có artifact hợp lệ, manifest khớp, và mock tái lập chính xác từ code đã commit. Tuy nhiên báo cáo vẫn có các claim sai hoặc vượt bằng chứng: sáu FN bị mô tả là đã được ACL chặn dù artifact ghi `allow` và đã gọi provider; phần kết luận còn số injecagent 47%; A/B vẫn được gọi là content-free và các rep “độc lập”; phần mở đầu vẫn mô tả A/B như cùng retrieval. Provenance của ba run mới cũng không chứng minh dirty chỉ do artifact.

Điểm:

- Tái lập mock và toàn vẹn file: **9.0/10**.
- Provenance xuyên suốt: **6.5/10**.
- Nhất quán/bám bằng chứng của báo cáo: **6.0/10**.
- Tổng hợp: **7.2/10 — REVISE**.

## 1. Tái lập mock và toàn vẹn artifact

Chạy `scripts/run_v3_evaluation.py` ở cấu hình mock tất định từ workspace có các file code/dataset mục tiêu đúng commit `24a9683`, output ra thư mục tạm ngoài repository, cho:

| Claim | Artifact/rerun | Kết quả | Mức độ |
|---|---|---|---|
| n=425 | rerun | 425 | Khớp |
| TP/FN/FP/TN = 194/6/0/225 | rerun và `b0f8fecb/result.jsonl` | 194/6/0/225 | Khớp |
| TPR/FPR/Stop = 97.0%/0%/97.0% | rerun và `b0f8fecb/metrics.json` | 97.0%/0%/97.0% | Khớp |
| garak 94.3% | tính lại từ result | 99/105 = 94.2857% | Khớp sau làm tròn |
| injecagent 100% | tính lại từ result | 38/38 | Khớp |
| pyrit 100% | tính lại từ result | 57/57 | Khớp |
| `dataset_sha256` ổn định | rerun so với ba run commit | `1da74f20f04f5f3c1d6966319539a05710b344e061be705f747332ed2c7c9af9` | Khớp |
| `cases_sha256` ổn định | rerun so với ba run commit | `f73d094a2564c1256fa1ab5a04a834460507c0efc241632a4dc24ca36d162dc4` | Khớp |
| corpus hash | ba run commit | `8cc05cd683feda35c2f62b473e61ee9c0fa6df4ced2ed475f1351cfd27cb9648` | Khớp |

Rerun thoát mã 0 và in đường dẫn artifact tuyệt đối khi `--output` nằm ngoài repo. Như vậy lỗi runner #6 đã được sửa đúng: khối `relative_to(REPO_ROOT)` có fallback `run_dir.as_posix()` và không biến một lần ghi thành công thành exit 1.

Kiểm SHA-256 độc lập cho `metrics.json`, `report.md`, `result.jsonl` của cả `b0f8fecb`, `bfee551a`, `f946bb7b`: **9/9 file khớp manifest**. `result.jsonl` content-free theo nghĩa hẹp của runner: chỉ có ID/nhãn/quyết định/metadata, không có payload, answer hay canary value.

## 2. Đối chiếu mọi số kết quả trong Chương 4

| Claim trong báo cáo | Bằng chứng | Match | Severity |
|---|---|---|---|
| Rule `b0f8fecb`: 97.0%, FPR 0%, Stop 97.0% | metrics + tính lại result | Có | — |
| CM rule 194/6/0/225 | 425 dòng result | Có | — |
| Family rule 94.3/100/100 | 99/105, 38/38, 57/57 | Có | — |
| Qwen `bfee551a`: TPR 100%, FPR 22.2%, hard FPR 20.8%, Stop 97% | metrics | Có | — |
| CM qwen 200/0/50/175 | result | Có | — |
| Qwen tăng 194→200 sau provider | 6 malicious có `provider_called=true`, tất cả bị block | Có về thời điểm; artifact không ghi reason/stage cụ thể | P1 nếu quy chắc cho Output-DLP |
| Hermes `f946bb7b`: 100%/66.2%/99.5% | metrics; CM 200/0/149/76 | Có | — |
| Exfil marker mới 0/200 | cả ba metrics/result mới | Có | — |
| Phân tầng exfil cũ 37/190 nhiễm và 6/10 sạch | cross-ref case content với `5f1e19a2/result.jsonl` | Có, nhưng Ch4 không gắn run_id tại claim | P2 |
| Residual 6/10 `direct_kb_exfil` | sáu FN đều technique tương ứng | Có về phân loại residual | — |
| “sáu residual được ACL/RBAC chặn ở truy hồi” | sáu dòng đều `blocked=false`, `decision=allow`, `provider_called=true` | **Không** | **P0** |
| Tiến trình 48.5→77→81.5→97 và delta +28.5/+4.5/+15.5 pp | các run lịch sử đã commit và bảng tối ưu | Có; số 81.5 là mốc lịch sử, không phải số cũ sót | — |
| A/B 12/18 (3/6,4/6,5/6) vs 0/18; guarded block 9/18 | `095917Z/ab_result.json` | Có | — |
| Full suite 1531 pass, 0 fail, 4 skip, 1 warning | rerun với basetemp ngắn ngoài repo | 1531 pass, 4 skip, 1 warning | Khớp |

Không tìm thấy `18.7`, `163`, `1526` hay `1529` trong Ch4, phụ lục, mở đầu hoặc kết luận. `81.5` còn xuất hiện đúng vai trò mốc tối ưu lịch sử. Các run_id chính `b0f8fecb`, `bfee551a`, `f946bb7b`, `20260812T095917Z` trỏ đúng thư mục artifact.

Hai số/claim còn sót ngoài bảng kết quả:

1. `chapters/conclusion.tex` vẫn viết “injecagent ≈47%” và đề nghị nâng recall injecagent, trái với kết quả hiện tại 38/38 = 100%. Đây là số cũ thực sự, **P0**.
2. `chap-0.phan-mo-dau.tex` nói A/B dùng “cùng một cơ chế RAG” để tách bạch tác dụng tường. Ch4 tự xác nhận hai path dùng store/retrieval khác nhau, nên đây là oversell, **P1**.

Log LaTeX hiện có không báo undefined reference/citation hay multiply-defined label. Các nhãn bảng/figure được tham chiếu tồn tại. Đây là kiểm tra consistency của log hiện có, không phải một clean-build được provenance-lock.

## 3. A/B demo

Artifact `reports/demo-ab/20260812T095917Z` có run_id, model tag, reps=3, kết quả từng rep và manifest. Hai hash manifest đều khớp file thực:

- `ab_result.json`: `ffa51f4bccd9c0832823119ef80735b3ce2012043334d7e0f928cd8533464eea`.
- `transcript.txt`: `eab7ab46fd209f5dba951bca7fd3902c18f4871b94a68dfafe29826842a0afb5`.

Việc đổi tên từ `transcript_content_free.txt` thành `transcript.txt` là đúng, nhưng Ch4 vẫn ghi “artifact content-free”. Điều này **sai** ở cấp thư mục run: transcript chứa nguyên văn prompt tổng hợp. Chỉ `ab_result.json` là content-free theo schema hiện tại. Cần đổi claim thành “summary content-free; transcript chứa prompt synthetic và được hash”, hoặc bỏ transcript khỏi gói content-free.

Ba rep không phải ba đơn vị thử nghiệm độc lập: chúng lặp cùng sáu prompt, cùng thứ tự, cùng model/service và không có randomization/seed/model digest. Dao động 3/6→4/6→5/6 chứng minh stochastic repeat, không tạo independence. Ch4 vẫn viết `--reps` “để lặp độc lập” và mục giới hạn chưa sửa điểm này. Artifact giúp kiểm toán run đã xảy ra, nhưng chưa bảo đảm tái lập chính xác 12/18 với Ollama phi tất định.

## 4. Provenance và diễn giải dirty

Các field hiện có là hữu ích và content-free: commit, boolean dirty, provider, model tag, semantic config, corpus hash, dataset full-content hash. Chúng đủ để truy vết tối thiểu và đủ cho mock khi code sạch/được xác minh lại.

Tuy nhiên **không đồng ý** với diễn giải rằng dirty của ba run mới “chỉ do artifact untracked”:

- Ba run mới ghi `git_commit=77be92d...`, `git_worktree_dirty=true`.
- Diff `77be92d..24a9683` chứa chính `app/guards/input_guard.py`; thay đổi này là điều tạo kết quả 97% và chỉ được commit trong `24a9683`.
- Vì vậy tại thời điểm chạy, code hiệu lực không thể được khôi phục chỉ từ commit ghi trong provenance. Boolean dirty không chứa patch hoặc danh sách file, nên không thể chứng minh dirty chỉ là output.

Rerun tại `24a9683` tái lập chính xác giúp xác nhận số mock và giảm rủi ro sửa số, nhưng không biến provenance lịch sử thành clean-run. Cách trình bày trung thực: “các run gốc dùng dirty worktree tại parent commit; deterministic mock được tái lập từ commit `24a9683` với cùng dataset hash và số liệu”. Nếu cần bằng chứng clean provenance, phải tạo run từ clean worktree và commit artifact ở commit kế tiếp; không được gọi run đó là cùng commit chứa artifact.

Gap còn lại đã được Ch4 nêu đúng một phần: chưa lock dependency/environment và chưa pin model digest. Còn nên nêu thêm:

- Python/OS/architecture và lockfile hash;
- Ollama version, model immutable digest/quantization/template;
- effective config đầy đủ thay vì vài env field;
- seed/temperature/sampling và provider build;
- dirty file list hoặc patch hash; tốt nhất từ chối publish run định lượng khi source/config dirty;
- runner/script hash nếu commit không clean; DB/schema/migration identity.

## 5. Exfil và giới hạn diễn giải

Phân tầng cũ tái lập được từ clone có result và dataset v3: trong run `5f1e19a2`, 37/190 case có canary nằm sẵn trong prompt bị đánh dấu leak, còn 6/10 case prompt sạch bị leak. Vì vậy “prompt-canary confounded” và “6/10 là tín hiệu rò kho thật nhưng dưới công suất” là cách diễn giải đúng.

Các run DLP mới có 0/200 marker returned. Điều đó chỉ chứng minh canary không xuất hiện trong answer cuối; không chứng minh input attack đã bị phát hiện hoặc kho không bị truy cập. Chính sáu case qwen đã tới provider. `result.jsonl` không lưu reason code/stage của block, nên quy toàn bộ sáu block sau provider cho Output-DLP là suy luận từ kiến trúc, chưa phải claim được artifact độc lập chứng minh.

Nghiêm trọng hơn, sáu FN rule không được ACL chặn theo chính outcome của runner. Nếu ACL thật sự bảo vệ tài liệu ở tầng khác, cần một thí nghiệm/field riêng (`retrieval_denied`, authorized chunks, canary-in-store) thay vì đổi nghĩa FN thành “đã chặn”.

## 6. Kiểm thử và tham chiếu

Lần chạy full suite đầu với một basetemp dài ngoài repo cho `1506 passed, 4 skipped, 17 failed, 8 errors`; traceback đều là `FileNotFoundError` ở đường dẫn fixture holdout tổng hợp rất dài trên Windows. Lần thứ hai đặt basetemp trong repo bị policy output-containment từ chối, đúng theo thiết kế. Đây không phải chạy holdout thật và không phải bằng chứng lỗi guard.

Rerun cuối với basetemp ngắn **ngoài repo** hoàn tất: **1531 passed, 4 skipped, 1 warning, 0 failed** trong 222.61 giây. Claim Ch4 và phụ lục khớp. Warning là `StarletteDeprecationWarning` của `fastapi.testclient`; Ch4 không nêu warning còn phụ lục nêu 1 warning, không tạo mâu thuẫn về pass/fail. Điều kiện đường dẫn nên được ghi trong lệnh tái lập vì nó có ảnh hưởng thực tế trên Windows.

## Danh sách sửa bắt buộc

### P0

1. Xóa/đổi mọi câu “6/10 residual do ACL chặn”: artifact coi chúng là FN, allow, gọi provider. Nếu có bằng chứng ACL khác, dẫn đúng artifact riêng.
2. Sửa kết luận “injecagent ≈47%” và hướng phát triển tương ứng; hiện tại benchmark family là 100%, đồng thời giữ hạn chế template/evasion ngoài phân phối.
3. Không diễn giải dirty của `b0f8fecb/bfee551a/f946bb7b` là chỉ do artifact. Ghi rõ code thay đổi chưa commit tại `77be92d`, và dẫn rerun `24a9683` như bằng chứng tái lập độc lập.

### P1

1. Đổi “artifact A/B content-free” thành mô tả chính xác theo file; transcript có prompt thô synthetic.
2. Đổi “reps độc lập” thành “stochastic repeated trials trên cùng prompt/order”, bổ sung hạn chế không độc lập và không pin seed/digest.
3. Sửa phần mở đầu: A/B hiện là so sánh hai system path khác retrieval/store, không phải guard-only ablation trên cùng RAG/chunks.
4. Với claim sáu qwen block do Output-DLP, bổ sung reason/stage artifact hoặc hạ câu thành suy luận kiến trúc.
5. Giữ được số full-suite đã tái lập; bổ sung command/OS/path condition tối thiểu để người ngoài tránh lỗi Windows/path-containment.

### P2

1. Gắn run `5f1e19a2` ngay cạnh claim 37/190 và 6/10 pre-DLP.
2. Ghi model digest, Ollama/Python/dependency lock, sampling/effective-config hash ở run tương lai.
3. Với A/B tương lai: randomize/counterbalance order, tách instance/session, pin model digest và sampling, tăng số prompt độc lập, định nghĩa đơn vị phân tích và CI trước khi chạy.

## Kết luận kiểm toán

Không có dấu hiệu bịa các số neo mới: 97.0%/0%, 194/6/0/225, family 94.3/100/100, qwen 100%/22.2%, hermes 100%/66.2% và A/B 12/18 vs 0/18 đều truy được tới artifact đã hash. Blocker còn lại nằm ở **diễn giải vượt outcome, provenance dirty không đủ khóa, và số cũ/claim A/B chưa được dọn hết**. Do đó chưa đủ điều kiện chấm PASS cuối trước nộp.
