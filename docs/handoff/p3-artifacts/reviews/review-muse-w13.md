# Review chéo W13 — `0c56e28` trên `feat/p3-rag-opt`

**Verdict: PASS** — merge được về mặt text/logic. Không phát hiện issue chặn nào (không có `P3W13-FIX` / `P3W13-BLOCK` / `P3W13-NEW`).
Test do coordinator chạy lại, không chạy lại ở review này: 60 passed (`test_v2_dev_val_manifest.py`) + 138 passed (regression chọn lọc) = 198 passed, 0 failed. Không chạy val.

## Đối chiếu tiêu chí

| Tiêu chí | Kết quả |
|---|---|
| Manifest dẫn xuất đúng 6 file (dev+val cases/labels + corpus + exemptions; provenance loại vì split loader không dùng, không phải holdout) | Đạt. `DEV_VAL_FROZEN_PATHS` đúng 6 path; `design/authoring-provenance.jsonl` bị từ chối theo path mà không mở. |
| Chế độ dev-val không đòi holdout | Đạt. `derive`/`verify` không tham chiếu holdout; thiếu holdout không phải lỗi; dispatch `_verify_benchmark_manifest` tách official/dev-val. |
| Từ chối path holdout trước khi mở | Đạt. `_check_dev_val_working_set` quét tên (case-insensitive, gồm cả dir) trước mọi `open`/hash; bảng manifest kiểm `holdout` trước khi mở artifact; test chặn `Path.open`/`_sha256_file` chứng minh. |
| Verifier official 9-file và authorized holdout không bị nới | Đạt. Patch không có hunk nào sửa thân `verify_frozen_manifest` / `load_authorized_holdout_benchmark`; `load_split_benchmark` thêm `benchmark_mode` keyword-only, default `official`; `--benchmark-mode/--benchmark-root` bị từ chối khi kèm `--holdout-authorization`. |
| Tài liệu/comment mâu thuẫn | 2 điểm chữ nghĩa + 1 điểm thiếu bao phủ test, đều không chặn (xem ghi chú). |

Điểm khớp PLAN-P3-v6 W13: Output (manifest dẫn xuất + chế độ runner + test fixture/holdout-refusal/không mở holdout) và Pass (test xanh, review xác nhận không truy cập path holdout, fail khi lẫn holdout theo path) đều được bao phủ. W1 vẫn là blocker nguồn dev+val chính thức — W13 không tự tạo dữ liệu, chỉ dùng fixture synthetic trong test. APPROVAL-v6 không đặt thêm ràng buộc nào lên W13; không có lần val nào trong patch/doc.

## Ghi chú không chặn (không phải issue)

- **N1 — chữ "containing `result.json`" trong doc:** code so khớp chính xác tên file (`lowered == "result.json"`), chỉ `holdout`/`ollama` là substring. Hành vi đúng và test `archive/result.json` xanh; nên sửa doc thành "tên file đúng `result.json`" cho khớp code.
- **N2 — đoạn "Commit creation was blocked… no commit was created" trong `phase3-w13-dev-val-manifest.md` đã lỗi thời:** commit `0c56e28` hiện đã tồn tại với đúng message được nêu. Nên xóa/sửa đoạn này trước hoặc khi merge để doc không tự mâu thuẫn.
- **N3 — file manifest copy thừa trong cây dev-val chưa rõ hành vi:** `_iter_frozen_artifact_paths` (suy từ test xanh) chỉ chốt 6 artifact runtime, nên một bản copy `manifests/benchmark-v2-manifest.json` nằm trong cây dev-val dường như không bị từ chối và không được test nào bao phủ. Vô hại về rò rỉ holdout (chế độ dev-val chỉ đọc derived path), nhưng nên làm rõ trong doc hoặc thêm một test fail-closed/cho-phép tường minh.
