## Review W2

**Verdict: PASS** — đúng scope dev/MOCK, không val/holdout.

* `LOG_ONLY` context không fold vào `final_decision`, vẫn giữ audit/`stage_results` qua [_context_fold_severity](file:///workspace/deliverables/shield-phase3-rag-opt-20261111/app/services/rag_query.py:37).
* `SANITIZE` neighbor thấp điểm bị loại (không pass sanitized copy), fail-closed khi rỗng, qua [_primary_relevance_chunk_ids](file:///workspace/deliverables/shield-phase3-rag-opt-20261111/app/services/rag_query.py:49) + ngưỡng `0.5`.
* Không tắt lớp context; `BLOCK` thấp điểm vẫn chặn.

Không mở issue `P3W2-FIX/BLOCK/NEW`.

Ghi chú không chặn:
* Ngưỡng `0.5` + so sánh `abs(score)` chỉ fit dev/MOCK, dễ overfit; cần val/holdout riêng trước khi chốt.
