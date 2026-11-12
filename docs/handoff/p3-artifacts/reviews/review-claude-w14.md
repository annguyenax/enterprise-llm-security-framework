# Review chéo W14 — Claude (độc lập, code do Codex implement)

- Repo: `/workspace/shield-team/enterprise-llm-security-framework`, branch `feat-p3-rag-opt`, HEAD `bbb78f3318c09f44847d952027e1fe895ccb5d98` (không đổi). Working tree có thay đổi W14 chưa commit.
- Đã đọc: `git diff` của `scripts/run_v2_evaluation.py`, `scripts/analyze_v2_results.py`, `tests/test_v2_holdout_authorization.py`; toàn bộ các file mới `scripts/v2_validation_ledger.py`, `tests/test_w14_dev_val_execution.py`, `tests/v2_synthetic_support.py`; `w14/w14-coordinator-notes.txt`; `w14/w14-implement-notes.md`; VAL1-RUNBOOK phần P3VAL1-BLK-01/02; APPROVAL-v6 phần ngưỡng.
- Đã chạy: chỉ `.venv/bin/python -m pytest -q tests/test_w14_dev_val_execution.py`, kết quả **22 passed**. Module này chỉ dùng fixture tổng hợp; guard autouse của nó chặn open, glob, walk và hash `datasets/v2`, chặn cả network. Không chạy lại 649 test của coordinator. Không chạy val, không dùng `--holdout-authorization`, không mở/glob/hash holdout, không đọc cases/labels val thật. Không sửa code, không commit/stash/checkout.
- Code không hard-code hash sản xuất nào (`25ba6502…`, `c91da60b…`), nên không có typo hash để sửa.

## Verdict: **PASS-WITH-FIXES**

Kết luận chính: hai blocker P3VAL1-BLK-01/02 được gỡ đúng phạm vi hẹp. Ollama chỉ chạy được khi đồng thời có `dev-val` và `validation`, và phải có một capability riêng do verifier dev-val cấp. Analyzer dev-val không còn gọi verifier official.

Còn một chỗ code làm yếu cổng Ollama hiện có, kể cả đường holdout (FIX-01). Chỗ này nhỏ nhưng trái yêu cầu "không nới", nên phải sửa trước khi coordinator commit. Ngoài ra không có lỗi chặn (BLOCK).

## Issues

### P3W14-FIX-01 — `_ollama_provider_spec` bị gỡ 2 kiểm tra cũ, ảnh hưởng cả đường holdout (sửa trước commit)
`scripts/run_v2_evaluation.py:1355-1362`. Trên `bbb78f3`, hàm này có hai kiểm tra:
```python
if active_settings.llm_provider != "ollama":
    raise IntegrityError("provider_identity", "Ollama settings are required")
_validate_ollama_preclaim_environment(active_settings)
```
Diff đã xóa cả hai và thay bằng comment về AST reader. Lý do đó không đứng vững. Đoạn rescore lịch sử của analyzer (`analyze_v2_results.py:3443-3449`) chỉ lọc node `ast.Assign` có target `descriptor`, nên giữ hai dòng trên không làm AST reader mơ hồ.

Hậu quả: khi dựng spec, đường holdout và worker holdout không còn kiểm `settings.llm_provider`, credential production hay `OLLAMA_BASE_URL`. Hiện vẫn còn các lớp bù: `holdout_preflight` gọi preclaim ở dòng 2722, `_validate_provider_environment` kiểm `LLM_PROVIDER` và credential, worker kiểm `runtime_settings.llm_provider`, và factory hard-code `base_url`. Vì vậy tác động thực tế thấp. Dù vậy đây là một lớp defense-in-depth bị gỡ trên cổng holdout.

**Sửa:** đặt lại hai dòng trên ngay sau `_require_evaluation_ollama_capability(...)`, trước literal `descriptor`. Thêm một test: gọi `_ollama_provider_spec` với capability hợp lệ nhưng settings không phải Ollama, hoặc có credential production, thì phải fail.

### P3W14-FIX-02 — Analyzer CLI nuốt lỗi runner thành `internal_error` (thấp)
`scripts/analyze_v2_results.py:3810`. `main` chỉ bắt `AnalysisError`. Các lỗi mới của đường dev-val/Ollama là `runner.IntegrityError`, ví dụ tham chiếu chứa "holdout", ledger hỏng hoặc bị khóa, freeze lệch, receipt lệch claim. Chúng sẽ hiện thành `FAIL [internal_error]` và mất mã lỗi. Vẫn fail-closed nên không ảnh hưởng an toàn, nhưng khi An duyệt từng lệnh sẽ không chẩn đoán được nguyên nhân STOP. Mẫu này có từ trước (`verify_frozen_manifest`), W14 chỉ làm nó xuất hiện thường hơn.

**Sửa:** thêm `except runner.RunnerError as exc:` in `FAIL [{exc.code}]`, giống runner.

### P3W14-NEW-01 — Lượt val Ollama nào cũng có PASS/FAIL theo W3; chưa ghi mục đích lượt (cần coordinator/An chốt)
APPROVAL-v6 viết: "Các lần val ở W2 … **không có kết quả đạt/không đạt**", còn "Lần xác nhận W3 dùng ngưỡng Pass của W3". Tuy vậy, `_w3_validation_thresholds` (`analyze_v2_results.py:1039`) gắn `status` PASS/FAIL cho mọi lượt Ollama, và cũng cho MOCK (MOCK có `diagnostic_only=true`). Freeze, ledger và analysis không có trường nào nói lượt này là chẩn đoán W2 hay xác nhận W3.

**Đề xuất:** runbook/freeze của val lần 1 ghi rõ mục đích lượt (W2 hay W3), và An xác nhận cùng lúc với cách hiểu "C0 là primary". Tốt hơn nữa là thêm `attempt_purpose` vào freeze và claim, rồi để analyzer báo `status` W3 chỉ khi purpose là W3; các trường hợp khác báo `NOT_APPLICABLE`/`DIAGNOSTIC`. Không cần đổi ngưỡng.

### P3W14-NEW-02 — MOCK được nhận `--campaign-run-id` tùy ý, kể cả ID dạng sản xuất (thấp)
`run_v2_evaluation.py:2598-2602`. MOCK chỉ tự sinh `dev-val-mock-…` khi không truyền ID. Nếu truyền `P3VAL1-20261112-<sha>-01`, artifact MOCK sẽ mang đúng campaign ID sản xuất, chỉ phân biệt được qua `attempt=0`/`diagnostic_only=true`. Không tiêu thụ cap, nhưng dễ lẫn khi đối soát.

**Đề xuất:** MOCK bắt buộc dùng tiền tố `dev-val-mock-`, hoặc từ chối `--campaign-run-id` khi provider là mock.

### P3W14-NEW-03 — Lưu ý vận hành test (có từ trước W14, không phải lỗi W14)
`tests/test_v2_evaluation_runner.py:401` và `tests/test_v2_result_analyzer.py:92` gọi `verify_frozen_manifest` thật trên `datasets/v2`, tức là hash holdout nếu cây đó có holdout. Coordinator chỉ chạy 6 module nên không chạm hai file này. Không nên chạy full suite trên checkout có holdout. Đề xuất ghi điều này vào runbook/notes.

Ngoài các mục trên: **không có P3W14-BLOCK.**

## Kiểm tra bắt buộc

1. **Dev-val không đọc/glob/hash holdout; manifest trỏ holdout thì fail-closed trước khi mở — ĐẠT.**
   - Runner: `preflight` đi qua `_verify_benchmark_manifest(..., "dev-val")`, tức `verify_dev_val_manifest`, rồi `load_split_benchmark(..., benchmark_mode="dev-val")`. Dev-val bắt buộc có `benchmark_root` tường minh, không rơi về `datasets/v2`.
   - Đường Ollama còn đi qua `_dev_val_reference`, áp lên benchmark root, output, ledger, freeze, receipt và mọi thư mục cha. Bước này từ chối tên chứa "holdout" và symlink/junction, trước khi mở file.
   - Analyzer: `_read_verified_input(dev_val_validation=True)` cũng gọi `_dev_val_reference` cho đường dẫn result.
   - Test `test_prohibited_dataset_reference_rejected_in_runner_and_analyzer` (mock/ollama × working-set/manifest) chứng minh fail trước `_sha256_file` và không ghi ledger. Guard autouse chặn open/glob/walk/hash `datasets/v2` và `holdout.jsonl`.
   - Dev-val chỉ đọc metadata file manifest official đã track (`OFFICIAL_V2_MANIFEST_PATH`), như W13/runbook đã duyệt; test đã monkeypatch file này sang bản tổng hợp.

2. **Official/holdout vẫn đòi authorization; không nới `VerifiedHoldoutAuthorization` — ĐẠT, trừ FIX-01.**
   - `_require_ollama_capability`, `load_authorized_holdout_benchmark`, `verify_frozen_manifest` và `load_split_benchmark` (không có tham số authorized) không đổi.
   - `VerifiedDevValOllamaCapability` là class riêng, không kế thừa. Registry kín theo `id` + `repr`, có keepalive chống tái dùng id. Hai kiểm tra `isinstance(VerifiedHoldoutAuthorization)` của holdout vẫn từ chối capability này.
   - `_require_evaluation_ollama_capability` từ chối khi truyền đồng thời hai capability. Worker từ chối payload có cả `holdout_evidence` lẫn `dev_val_evidence`.
   - Test cho thấy `True`, `{}`, `dataclasses.replace` và `deepcopy` đều fail; capability dev-val không mở được `_require_ollama_capability` lẫn `load_authorized_holdout_benchmark`. `test_boolean_or_fabricated_capability_cannot_unlock_ollama` nằm trong 649 test coordinator đã chạy.

3. **Ollama chỉ khi dev-val + validation — ĐẠT.**
   - Preflight (`:2587`) và CLI (`:4922`) chặn khi mode khác `dev-val` hoặc split khác `validation`.
   - `_verify_dev_val_claim_inputs` kiểm lại lần nữa, đồng thời đòi đủ C0–C7 theo thứ tự, repo sạch đúng SHA/branch, Judge OFF, freeze riêng, campaign ID và ledger.
   - Test `test_disallowed_ollama_paths_fail_before_io` phủ dev-val+development, official+development và official+validation, đều fail trước khi `Path.open`.

4. **Analyzer dev-val không gọi `verify_frozen_manifest`; đường official giữ nguyên — ĐẠT.**
   - `analyze_results` rẽ sang `verify_dev_val_manifest` khi mode là dev-val. Thiếu root thì fail; CLI đòi mode và root đi cùng nhau.
   - Test e2e monkeypatch `verify_frozen_manifest` thành `pytest.fail`. `test_official_analyzer_keeps_its_verifier_and_rejects_six_file_set` xác nhận official vẫn gọi verifier official và fail trên bộ sáu file.

5. **Trộn `--holdout-authorization` với dev-val/root/split bị từ chối trước khi mở — ĐẠT.**
   - Runner: `_holdout_request_from_args` từ chối mode/root, các cờ dev-val và `--split` trước `run_holdout_evaluation`; việc parse authorization chưa diễn ra.
   - Analyzer: `main` kiểm mode và root đi cùng nhau trước. `_holdout_analysis_request_from_args` từ chối mode/root/campaign/ledger/freeze/expected digest.
   - Test `test_mixed_authorization_and_dev_val_fails_before_any_open` chạy cho cả runner và analyzer, với `Path.open` bị chặn.
   - Ở chiều ngược lại, `preflight`/`_validate_request` từ chối các cờ validation khi mode không phải dev-val.

6. **Nhãn, cap 3 và MOCK — ĐẠT.**
   - JSON, result manifest, analysis, analysis-manifest và CSV đều mang `benchmark_mode`, `split`, `campaign_run_id`, `run_id` theo từng config, cùng `validation_cap` (attempt, max, consumed, diagnostic_only, claim_sha256). Run ID của từng config phải khác nhau và khác campaign ID, kiểm ở cả runner lẫn analyzer.
   - Ledger: hash chain, `attempt == index`, tối đa 3 dòng, khóa bằng mkdir, mở `O_APPEND` rồi đối chiếu `fstat` (dev, ino, size, nlink) và fsync. Không rollback. Claim chỉ ghi **sau** khi kiểm output, nên output trùng không đốt lượt.
   - Test chứng minh: 3 lượt lỗi vẫn tính và lượt 4 bị chặn mà ledger giữ nguyên byte; MOCK không đọc/ghi ledger và bị cấm truyền ledger/freeze; concurrency không vượt 3; freeze bind đường ledger nên không thay được ledger mới.
   - Giới hạn còn lại (implement notes đã ghi đúng): cap chỉ có hiệu lực khi coordinator giữ đúng một ledger và một freeze; chủ filesystem vẫn xóa hoặc rollback được. Lượt W2 cũ phải được đối soát thủ công; theo review-muse-val1 hiện là 0/3.
   - Lỗi Ollama chỉ lộ ra khi inference (service tắt, sai digest hoặc version), lúc đó lượt đã bị tính. Đúng chính sách "đếm cả lượt lỗi", nhưng runbook cần thẻ probe không claim (API/version/digest) ngay trước thẻ chạy.
   - Analyzer Ollama cần lặp lại đúng môi trường lúc chạy: `LLM_PROVIDER=ollama`, settings khớp freeze, repo sạch đúng SHA thực thi, cùng ledger và freeze. Runbook phải ghi điều này.

7. **Ngưỡng v6, AOMR so với C3, AOMR < 0.80 là cờ An quyết — ĐẠT, xem thêm NEW-01.**
   - Gate gồm FPR ≤ 0.15, AOMR(C0) ≥ AOMR(C3) (so bằng nhân chéo số nguyên), mismatch ≤ 0.20, coverage = 1 và error_rate ≤ 0.05. Thiếu điều kiện báo tỷ lệ thì ra `UNKNOWN`, không PASS.
   - C0 là primary và C3 chỉ là comparator, nên không thể đạt FPR bằng cách tắt context. Cách hiểu "chờ An xác nhận" được ghi vào artifact.
   - `official_aomr_threshold` vẫn là 0.80. `an_decision_required_before_w5` bật cả khi < 0.80 lẫn khi UNKNOWN. `automatic_w5_authorization=false`. Ngưỡng 0.80 không vào gate W3 và không bị hạ.

8. **Fixture `test_v2_holdout_authorization` đổi sang synthetic có làm yếu cổng không — KHÔNG làm yếu.**
   - Hai fixture trước đây gọi `verify_frozen_manifest` thật (hash holdout) và load development thật; nay dùng `ManifestIdentity("a"*64, "final", 9)` và inventory tự tạo. Các assertion và gate holdout giữ nguyên.
   - Patch target đổi từ `runner` sang `analyzer.runner`, sửa đúng chỗ patch trước đây sai module.
   - Guard `_guard_against_opening_real_holdout` nay **chặt hơn**: cấm mọi `.json`/`.jsonl` dưới `datasets/v2`, kể cả mở binary để hash.
   - Phần độ phủ bị mất là việc gắn artifact với manifest official thật. Phần đó không phải cổng an toàn và vẫn được kiểm ở chỗ khác (xem NEW-03).

9. **Không có đường lách `--holdout-authorization` cho val — ĐẠT.**
   - `HoldoutRunRequest` không có split; authorization chỉ phục vụ holdout.
   - Val Ollama chỉ đi qua capability dev-val. Capability này yêu cầu claim mới trong ledger (cap 3) và freeze riêng; freeze/authorization của P2 không dùng lại được.
   - CLI holdout từ chối các cờ dev-val. Không có cờ hay boolean nào khác mở được Ollama.

## Ghi chú nhỏ (không chặn)
- Descriptor Ollama đang tồn tại hai bản: `_ollama_behavior_descriptor` và literal trong `_ollama_provider_spec`. Nếu hai bản lệch nhau thì fail-closed ("provider settings differ from validation claim"), nên an toàn, nhưng nên có một test so khớp hai bản.
- `attempt_root = first.manifest_path.parents[6]` (`analyze_v2_results.py:2507`) là số ma thuật, nhưng đi kèm kiểm `_run_directory` và `output_root_sha256` trong claim nên vẫn fail-closed.
- Worker gọi lại `verify_existing_dev_val_ollama_claim` mỗi lần khởi động: hash lại 6 file, đọc lại freeze và ledger. Chi phí chấp nhận được và là kiểm tra có lợi.

## Việc trước khi commit
1. Codex/coordinator sửa FIX-01 (bắt buộc) và FIX-02 (nên làm), chạy lại 6 module.
2. Coordinator/An chốt NEW-01 (lượt val lần 1 là W2 hay W3) trước khi viết thẻ analyzer. Xử lý NEW-02 nếu tiện.
3. Runbook: tạo một ledger rỗng ngoài checkout; thẻ probe Ollama không claim; analyzer chạy cùng môi trường/SHA/freeze/ledger; ghi NEW-03; thay SHA/run_id/freeze sau commit. STOP thẻ 18 chỉ mở theo điều kiện đã ghi trong runbook.
