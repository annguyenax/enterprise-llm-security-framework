# Review: delta 464218b (parent 0c56e28), P3W13 follow-up

## Verdict: **PASS**

Cả 3 issue W13 còn mở đều đã đóng. Tôi không thấy issue mới nào chặn. Đây là kết luận review của tôi; quyết định cuối cùng vẫn thuộc người duy trì.

Phạm vi kiểm tra: tôi đọc `git show 464218b`, `scripts/run_v2_evaluation.py` (dòng 955–1089 và 4430–4599) và `scripts/derive_v2_dev_val_manifest.py`. Tôi không truy cập được `/workspace/deliverables/...` (bị chặn quyền), nên đã dùng `git show`. Tôi không chạy test; số liệu test là của coordinator (79 + 138 = 217 passed, 0 failed). Tôi không sửa code, không chạy val, không mở artifact holdout.

## Trạng thái từng issue

### P3W13-FIX-01: ghim derived manifest vào official V2: **CLOSED / PASS**
- Đã thêm `OFFICIAL_V2_MANIFEST_PATH` (`scripts/run_v2_evaluation.py:171`) và helper `_official_dev_val_metadata()` (`:1018`). Helper này chỉ đọc metadata của manifest, kiểm tra trạng thái FINAL và bảng 9 entry đúng thứ tự sắp xếp, rồi lấy ra 6 entry dev+val. Nó không mở artifact nào.
- `derive_dev_val_manifest` (`:1038`) từ chối mọi `source_manifest` có đường dẫn resolve khác đường dẫn official, kể cả khi file đó FINAL hoặc trùng byte. Sau đó nó luôn đọc từ đường dẫn đã ghim chứ không từ đường dẫn người dùng đưa vào, nên dùng symlink hay cách viết đường dẫn khác cũng không thay được nguồn.
- `verify_dev_val_manifest` (`:1073–1077`) kiểm tra `source_manifest_sha256` phải bằng SHA-256 của đúng các byte manifest official, và bảng 6 entry (path, sha256, size_bytes) phải khớp tập con official. Cả hai kiểm tra diễn ra trước `_verify_dev_val_artifacts`, tức là trước khi băm bất kỳ artifact nào. Hai đường `preflight` (`:2376`) và `load_split_benchmark` (`:2070`) đều gọi qua hàm này.
- Các test mới bao phủ: digest hợp lệ nhưng không phải official (cả `verify` lẫn `preflight`); bảng tự nhất quán nhưng đã bị sửa, cho từng file trong 6 file; sai lệch từng hash và từng size. Tất cả có `_sha256_file` được stub để fail nếu bị gọi. Như vậy kẽ hở trước đây (bảng cùng digest tự khai, chỉ tự nhất quán với chính nó) đã được đóng.
- `datasets/` không thay đổi giữa 0c56e28 và 464218b. Metadata của manifest official: 1603 byte, sha256 `c91da60b…335a`.

### P3W13-FIX-02: chỉ cho `--benchmark-root` đi với `--benchmark-mode dev-val`: **CLOSED / PASS**
- Ở `main()` (`:4539`), lệnh bị từ chối ngay sau `parse_args`, trước nhánh holdout và trước mọi dispatch hay đọc file. Dòng lỗi là `FAIL [cli_benchmark_root]`.
- Điều kiện kiểm tra là `!= "dev-val"`, nên chặn cả mode `official` mặc định lẫn khi ghi `official` tường minh.
- Kiểm tra cũ `cli_holdout_benchmark` (`:4476`) vẫn còn và làm lớp phòng thủ thứ hai.
- Test bao phủ đủ 4 tổ hợp: mode ngầm định hoặc tường minh, có hoặc không có `--holdout-authorization`. Trong test, `Path.open` bị cấm, còn `run_evaluation`, `run_holdout_evaluation` và `_holdout_request_from_args` đều được stub để fail nếu bị gọi.
- Help text của tham số đã sửa cho khớp hành vi mới.

### P3W13-NEW-01: sửa tài liệu lịch sử commit: **CLOSED / PASS**
- Đã xoá đoạn nói commit bị chặn bởi `index.lock` hoặc file còn unstaged. Thay vào đó, tài liệu ghi rằng W13 đã được commit tại `0c56e2816514f551c2b8c4a9b612d1a24f2ff24b`, kèm ánh xạ từng issue sang phần sửa tương ứng.
- Tôi chạy `git grep` trên `docs`, `TASK_BOARD.md`, `PROJECT_PLAN.md`, `README.md`, `scripts` và `tests` tại 464218b, tìm các cụm "no commit was created", "commit creation was blocked", "remain unstaged", "60 passed" và "index.lock". Không có kết quả nào.
- Số test trong tài liệu đã cập nhật thành 79, khớp với số coordinator báo.
- Phần Limits đã đổi từ "chỉ ghi lại nguồn gốc" thành "ghim vào manifest official", khớp với code.

## Issue mới
Không có (không có P3W13-FIX, P3W13-BLOCK hay P3W13-NEW mới).

## Ghi chú không chặn
1. **Đường gọi trực tiếp bằng Python vẫn nhận `benchmark_root` ở mode official.** Ví dụ `run_evaluation(request, benchmark_root=...)` hay `preflight(..., benchmark_root=...)`. FIX-02 chỉ yêu cầu chặn ở CLI, và các test hiện có (`test_v2_evaluation_runner.py`, `test_v2_holdout_authorization.py`, `test_p2_authorized_ollama_runner.py`) đang dựa vào khả năng này. Đường official vẫn được `verify_frozen_manifest` bảo vệ, nên đây không phải lỗ hổng. Nên ghi rõ phạm vi này trong tài liệu nếu reviewer sau hỏi.
2. **Chế độ dev-val giờ cần manifest official có mặt và đọc được ở local mỗi lần verify.** Đây là hệ quả có chủ đích của việc ghim. Hiện chưa có test riêng cho trường hợp manifest official bị thiếu hoặc hỏng khi đang verify dev-val. Lỗi khi đó sẽ fail-closed với mã `manifest_unreadable` hoặc `manifest_not_final`, nên có thể bổ sung test này sau.
3. **Thứ tự kiểm tra trong `derive_dev_val_manifest`.** Hàm chạy `_check_dev_val_working_set` trước, rồi mới kiểm tra đường dẫn nguồn. Bước đầu chỉ quét tên và link, không mở artifact (test với `Path.open` bị cấm đã xác nhận), nên không ảnh hưởng đến cam kết "từ chối trước khi mở file".
4. **So sánh bảng ở `:1076` dùng so sánh list có thứ tự.** Điều này đúng, vì `_validate_manifest_table` đã buộc cả hai phía phải sắp xếp và có đúng tập path.
