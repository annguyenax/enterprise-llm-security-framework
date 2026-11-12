# Nhật ký quyết định — Phase 3 RAG opt

Mọi mốc dưới đây ghi theo giờ của An, Asia/Saigon (UTC+7). Câu của An để nguyên văn.

## 08:52, 12/11/2026, Asia/Saigon

- Nguồn: widget `t100s502`
- Nguyên văn: "Duyệt ngưỡng như plan bản 6, cho đội bắt đầu làm"
- Phạm vi: duyệt ngưỡng PLAN-P3-v6 (sha256 `45b5530264b4acd13d5792439f3514ac97cc74f8fb86321ade54534d12ce2c0e`). Biên bản: `APPROVAL-v6.md`.

## 10:15, 12/11/2026, Asia/Saigon

- Nguồn: An trả lời sau báo cáo W2b (`db791b4`, FPR dev C0 MOCK 1/12, AOMR 8/14)
- Nguyên văn: "Chưa chạy val, cho đội cải thiện tỷ lệ chặn đúng trên dev trước"
- Ý nghĩa cho đội: không chạy val (không tiêu một trong 3 lượt). Tiếp W2c trên dev: cải thiện AOMR/chặn đúng, giữ FPR C0 không tăng, không đụng holdout, không push. Ghi nhận lúc vào log: 10:16, 12/11/2026, Asia/Saigon.

## 10:36, 12/11/2026, Asia/Saigon

- Nguồn: An trả lời câu hỏi chọn hướng (các lựa chọn: luật chặn khi tài liệu độc bị chặn / nới giới hạn 12 từ truy xuất / chạy val), widget `t102u`
- Nguyên văn: "thử cach nào tối ưu là đc"
- Ý nghĩa cho đội: thử hướng nào tối ưu được thì làm. **Vẫn không chạy val**, không đụng holdout, không push. W2d thí nghiệm H1 (luật chặn khi chunk độc liên quan trực tiếp bị BLOCK), H2 (nới/chọn term truy xuất thay vì cắt 12 từ đầu), và H1+H2. Chỉ giữ biến thể nếu AOMR C0 dev tăng và FPR C0 ≤ 1/12. Ghi nhận lúc vào log: 10:36, 12/11/2026, Asia/Saigon.

## 11:05, 12/11/2026, Asia/Saigon

- Argon review W2d: **PASS**. File: `review-argon-W2d.txt` (71 dòng), commit `40e4461`.
- Trong lúc chạy, Argon gọi một số lệnh test bị exit code 4 và 1, nên **không dùng test của Argon làm bằng chứng**. Bằng chứng test cho W2d là bộ của coordinator: 207 related + 79 W13 passed.

## 11:09, 12/11/2026, Asia/Saigon

- Nguồn: An trả lời widget `t102s541`
- Nguyên văn: "Cho đội cải thiện tiếp tỷ lệ chặn đúng trên dev"
- Ý nghĩa cho đội: tiếp tục cải thiện AOMR/chặn đúng trên dev (W2e). **Vẫn không chạy val**, không đụng holdout, không push. Ghi nhận lúc vào log: 11:10, 12/11/2026, Asia/Saigon.

## 11:40, 12/11/2026, Asia/Saigon

- Argon review W2e: **PASS**. File: `review-argon-W2e.txt` (74 dòng), commit `bbb78f3`.
- Trong lúc review, không có lệnh test nào của Argon exit khác 0.

## 11:41, 12/11/2026, Asia/Saigon

- Nguồn: An trả lời widget `t102s548`
- Nguyên văn: "Đồng ý, chuẩn bị chạy val lần 1 trên máy anh với Ollama thật, anh duyệt từng lệnh"
- Ý nghĩa cho đội: chỉ **chuẩn bị** val lần 1 (1/3 trong cap). Chưa chạy gì trên máy An. Coordinator sẽ tự chạy từng lệnh trên máy An, An duyệt từng lệnh qua card. Dùng Ollama thật, tái dụng runbook/preflight P2. Ghi nhận lúc vào log: 11:42, 12/11/2026, Asia/Saigon.

## 12:41, 12/11/2026, Asia/Saigon

- Argon review W14: **PASS**. File: `review-argon-W14.txt` (28 dòng), commit `796ae25`. Không issue. Có 1 lệnh dò venv exit 1, **không phải test**, không dùng làm bằng chứng test.

## 12:41, 12/11/2026, Asia/Saigon

- Nguồn: An trả lời widget `t102s555`
- Nguyên văn: "Duyệt chạy val lần 1: commit 796ae25, run_id P3VAL1-20261112-796ae25-01, chấm theo C0, ledger và thư mục mới trên D: như em nêu, chỉ chạy khi Argon PASS, anh duyệt từng lệnh"
- Ý nghĩa cho đội: An duyệt thực thi VAL1 trên máy anh với SHA `796ae25f9779cba30c9be60f35af3e67a74d0450`, run_id `P3VAL1-20261112-796ae25-01`, chấm hàng C0, dùng ledger và thư mục mới trên D: như runbook. Chỉ chạy khi Argon đã PASS (đã PASS 12:41). An duyệt từng lệnh qua card. Thẻ 18–20 được mở khóa bởi duyệt SHA này. Ghi nhận lúc vào log: 12:42, 12/11/2026, Asia/Saigon.

## 12:50, 12/11/2026, Asia/Saigon

- Nguồn: coordinator sau khi thẻ 17 FAIL trên máy An; xác nhận thẻ 08 chỉ chạy 6 test fixture tạm, không ghi `RETRIEVAL_DB_PATH`.
- Sự cố: lần chạy VAL1 dừng ở thẻ 17 vì `Get-FileHash` đòi `D:\DoAnThucTap\p3-val1-preflight\p3-val1-test-retrieval.db`, file không tồn tại. Đây là lỗi runbook, không phải lỗi máy. Việc test không ghi ra đường dẫn thật là dấu hiệu tốt.
- Sửa: thẻ 17 trong `VAL1-RUNBOOK.md` — nếu db không tồn tại thì ghi vào receipt đúng chữ `test_retrieval_db: absent (fixture-only tests)`; nếu db tồn tại thì hash; giữ nguyên mọi kiểm tra khác. Không tự tạo file db. SHA-256 runbook cũ `63979dc741e8c5ce4d3a691788d32f5d42a5caaf1e93c650246c1e73b0907111`; SHA-256 runbook mới `c0f48830d6f80e548acad08f63be044a8887d3ca5bc6bf0ec37dd9aca2e409a7`.
- Lệch lúc thực thi thẻ 01–05 (ghi nhận, không sửa cây máy): (1) thẻ 01 tạo sớm thư mục `D:\DoAnThucTap\p3-val1-preflight` và ghi log `p3-val1-preflight\p3-val1-preflight.log` thay vì chỉ tạo `D:\DoAnThucTap\p3-val1-preflight-log.txt`; log chuẩn được ghi từ bước đo `nvidia-smi`. (2) clone checkout (nội dung thẻ 05) chạy trước `git bundle list-heads` (thẻ 04); sau đó list-heads và kiểm identity/hash official manifest/không holdout đều khớp SHA `796ae25f9779cba30c9be60f35af3e67a74d0450`, không clone lại. (3) thẻ 16 lần gọi đầu typo `-or` (parse error, không tạo smoke receipt); chạy lại đúng runbook thì PASS, `elapsed_ms=10781`.
- Ledger và freeze lúc ghi log này vẫn chưa tạo. Chưa tiêu thụ lượt val. Chờ Claude review nhanh riêng diff thẻ 17 (PASS mới chạy lại thẻ 17).

## 12:51, 12/11/2026, Asia/Saigon

- Claude review nhanh, 1 lượt, chỉ diff thẻ 17 của `VAL1-RUNBOOK.md` (sha256 `c0f48830d6f80e548acad08f63be044a8887d3ca5bc6bf0ec37dd9aca2e409a7`): **PASS**. File: `review-claude-val1-card17.md`. Không issue bắt phải sửa. tokrun `review-claude-val1-card17`; stderr served by claude-sonnet-5-5 (fallback from claude-opus-5-5). Được phép chạy lại thẻ 17 trên máy An.

## 12:52, 12/11/2026, Asia/Saigon

- Thẻ 17 chạy lại sau Claude PASS: **OK**. Receipt ghi `test_retrieval_db: absent (fixture-only tests)`. Ledger rỗng mới tại `D:\DoAnThucTap\p3-val1-ledger.jsonl`. Freeze lúc đó chưa có.
- Thẻ 18 (đã mở khóa, không chạy lệnh throw): tạo freeze từ settings/receipt thật, `D:\DoAnThucTap\p3-val1-preflight\p3-val1-frozen-config.json`, SHA-256 `13ec75fdbc93bd5032cc83d2e68a5c29566ce6dcac53d0532356d91464b31058`.
- Thẻ 19 chạy **một lần**, bắt đầu 12:52:23, FAIL 12:52:24 (exit 1). STDERR: `FAIL [validation_claim]: validation receipt/ledger is unavailable or malformed`. Claim đã ghi trước inference: attempt **1/3**, `started_at_utc` 2026-11-12T05:52:24Z, campaign `P3VAL1-20261112-796ae25-01`. Output chỉ có `dev-val-start-receipt.json`. Không rerun, không sửa ledger, không chạy thẻ 20.
- Nguyên nhân quan sát (không tự sửa): ledger 1860 byte, dòng kết thúc CRLF; receipt 1859 byte, chỉ LF (canonical). `read_claims` đòi `canonical(record) == line` nên reject. Artifact và ledger giữ nguyên.

## 13:00, 12/11/2026, Asia/Saigon

- Nguồn: An trả lời widget `t102s563`
- Nguyên văn: "Lượt val 1 hỏng trước khi chạy câu nào thì không tính vào cap, vẫn còn 3 lượt, ghi rõ trong log"
- Ý nghĩa cho đội: lượt `P3VAL1-20261112-796ae25-01` được xếp là lượt hỏng vì lỗi môi trường (ledger ghi CRLF, fail trước inference, không chạy câu val nào, không xem metric). **Không tính vào cap.** Cap Shield vẫn còn **3/3**. Ledger cũ `D:\DoAnThucTap\p3-val1-ledger.jsonl` giữ nguyên làm bằng chứng, không auto-repair, không tái dùng làm ledger chạy. Runbook và ledger mới của P3VAL2 phải ghi rõ lượt sắp chạy là **lượt 1/3 hợp lệ**, và ghi chú tham chiếu sang lượt hỏng P3VAL1. Ghi nhận lúc vào log: 13:00, 12/11/2026, Asia/Saigon.

## 13:06, 12/11/2026, Asia/Saigon

- W15 đóng băng trên `feat-p3-rag-opt`: commit `e604aed6cec9d8a348baaacfb3341356b2697614`, parent `796ae25f9779cba30c9be60f35af3e67a74d0450`. Không push. Chưa chạy gì trên máy An cho P3VAL2.
- Codex implement, Claude review chéo **PASS-WITH-FIXES** (FIX-01 = thẻ self-check runbook, không đổi code; FIX-02 chỉ tài liệu audit log). Muse **PASS**. Prompt Argon W15 đã soạn, chưa dispatch.
- Coordinator test: **657 passed** (7 W15 + hồi quy), `python -m scripts.v2_validation_ledger --self-check` PASS.
- Chuẩn bị (chưa chạy): runbook `VAL2-RUNBOOK.md` sha256 `4659f8abdd2234628ec41c4db204a44ed9812eac46b93b52445f1f6363e7727e`; bundle `val2-transfer/feat-p3-rag-opt-e604aed.bundle` sha256 `1d244bce659e0cca2fd766da30c7f18a37ef496bd998992ab7bfa0a23f43e6d3` (13250129 byte); SHA256SUMS `b27fa10c1c47ba7cd1186192fb05546acd54ff7fce4797e370c78858eed4726c`; run_id `P3VAL2-20261112-e604aed-01`; ledger mới dự kiến `D:\DoAnThucTap\p3-val2-ledger.jsonl` (chưa tạo trên máy An). Đây là **lượt 1/3 hợp lệ**, có ghi chú tham chiếu lượt hỏng `P3VAL1-20261112-796ae25-01` (không tính vào cap, An 13:00).

## 13:14, 12/11/2026, Asia/Saigon

- Argon review W15: **PASS**. File: `review-argon-W15.txt` (75 dòng `splitlines`, không issue blocking), commit `e604aed6cec9d8a348baaacfb3341356b2697614`. Ghi nhận P3W15-FIX-01/02 và NEW-01 là non-blocking.

## 13:16, 12/11/2026, Asia/Saigon

- Nguồn: An trả lời widget `t102s569`
- Nguyên văn: "Duyệt chạy val: commit e604aed, run_id P3VAL2-20261112-e604aed-01, chấm theo C0, ledger mới p3-val2-ledger.jsonl, chỉ chạy khi Argon PASS, anh duyệt từng lệnh"
- Ý nghĩa cho đội: An duyệt thực thi VAL2 trên máy anh với SHA `e604aed6cec9d8a348baaacfb3341356b2697614`, run_id `P3VAL2-20261112-e604aed-01`, chấm hàng C0, ledger mới `D:\DoAnThucTap\p3-val2-ledger.jsonl`. Chỉ chạy khi Argon đã PASS (đã PASS 13:14). An duyệt từng lệnh qua card. Thẻ STOP/khóa cho SHA `e604aed` được mở khóa bởi duyệt này. Đây là lượt 1/3 hợp lệ; lượt hỏng P3VAL1 không tính vào cap. Ghi nhận lúc vào log: 13:16, 12/11/2026, Asia/Saigon.

## 13:33, 12/11/2026, Asia/Saigon

- P3VAL2-20261112-e604aed-01 đã chạy xong trên máy An (LAPTOP-PSO405PC), SHA `e604aed6cec9d8a348baaacfb3341356b2697614`, chấm official analyzer dev-val theo C0.
- Thẻ 01–21: hoàn tất đúng thứ tự; thẻ 11 bỏ qua vì thẻ 10 OK (Ollama API 0.40.11); thẻ 17 self-check **PASS** (`canonical UTF-8 LF bytes and read_claims verified`); ledger sản xuất lúc đó chưa tồn tại. Thẻ 19–21 chạy vì An đã mở khóa lúc 13:16. Không card nào bị từ chối/hết hạn. Không đụng holdout, không `--holdout-authorization`, không ghi cây VAL1/P2/official.
- Ghi chú thực thi nhỏ: thẻ 07 tách hai Shell (pip install OK, rồi mới tạo `D:\DoAnThucTap\p3-val2-preflight` và ghi pip freeze). Clone chỉ sau list-heads. Hardware thẻ 02: RAM 15.73 GiB, free 8.16; C 4.01; D 61.42; RTX 4050 6141/5545 MiB. Smoke thẻ 16 OK, `elapsed_ms=7093`, `official_30s_timeout_enough=True` (không dùng làm latency official).
- Freeze live: `D:\DoAnThucTap\p3-val2-preflight\p3-val2-frozen-config.json`, 855 byte LF, SHA-256 `93bd4d5ec647d9e57bb61f5d54ba385a5acd2933cfea0cc9ea4945398099533e`.
- Ledger mới `D:\DoAnThucTap\p3-val2-ledger.jsonl`: 1859 byte, chỉ LF (0 CR), attempt **1/3** hợp lệ, `started_at_utc` 2026-11-12T06:22:36Z, `consumed=true`, `diagnostic_only=false`, claim SHA-256 `51b5ec1b96e561a767174af03435ed5b12144110069d211d28731ea427d25174`. Ledger VAL1 giữ nguyên, không tính vào cap. Cap đã dùng **1/3**, còn 2 lượt.
- Runner một lần, Start-Process pid 14668 (worker 29476), bắt đầu 13:22:36, kết thúc 13:28:49 Asia/Saigon; stdout `OK: wrote 8 validation diagnostic run(s).` (8 config complete); stderr rỗng; không rerun.
- Analyzer official exit 0 lúc 13:32:53. W3 trên C0: **FAIL** vì mismatch 4/14 = 0.2857 > 0.20. Các cổng khác PASS: FPR 1/12 = 0.0833 ≤ 0.15; AOMR C0 10/14 = 0.7143 ≥ AOMR C3 6/14 = 0.4286; coverage 30/30 = 1.00; error 0/30 = 0.00. Cờ AOMR < 0.80: có (`c0_aomr_below_0_80=true`), `decision=PENDING_AN`, cần An quyết trước W5; không phải auto-fail theo ngưỡng AOMR vs C3.
- Latency official: `reportable=false`, p50/p95 = null (chỉ determinism repetitions, 2 lần; không công bố số latency khoa học).
- Aggregate mang về box (chỉ analysis, không result/case): `/workspace/deliverables/shield-phase3-rag-opt-20261111/results/P3VAL2-20261112-e604aed-01/` (`analysis.json` `462bed186d0a109c563a0aee7682354aa2336388df4bb7355b5acaebdd3a6757`, `analysis-table.csv` `a710fde8e06141d37b9d57019ca7293d2a433b668b516298cefff0775f33a5fa`, `analysis-manifest.json` `108db6c4e8fb00697837156a9b629332119e0b1dd434bc3f94b731cdbb931196`). CopyToBox từ D: bị từ chối vì ngoài allowed root; đã stage sang `C:\Users\ADMIN\p3-val2-transfer\analysis-aggregates\` rồi copy, hash khớp.

## 13:54, 12/11/2026, Asia/Saigon

- Nguồn: An trả lời widget `t103u`
- Nguyên văn: "bạn sắp hết usage rồi, lưu tất cả trạng thái lên repo để tôi yêu cầu từng nhân viên khác làm, tạm thời k cần bạn điều phối nữa"
- Ý nghĩa cho đội: An yêu cầu lưu toàn bộ trạng thái P3 lên repo `feat-p3-rag-opt` để giao việc trực tiếp cho từng nhân viên (Claude, Codex, Argon, Muse). Coordinator tạm dừng điều phối. Không gọi model staff trong lượt lưu này. Ghi nhận lúc vào log: 13:54, 12/11/2026, Asia/Saigon.
