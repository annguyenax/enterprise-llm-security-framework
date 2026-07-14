# Phase 12E Master Plan — Ablation Evaluation of the RAG Security Pipeline

> **Trạng thái: KẾ HOẠCH. Phase 12E CHƯA BẮT ĐẦU triển khai.**
> Branch: `phase-12e-planning` · Base commit: `4654fc4bac8f578d09c178c6ffb58fe0b7446c4c`
>
> Tài liệu này **không** là kết quả, **không** chứa số liệu đánh giá nào, và
> **không** cho phép bắt đầu code. Nó phải qua 3 audit gate (Code X / Gemini /
> Grok) và go-ahead riêng của người duy trì trước khi bất kỳ dòng code 12E nào
> được viết (`AGENT_RULES.md` rule 12).

**Quy ước:** mọi chỗ ghi `VERIFY DURING IMPLEMENTATION` là điều **chưa được
code hiện tại chứng minh**. Không được coi là đã hỗ trợ.

---

## 0. Bằng chứng nền từ repository (đã đọc code thật, không suy đoán)

| Sự thật | Bằng chứng |
|---|---|
| **`GuardProfile` CHƯA TỒN TẠI** | `app/core/pipeline.py:12-18` — docstring ghi rõ nó là "future home", "explicitly a Phase 12E concern", "deliberately **not** implemented in this pass" |
| **Không có guard toggle nào trong config** | `app/core/config.py` — `Settings` chỉ có `enable_audit_log`; không có cờ bật/tắt guard nào |
| `settings` là singleton nạp lúc import | `app/core/config.py:131` |
| **Seam tiêm đã có và đã được chứng minh** | `run_rag_query_uncommitted(*, query, top_k, retriever, request_id=None, provider=None)` — `app/services/rag_query.py:363-370`. `tests/test_rag_pipeline.py:103-105` đã dùng `provider=provider` thành công |
| 8 stage có đo latency | `latency_ms[...]` tại `rag_query.py` dòng 418, 461, 492, 565, 616, 699, 726, 747 → `input_guard`, `retrieval`, `provenance_guard`, `rag_context_guard`, `aggregate_context_guard`, `provider`, `dlp`, `output_guard` |
| Khoá `"total"` được thêm bởi `_with_total` | `rag_query.py:124-128`, dùng `time.perf_counter()*1000` |
| 7 `stop_reason` + `None` | `scripts/validate_v2_benchmark.py:146-149` |
| 5 `Decision` | `allow`, `block`, `sanitize`, `log_only`, `human_review` |
| **Mock Provider KHÔNG BAO GIỜ echo nội dung chunk** | `app/services/llm_provider.py:47-64` — chỉ phát `"{n} guard-approved context chunk(s) were considered."` |
| Do đó `expected_dlp_action` chỉ có 1 giá trị | `DLP_ACTION_VALUES = {"not_applicable_mock_provider"}` — `validate_v2_benchmark.py:145` |
| Benchmark: 120 case / 172 doc / 23 family, split 30-30-60 | manifest FINAL, 9 artifact |
| `category`: benign 48 · malicious 48 · mixed 16 · neutral 8 | đếm trực tiếp từ `datasets/v2/labels/*.jsonl` |
| `evaluation_scope`: end_to_end 104 · availability_fault 8 · component 4 · residual_risk_only 4 | đếm trực tiếp từ `datasets/v2/cases/*.jsonl` |
| Seam nạp corpus | `upsert_documents` — `app/retrieval/base.py:34`, `app/retrieval/sqlite_bm25.py:280` |
| **Rule of Freezing (bắt buộc)** | `ADR-003` §"Freezing and integrity rules": runner **phải** verify SHA-256 manifest ở đầu **mỗi** lần chạy và **abort trước khi sinh bất kỳ report nào** nếu lệch |

---

## 1. Mục đích và phạm vi

**Mục đích:** đo bằng thực nghiệm mức đóng góp của từng lớp guard trong pipeline
RAG security (Phase 12C) đối với khả năng phòng thủ, tỉ lệ báo động giả, và độ
trễ — trên benchmark v2 đã FINAL freeze (Phase 12D).

**Trong phạm vi:** ablation runner offline; cấu hình bật/tắt guard nội bộ; thu
thập metric phát hiện / báo động giả / rò rỉ / độ trễ; báo cáo có kiểm soát
claim.

**Ngoài phạm vi:** sửa logic guard; thêm guard mới; retrieval ngữ nghĩa; gọi LLM
thật; tối ưu hiệu năng; bất kỳ thay đổi nào lên 9 artifact đã freeze.

## 2. Câu hỏi nghiên cứu

- **RQ1.** Mỗi lớp guard đóng góp bao nhiêu vào tỉ lệ chặn tấn công (attack
  block rate) trên tập holdout?
- **RQ2.** Mỗi lớp guard gây ra bao nhiêu báo động giả trên case benign?
- **RQ3.** Lớp nào là *cần thiết* (bỏ nó ra thì có tấn công lọt) và lớp nào chỉ
  *dư thừa* (bỏ ra không đổi kết quả) trên benchmark này?
- **RQ4.** Chi phí độ trễ của từng lớp là bao nhiêu (p50/p95 per-stage)?
- **RQ5.** Có tấn công nào **không lớp nào** chặn được (residual risk đã khai
  báo trước) — và benchmark có dự đoán đúng chúng không?

## 3. Giả thuyết

- **H1.** Input Guard chặn phần lớn `direct_injection`, nhưng **không** chặn được
  `indirect_injection` (nội dung độc nằm trong document, không nằm trong query).
- **H2.** RAG Context Guard là lớp *duy nhất* chặn được indirect injection ⇒ bỏ
  nó ra sẽ làm rơi mạnh nhất attack block rate.
- **H3.** Provenance Guard đóng góp chủ yếu ở family low-trust/compromised-source,
  gần như không đóng góp ở family khác.
- **H4.** Tổng đóng góp của các lớp **không cộng tuyến tính** — có chồng lấn
  (một tấn công bị nhiều lớp cùng chặn).
- **H5.** Latency tổng chủ yếu do `retrieval`, không do guard. (Guard là rule-based,
  deterministic.)

Mọi giả thuyết đều có thể bị bác bỏ. Kết quả xấu được **báo cáo và phân tích**,
không được vá thầm (ADR-003, Rule of Freezing).

## 4. Đơn vị phân tích

**Một quan sát = một (case_id, config_id).** 120 case × N config. Case là đơn vị,
không phải chunk hay stage. Mỗi quan sát sinh đúng một `RagPipelineResult`.

## 5. Cấu hình thí nghiệm

| ID | Mô tả | Biện minh |
|---|---|---|
| `C0_all_on` | Toàn bộ guard bật (baseline có bảo vệ) | Mốc so sánh chính |
| `C1_no_input` | Tắt Input Guard | RQ1/RQ3 |
| `C2_no_provenance` | Tắt Provenance Guard | RQ1/RQ3 |
| `C3_no_context` | Tắt RAG Context Guard (cả per-chunk lẫn aggregate) | RQ1/RQ3, H2 |
| `C4_no_dlp` | Tắt DLP | RQ1 (xem §15 — giới hạn nghiêm trọng) |
| `C5_no_output` | Tắt Output Guard | RQ1/RQ3 |
| `C6_none` | **No-guard baseline** — tắt toàn bộ guard | Mốc "không phòng thủ" |

**Tổ hợp (chỉ khi có biện minh học thuật):** `C7_no_context_no_output` — kiểm tra
H4 (chồng lấn giữa hai lớp cùng thấy nội dung độc). Không chạy toàn bộ 2⁵=32 tổ
hợp: cỡ mẫu không cho phép kết luận về tương tác bậc cao, và làm vậy chỉ tạo ảo
giác chính xác.

**`C6_none` chỉ được chạy khi thoả cả 4 điều kiện:**
1. Chạy **offline**, in-process, qua `run_rag_query_uncommitted(...)` — **không**
   qua HTTP server đang chạy.
2. Dùng database SQLite **tạm thời riêng cho từng run**, không phải
   `data/retrieval.db`.
3. Provider là Mock/double offline — không có provider thật.
4. Cấu hình no-guard **không thể** đạt tới từ bất kỳ request HTTP nào (§8).

## 6. Ma trận ablation

| Config | Input | Provenance | Context (chunk) | Context (aggregate) | DLP | Output |
|---|---|---|---|---|---|---|
| `C0_all_on` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `C1_no_input` | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `C2_no_provenance` | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ |
| `C3_no_context` | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| `C4_no_dlp` | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| `C5_no_output` | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| `C6_none` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `C7_no_context_no_output` | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |

`retrieval` và `provider` **không phải guard** → không bao giờ tắt (tắt chúng thì
không còn pipeline để đo).

**Tổng số lần chạy pipeline:** 120 case × 8 config = **960**.

## 7. Thiết kế guard-toggle

`GuardProfile` **phải được xây mới** (chưa tồn tại — §0). Ràng buộc thiết kế:

```python
# app/core/pipeline.py  (ĐỀ XUẤT — chưa tồn tại)
@dataclass(frozen=True)
class GuardProfile:
    input_guard: bool = True
    provenance_guard: bool = True
    rag_context_guard: bool = True
    aggregate_context_guard: bool = True
    dlp: bool = True
    output_guard: bool = True

    @property
    def profile_id(self) -> str: ...   # ổn định, dùng làm khoá kết quả

ALL_ON = GuardProfile()   # mặc định của MỌI đường public
```

**Ràng buộc bất di bất dịch:**

1. `GuardProfile` được truyền vào **như một tham số hàm** của
   `run_rag_query_uncommitted(..., guard_profile: GuardProfile = ALL_ON)` —
   **KHÔNG** đọc từ biến môi trường, **KHÔNG** thêm field vào `Settings`,
   **KHÔNG** đọc từ request body.
2. Mặc định là `ALL_ON`. Bỏ qua tham số ⇒ hành vi **byte-identical** với Phase
   12C hiện tại.
3. Khi một guard bị tắt, stage đó **vẫn phải ghi một `StageResult`** với
   `reason_code` dạng `"<stage>_disabled_ablation"` và `decision=None`, để
   telemetry không bị "mất stage" một cách âm thầm.
4. **Không sửa logic bên trong bất kỳ guard nào.** Toggle chỉ quyết định *có gọi*
   guard đó hay không — không đổi cách nó phán quyết.

`VERIFY DURING IMPLEMENTATION`: liệu có thể bỏ qua RAG Context Guard mà vẫn giữ
được ràng buộc aggregate-context-budget hay không. Hiện `_bound_chunks_for_aggregate`
(`rag_query.py:131`) đứng riêng; cần xác minh tắt guard không vô tình bỏ luôn
giới hạn kích thước context gửi provider.

## 8. Tách biệt cấu hình phục vụ công khai và cấu hình đánh giá nội bộ

**Đây là ràng buộc bảo mật cứng.** Hiện tại **không có bất kỳ bề mặt nào cho phép
client tắt guard** (`config.py` không có cờ nào; request schema `extra="forbid"`).
Phase 12E **không được phá vỡ tính chất này**.

| | Public serving | Internal evaluation |
|---|---|---|
| Đường vào | `POST /v1/rag/query` (HTTP) | `run_rag_query_uncommitted(...)` in-process |
| Guard profile | **Luôn `ALL_ON`, hard-coded** | Tham số hàm |
| Nguồn cấu hình | `Settings` (env) | Đối tượng Python truyền tay |
| DB | `data/retrieval.db` | SQLite tạm, riêng từng run |

**Test bắt buộc (Phase 12E phải thêm):**
- Không có tên biến môi trường nào có thể đổi `GuardProfile`.
- Request HTTP chứa field `guard_profile`/`guards`/`disable_*` bị `extra="forbid"`
  từ chối với 422.
- `app/api/routes.py::rag_query` gọi pipeline **không truyền** `guard_profile`
  (⇒ luôn nhận `ALL_ON`).
- Grep tĩnh: `GuardProfile` không xuất hiện trong `app/api/`.

## 9. Chính sách split

Ba split, **vai trò tách bạch tuyệt đối**:

| Split | Số case | Vai trò |
|---|---|---|
| development | 30 | Debug runner, sửa lỗi hạ tầng. **Được xem tự do.** |
| validation | 30 | Chốt cấu hình runner, chọn metric, dry-run. **Được xem.** |
| holdout | 60 | **Đo lần cuối. CHỈ ĐƯỢC CHẠY MỘT LẦN.** |

## 10. Quy tắc sử dụng development / validation / holdout

1. **Holdout chỉ chạy một lần**, sau khi runner đã đóng băng trên
   development+validation, và sau khi người duy trì phê duyệt.
2. **Sau khi xem kết quả holdout, KHÔNG được sửa logic guard, không được sửa
   metric, không được sửa runner.** Bất kỳ sửa đổi nào sau đó ⇒ mọi số holdout
   trở nên vô hiệu và phải chạy lại trên một benchmark mới (v3).
3. Không "peek" holdout trong lúc phát triển. Runner mặc định **loại trừ**
   holdout; phải có cờ tường minh `--include-holdout` + xác nhận của người duy trì.
4. Kết quả kém trên holdout được **báo cáo và phân tích**, không được vá
   (ADR-003, Rule of Freezing).

## 11. Kiểm soát nhiễm chéo

1. **Runner phải verify SHA-256 manifest ở đầu MỖI lần chạy và abort TRƯỚC KHI
   sinh bất kỳ file kết quả nào nếu lệch** — đây là yêu cầu tường minh của
   ADR-003 (§"Freezing and integrity rules"), không phải tuỳ chọn.
2. Runner **không được ghi** vào `datasets/v2/`.
3. Corpus được nạp vào một SQLite **tạm thời**; database đó bị xoá sau run.
4. Không có tuning nào dựa trên holdout (§10).
5. Candidate do Hermes sinh **không bao giờ** trở thành ground truth tự động
   (§32).

## 12. Metric và công thức chính xác

Ký hiệu: với case $i$ và config $c$, gọi $d_{i,c}$ = `final_decision` thực tế,
$s_{i,c}$ = `stop_reason` thực tế. Ground truth từ label: $A_i$ =
`allowed_final_decisions` (tập), $S_i$ = `allowed_stop_reasons` (tập).

**Định nghĩa "đúng" (correct):**
$$\text{correct}(i,c) = \mathbb{1}[\,d_{i,c} \in A_i \;\wedge\; s_{i,c} \in S_i\,]$$

Dùng **tập cho phép** (`allowed_*`), không dùng giá trị đơn (`expected_*`) — vì
label đã cố ý cho phép nhiều kết cục hợp lệ (ví dụ một tấn công có thể bị chặn ở
Input Guard *hoặc* ở Context Guard, cả hai đều đúng).

**Chỉ tính trên `evaluation_scope`:**
- `end_to_end` (104 case) → dùng cho mọi metric chính.
- `component` (4) → báo cáo riêng, không gộp.
- `availability_fault` (8) → báo cáo riêng (đo fail-closed, không đo detection).
- `residual_risk_only` (4) → **không tính vào detection metric**; báo cáo riêng
  như bằng chứng trung thực về giới hạn.

## 13. Metric phát hiện

Trên tập $M$ = case `category ∈ {malicious, mixed}` và `evaluation_scope = end_to_end`:

$$\text{ABR}(c) = \frac{|\{i \in M : \text{correct}(i,c)\}|}{|M|} \quad \text{(Attack Block Rate)}$$

$$\text{ASR}(c) = 1 - \text{ABR}(c) \quad \text{(Attack Success Rate)}$$

Ở đây "chặn" nghĩa là **kết cục khớp ground truth**, không đơn thuần là
`decision == block` — vì một số case đúng đắn phải `sanitize` chứ không `block`.

## 14. Metric báo động giả

Trên tập $B$ = case `category = benign` và `evaluation_scope = end_to_end`:

$$\text{FPR}(c) = \frac{|\{i \in B : \neg\text{correct}(i,c)\}|}{|B|}$$

`neutral` (8 case) báo cáo riêng, không gộp vào FPR — chúng không phải benign
theo nghĩa "phải được trả lời", mà là trung tính.

## 15. Metric rò rỉ — GIỚI HẠN NGHIÊM TRỌNG, PHẢI KHAI BÁO

**Mock Provider không bao giờ echo nội dung chunk** (`llm_provider.py:47-64`, chỉ
phát ra số lượng chunk). ⇒ **Không một secret nào trong document có thể xuất hiện
ở output của một live run.** ⇒ `redaction_count` sẽ **luôn bằng 0** với mọi
config, kể cả `C4_no_dlp` và `C6_none`.

**Hệ quả:** rò rỉ **không thể đo end-to-end** bằng live pipeline. Đây chính là lý
do label ghi `expected_dlp_action: "not_applicable_mock_provider"` và
`expected_redaction_count: 0`.

**Cách xử lý (bắt buộc, trung thực):**
- Rò rỉ được đo bằng một **provider double có kịch bản** (scripted offline
  provider) tiêm qua tham số `provider=` đã có sẵn — chính là mẫu mà
  `tests/test_dlp_guard.py` và `tests/test_rag_pipeline.py` đang dùng.
- Kết quả này phải được báo cáo **riêng**, gắn nhãn rõ ràng là **"đo bằng provider
  double, không phải bằng Mock Provider mặc định"**, và **không được trộn** vào
  metric detection/FPR của live run.
- **Luận văn KHÔNG được tuyên bố** "DLP ngăn rò rỉ trong thực tế" dựa trên live
  run. Chỉ được nói: "DLP ngăn rò rỉ trong điều kiện provider có echo context,
  được mô phỏng bằng double."

$$\text{LeakRate}(c) = \frac{\text{số case mà secret xuất hiện trong output cuối}}{\text{số case có secret trong context được chấp nhận}}$$
(chỉ tính trong chế độ provider-double)

## 16. Đo độ trễ

- Nguồn: `latency_ms` dict đã có sẵn trong `RagPipelineResult`
  (`pipeline.py:79`), ghi bằng `time.perf_counter()` (`rag_query.py:121`).
- **Warm-up:** bỏ 10 lần chạy đầu tiên của mỗi config trước khi ghi số.
- **Lặp:** mỗi (case, config) chạy $R$ lần; đề xuất $R = 5$.
  `VERIFY DURING IMPLEMENTATION`: $R$ đủ hay chưa, xét độ ồn của
  `perf_counter` trên Windows và I/O của SQLite.
- **Audit log ảnh hưởng latency.** Phải chạy với `ENABLE_AUDIT_LOG` cố định
  cho mọi config (đề xuất: bật, vì đó là cấu hình serving thật), và ghi rõ đã
  chọn gì.
- Máy đo: không chạy song song với việc khác; ghi lại CPU/RAM/OS.

## 17. Yêu cầu telemetry theo stage

`latency_ms` **đã có sẵn** 8 khoá stage + `"total"` (§0). Phase 12E cần thêm:

- Khi guard bị tắt, khoá stage đó **phải vắng mặt** (không ghi 0.0) — để phân
  biệt "chạy hết 0ms" với "không chạy". `VERIFY DURING IMPLEMENTATION`.
- `StageResult` cho stage bị tắt vẫn phải xuất hiện với
  `reason_code="<stage>_disabled_ablation"` (§7).
- **Không** thêm telemetry nào ghi nội dung thô (query, chunk text, secret) —
  vi phạm hợp đồng an toàn của `StageResult` (`pipeline.py:29-30`).

## 18. Tính p50 / p95

Với mỗi (config, stage), gom toàn bộ mẫu $x_1..x_n$ (mọi case × mọi lần lặp, sau
warm-up), sắp xếp tăng dần:

$$P_q = x_{\lceil q \cdot n \rceil} \quad (q = 0.50,\ 0.95)$$

**Dùng phương pháp "nearest-rank"** (không nội suy). Lý do: đơn giản, tái lập
được, không phụ thuộc thư viện. Phải ghi rõ trong báo cáo là đã dùng nearest-rank
— hai phương pháp khác nhau cho ra số khác nhau.

Báo cáo p50/p95 cho: `total`, và từng stage. Kèm $n$ (số mẫu) mỗi ô.

## 19. Tính đóng góp biên (marginal contribution)

Đóng góp của guard $g$ = mức tụt của ABR khi tắt riêng $g$:

$$\Delta_g = \text{ABR}(C0_{\text{all\_on}}) - \text{ABR}(C_{\neg g})$$

**Cảnh báo phải ghi trong báo cáo:** $\sum_g \Delta_g \neq \text{ABR}(C0) -
\text{ABR}(C6_{\text{none}})$ nói chung, vì các guard **chồng lấn** (một tấn công
có thể bị nhiều lớp cùng chặn). $\Delta_g$ đo *tính cần thiết* của $g$, **không**
đo "phần đóng góp" theo nghĩa phân rã cộng tính. Không được trình bày $\Delta_g$
như một phép chia miếng bánh.

Ngoài ra báo cáo:
- **Guard cần thiết:** $\Delta_g > 0$ ⇒ có tấn công *chỉ* $g$ chặn được.
- **Guard dư thừa trên benchmark này:** $\Delta_g = 0$ ⇒ **không** kết luận là vô
  dụng; chỉ kết luận "benchmark này không chứa tấn công mà chỉ $g$ chặn được".

## 20. Yêu cầu báo cáo theo nhóm

**Ràng buộc bắt buộc từ Gemini (đã chấp nhận ở Phase 12D, không thương lượng lại):**

> 23 family / 120 case ⇒ ~2–8 case holdout mỗi family. **Quá nhỏ để báo cáo phần
> trăm theo từng family.**

Do đó:
- **Được** báo cáo phần trăm ở: mức **tổng hợp** (toàn bộ end_to_end), và mức
  **nhóm lớn đã khai báo TRƯỚC khi xem kết quả**.
- Nhóm lớn đề xuất (**phải chốt trước khi chạy holdout**): `direct_injection`,
  `indirect_injection`, `data_exfiltration`, `benign_control`, `availability`.
  Ánh xạ family → nhóm phải viết ra và commit trước.
- **Không được** báo cáo phần trăm theo từng family riêng lẻ. Family chỉ được mô
  tả **định tính** ("cả 3 case của family X đều bị chặn") hoặc như case study.
- Mọi bảng phải kèm cỡ mẫu $n$. Không có $n$ = không được đăng.

## 21. Kiểm soát ngẫu nhiên và tính tất định

- Pipeline guard là **rule-based, tất định** — không có sampling.
- Mock Provider **tất định** (`llm_provider.py`).
- Retrieval BM25 **tất định** với cùng corpus + query.
- ⇒ Với cùng code + cùng corpus, kết quả *phán quyết* phải **byte-identical** qua
  các lần chạy. **Runner phải tự kiểm chứng điều này**: chạy lặp lại một config
  và assert kết quả trùng khớp. `VERIFY DURING IMPLEMENTATION`.
- Chỉ **latency** là biến thiên → chỉ latency mới cần lặp + phân vị.
- Nếu phát hiện phán quyết **không** tất định ⇒ **dừng ngay**, đó là bug, không
  phải "nhiễu thống kê".

## 22. Ghi nhận môi trường và phụ thuộc

Mỗi result artifact **phải** nhúng:

```yaml
environment:
  git_commit: <full sha>          # BẮT BUỘC
  git_branch: <branch>
  git_dirty: false                # PHẢI false — không chạy trên cây bẩn
  python_version: <sys.version>
  platform: <platform.platform()>
  cpu: <processor>
  benchmark_manifest_sha256: <hash của chính manifest>
  benchmark_manifest_status: final
  dependencies: <pip freeze>      # snapshot
  enable_audit_log: <bool>
  guard_profile: <profile_id>
  provider: mock | scripted_double
  repetitions: <R>
  warmup: <int>
```

**Không được chạy trên working tree bẩn.** `git_dirty=true` ⇒ runner abort.

## 23. Schema artifact kết quả

Đề xuất (JSON, một file per config):

```json
{
  "schema_version": 1,
  "config_id": "C3_no_context",
  "guard_profile": {"input_guard": true, "rag_context_guard": false, "...": "..."},
  "environment": { "...": "see §22" },
  "split": "validation",
  "cases": [
    {
      "case_id": "V2-VAL-0001",
      "scenario_family": "indirect_injection",
      "category": "malicious",
      "evaluation_scope": "end_to_end",
      "actual_final_decision": "allow",
      "actual_stop_reason": "allowed",
      "actual_provider_called": true,
      "actual_retrieved_count": 3,
      "actual_accepted_context_count": 3,
      "actual_redaction_count": 0,
      "correct": false,
      "latency_ms_samples": {"input_guard": [1.2, 1.1], "total": [42.0, 40.8]}
    }
  ],
  "aggregate": {
    "n_end_to_end": 104,
    "abr": null,
    "fpr": null,
    "note": "computed by the analysis step, not the runner"
  }
}
```

**Cấm tuyệt đối trong artifact:** query thô, chunk text, giá trị secret, đường dẫn
tuyệt đối, stack trace. (Cùng hợp đồng an toàn với `StageResult`.)

## 24. Bố cục file/thư mục đề xuất

```
app/core/pipeline.py                    # + GuardProfile (CHƯA CÓ — phải viết)
app/services/rag_query.py               # + tham số guard_profile (mặc định ALL_ON)

scripts/run_v2_evaluation.py            # runner (MỚI)
scripts/analyze_v2_results.py           # tính metric từ artifact (MỚI, tách khỏi runner)

reports/evaluation-v2/                  # THƯ MỤC MỚI — không đụng reports/evaluation/ (v1)
  raw/<config_id>-<split>.json
  analysis/metrics-<split>.json
  analysis/metrics-<split>.md

tests/test_guard_profile.py             # MỚI — chứng minh không có bề mặt public
tests/test_v2_evaluation_runner.py      # MỚI — manifest gate, determinism, abort paths
```

**Tách runner khỏi analyzer** là có chủ đích: runner sinh dữ liệu thô, analyzer
tính metric. Sửa công thức metric không cần chạy lại 960 lần pipeline.

**`reports/evaluation/` (v1) tuyệt đối không được ghi đè** — ADR-003 yêu cầu tường
minh.

## 25. Chính sách xử lý lỗi và run dở dang

- Bất kỳ exception nào ở một case ⇒ ghi `error_category`, **tiếp tục** các case
  còn lại, và đánh dấu run là `partial`.
- **Run `partial` KHÔNG được dùng để báo cáo.** Chỉ run `complete` mới được.
- Manifest hash lệch ⇒ **abort trước khi ghi bất kỳ file nào** (ADR-003).
- `git_dirty` ⇒ abort.
- Phán quyết không tất định ⇒ abort (§21).
- Runner **không được** ghi đè artifact đã tồn tại; phải fail-closed.

## 26. Quy trình tái lập

```powershell
git checkout <commit ghi trong artifact>
.\scripts\verify_phase.ps1              # manifest FINAL, 9 hash khớp
.venv\Scripts\python.exe scripts/run_v2_evaluation.py --split validation
.venv\Scripts\python.exe scripts/analyze_v2_results.py --split validation
```
Kết quả *phán quyết* phải trùng khớp hoàn toàn. Latency sẽ khác (phần cứng).

## 27. Giới hạn thống kê

- $n = 104$ case end_to_end toàn bộ; holdout end_to_end còn ít hơn.
- **Không tính p-value, không tuyên bố "có ý nghĩa thống kê"** cho so sánh giữa
  các config trên cỡ mẫu này.
- Khoảng tin cậy: nếu tính, phải là CI cho tỉ lệ (Wilson) và phải ghi rằng nó
  **rất rộng** ở $n$ nhỏ. `VERIFY DURING IMPLEMENTATION` — có thể quyết định không
  tính, và nói rõ vì sao.
- **Không so sánh theo từng family bằng phần trăm** (§20).

## 28. Rủi ro construct validity

- **Ground truth do chính nhóm tác giả guard viết ra** → nguy cơ vòng tròn. Giảm
  thiểu (đã làm ở 12D): label dùng `allowed_*` (tập kết cục hợp lệ) thay vì ép một
  hành vi cụ thể; validator **guard-independent** (không import `app.guards.*`).
- "Chặn được" ≠ "hiểu được". Guard rule-based có thể chặn đúng vì trùng keyword,
  không phải vì hiểu ý đồ. **Không được tuyên bố hiểu ngữ nghĩa.**
- `residual_risk_only` (4 case) là bằng chứng trung thực rằng có tấn công hệ thống
  **không thể** bắt — phải báo cáo, không được giấu.

## 29. Rủi ro internal validity

- **Rò rỉ holdout** — kiểm soát bằng §10 (chạy một lần, không sửa sau khi xem).
- **So sánh run từ các commit khác nhau** — cấm tuyệt đối. Mọi config trong một
  thí nghiệm phải chạy trên **cùng một commit**; commit đó nhúng trong artifact
  (§22). Analyzer **phải abort** nếu các artifact có `git_commit` khác nhau.
- **Sửa code giữa các lần ablation** — cấm. Toàn bộ 960 run phải cùng một commit.
- **Latency bị nhiễu** bởi tải máy — kiểm soát bằng warm-up, lặp, và ghi môi trường.

## 30. Rủi ro external validity

- Corpus **tổng hợp**, không phải dữ liệu doanh nghiệp thật.
- **Mock Provider**, không phải LLM thật ⇒ **không** đo được hành vi LLM thật, và
  **không** đo được rò rỉ end-to-end (§15).
- Retrieval **BM25 từ vựng**, không ngữ nghĩa.
- Guard **rule-based**, không phải model.
- ⇒ Kết quả nói về **hệ thống này, trên benchmark này**. Không ngoại suy ra
  "production LLM security".

## 31. Những claim luận văn KHÔNG ĐƯỢC đưa ra

1. ❌ "Hệ thống chặn được X% tấn công prompt injection **trong thực tế**."
   → Chỉ được: "trên benchmark v2, ở cấu hình C0, ABR = X% (n=...)".
2. ❌ "DLP ngăn rò rỉ dữ liệu." → Mock Provider không echo context; rò rỉ chỉ đo
   được bằng provider double (§15).
3. ❌ "Guard X chiếm Y% hiệu quả phòng thủ." → $\Delta_g$ không cộng tính (§19).
4. ❌ "Hệ thống bắt 100% family Z." → cỡ mẫu family quá nhỏ (§20).
5. ❌ "Hệ thống hiểu ý đồ tấn công." → rule-based (§28).
6. ❌ "Sẵn sàng production." → PoC học thuật, dữ liệu tổng hợp.
7. ❌ Bất kỳ số liệu 12E nào **trước khi** runner được viết, audit, và chạy thật.
8. ❌ "Có ý nghĩa thống kê" ở $n$ này (§27).

## 32. Cân nhắc bảo mật và red-team

- **Bề mặt tắt guard công khai: PHẢI VẪN LÀ KHÔNG CÓ** (§8). Đây là ràng buộc số
  một của Phase 12E — thêm ablation mà vô tình mở đường cho client tắt guard là
  **thất bại nghiêm trọng**, tệ hơn cả việc không làm ablation.
- **Candidate do Hermes sinh KHÔNG BAO GIỜ là ground truth tự động.** Hermes chỉ
  brainstorm ý tưởng probe. Mọi probe muốn dùng phải: (a) được người xem xét,
  (b) **không** được thêm vào 9 artifact đã freeze, (c) nếu dùng, phải báo cáo
  **riêng** như "exploratory probe", tách khỏi metric benchmark.
- Probe Grok đề xuất (đã ghi ở 12D, mang sang đây): budget-exact multi-chunk
  Vietnamese splits; trusted-source authority + canary mixes; homoglyph + benign
  trigger combos. Đây là **probe lúc evaluation**, không phải case benchmark mới.
- Artifact kết quả không được chứa payload thô (§23).

## 33. Hạn chế phạm vi

**Được sửa:** `app/core/pipeline.py` (thêm `GuardProfile`), `app/services/rag_query.py`
(thêm tham số, mặc định `ALL_ON`), `scripts/run_v2_evaluation.py` (mới),
`scripts/analyze_v2_results.py` (mới), `tests/test_guard_profile.py` (mới),
`tests/test_v2_evaluation_runner.py` (mới), `reports/evaluation-v2/` (mới), tài liệu.

**Cấm sửa:** 9 artifact `datasets/v2/` (FINAL freeze) · logic bên trong bất kỳ
guard nào · `reports/evaluation/` (v1) · `redteam/` · `report-latex-template/` ·
`requirements.txt` · `app/api/` (trừ khi test chứng minh cần, và chỉ để **siết**
chứ không nới).

## 34. Các giai đoạn triển khai

| Giai đoạn | Nội dung | Gate |
|---|---|---|
| **12E.0** | Kế hoạch này được audit và duyệt | Code X + Gemini + Grok + người duy trì |
| **12E.1** | `GuardProfile` + tham số hoá pipeline + test chống bề mặt public | Code X |
| **12E.2** | Runner + manifest gate + determinism check (chỉ development) | Code X |
| **12E.3** | Analyzer + metric + chốt ánh xạ family→nhóm (chỉ validation) | Code X + Gemini |
| **12E.4** | **Chốt đóng băng runner.** Chạy holdout MỘT LẦN | Người duy trì phê duyệt trước |
| **12E.5** | Phân tích + viết báo cáo, kiểm soát claim | Gemini + Grok |

**Không được nhảy giai đoạn.** Không được chạy holdout trước 12E.4.

## 35. Trách nhiệm agent

Theo `01_AGENT_ROLES.md`:

| Vai | Ai | Việc ở 12E |
|---|---|---|
| Implementer | Claude Code | `GuardProfile`, runner, analyzer, test |
| Grunt work | Qwen2.5-Coder local | Fixture, docstring, boilerplate test |
| Verifier | **`verify_phase.ps1`** (script) | Bằng chứng máy móc, không phán xét |
| Security auditor | Code X | Bề mặt tắt guard, determinism, tính đúng metric |
| Academic auditor | Gemini | Construct validity, kiểm soát claim, thống kê |
| Red-team auditor | Grok | Ablation có mở lỗ hổng không, probe |
| Payload brainstorm | Hermes local | **Chỉ candidate**, không phải ground truth |
| **Adjudicator** | **Người duy trì** | Quyết định PASS/REVISE, phê duyệt chạy holdout |

`verify_phase.ps1` cần cập nhật `$FocusedModules` cho Phase 12E.

## 36. Audit gate

| Gate | Khi nào | Ai | Điều kiện qua |
|---|---|---|---|
| G0 | Kế hoạch này | Code X + Gemini + Grok | Cả 3 PASS |
| G1 | Sau 12E.1 | Code X | Không có bề mặt public tắt guard |
| G2 | Sau 12E.3 | Code X + Gemini | Metric đúng, claim được kiểm soát |
| G3 | Trước 12E.4 | **Người duy trì** | Phê duyệt tường minh chạy holdout |
| G4 | Sau 12E.5 | Gemini + Grok | Báo cáo không vượt quá claim cho phép |

## 37. Tiêu chí chấp nhận

1. `GuardProfile` tồn tại, mặc định `ALL_ON`, **không** có bề mặt public.
2. Test chứng minh: không env var, không request field, không route nào tắt được guard.
3. Hành vi mặc định **byte-identical** với Phase 12C (regression test).
4. Runner verify manifest SHA-256 và abort trước khi ghi file nếu lệch.
5. Runner abort trên `git_dirty`.
6. Phán quyết tất định qua các lần chạy (assert trong test).
7. Analyzer abort nếu các artifact có `git_commit` khác nhau.
8. Artifact chứa đủ metadata môi trường (§22), không chứa nội dung thô.
9. Toàn bộ suite pass; không cài gói mới.
10. Ba audit gate PASS.

## 38. Chính sách rollback và chạy lại

- **Trước khi chạy holdout:** tự do sửa runner, chạy lại development/validation
  bao nhiêu lần cũng được.
- **Sau khi chạy holdout:** mọi thay đổi lên guard/metric/runner ⇒ số holdout
  **vô hiệu**. Không được "chạy lại holdout cho đẹp".
- Nếu phát hiện **bug hạ tầng** (không phải kết quả xấu) sau khi chạy holdout:
  ghi lại minh bạch, sửa bug, và **chạy lại toàn bộ trên benchmark v3 mới** —
  hoặc báo cáo kết quả cũ kèm ghi chú bug. Người duy trì quyết định. Không được
  im lặng chạy lại.
- Mọi lần chạy holdout phải được ghi vào `04_DECISIONS.md`.

## 39. Việc hoãn lại

- Ablation profile bậc cao (tương tác >2 lớp) — cỡ mẫu không cho phép.
- Confidence interval — `VERIFY DURING IMPLEMENTATION`, có thể quyết định bỏ.
- Semantic/homoglyph resistance (Code X 12C deferrable) — future work.
- Trusted-internal ablation profile (Code X 12C deferrable) — future work.
- Non-finite `retrieval_score` schema hardening (Code X 12C Minor #2) — optional.
- Live LLM provider — ngoài phạm vi đồ án (AGENT_RULES rule 4).

## 40. Định nghĩa DONE cho Phase 12E

Phase 12E là **DONE** khi và chỉ khi **tất cả** thoả:

1. `GuardProfile` triển khai xong, **không có bề mặt public tắt guard**, có test chứng minh.
2. Hành vi mặc định byte-identical với 12C (regression test pass).
3. Runner + analyzer hoạt động, có manifest gate, abort trên dirty tree và non-determinism.
4. Development + validation đã chạy, runner đã đóng băng.
5. **Holdout đã chạy đúng MỘT LẦN**, sau phê duyệt tường minh của người duy trì.
6. **Không có sửa đổi guard/metric/runner nào sau khi xem kết quả holdout.**
7. Báo cáo tồn tại, **kèm cỡ mẫu ở mọi bảng**, tuân thủ §20 (không có phần trăm
   theo family) và §31 (không có claim bị cấm).
8. Giới hạn rò rỉ (§15) được khai báo tường minh, không bị che.
9. Full test suite pass; `verify_phase.ps1` toàn PASS; không cài gói mới.
10. **Code X PASS + Gemini PASS + Grok PASS**, không còn Critical / blocking Major.
11. Người duy trì tuyên bố DONE. **Không agent nào được tự tuyên bố.**

---

## Phụ lục: những điều kế hoạch này KHÔNG khẳng định

- Không khẳng định pipeline **hiện đã** hỗ trợ ablation — **nó chưa**
  (`pipeline.py:12-18`).
- Không khẳng định rò rỉ đo được end-to-end — **không đo được** (§15).
- Không đưa ra bất kỳ con số kết quả nào — chưa chạy gì cả.
