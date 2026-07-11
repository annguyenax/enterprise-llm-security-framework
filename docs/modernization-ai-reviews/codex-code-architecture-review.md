No files were modified. The blueprint below is based on the current repository, including the untracked modernization reviews.

**Current Findings**

- [`ChatRequest`](D:/DoAnThucTap/enterprise-llm-security-framework/app/schemas/requests.py:31) accepts caller-supplied context, so retrieval provenance is not enforceable.
- [`run_chat()`](D:/DoAnThucTap/enterprise-llm-security-framework/app/services/gateway.py:74) is cohesive but should gain injected retrieval and guard-profile dependencies.
- [`_run_target_guard()`](D:/DoAnThucTap/enterprise-llm-security-framework/app/services/evaluation_runner.py:134) invokes one guard directly; it cannot support meaningful end-to-end ablation.
- Secret patterns are duplicated across RAG Guard, Output Guard, and audit logging.
- [`DocumentChunk.is_poisoned`](D:/DoAnThucTap/enterprise-llm-security-framework/app/services/dataset_loader.py:56) is benchmark ground truth. Runtime retrieval must never use that field to make security decisions.

## 1. Target Architecture V2

```text
Document ingest -> validation -> deterministic chunker -> ingestion scan
                -> SQLite document store + FTS5/BM25 index

RAG query -> Input Guard -> BM25 Retriever -> provenance/trust policy
          -> RAG Context Guard -> Mock Provider -> DLP/Output Guard
          -> response + structured audit event
```

Recommended core types:

- `Retriever` protocol: `upsert_documents()`, `search()`, `delete_document()`.
- `SQLiteBM25Retriever`: persistent lexical index using standard-library `sqlite3` and FTS5.
- `DocumentRecord`, `ChunkRecord`, `RetrievalHit`, `RetrievalResult`.
- `DocumentIngestionService`: validation, chunking, content hashing, transaction handling.
- `RAGQueryService`: retrieval followed by the existing guarded gateway.
- `GuardProfile`: enables/disables input, RAG, output and DLP layers for controlled ablation.
- `DLPScanner`: shared detectors, findings and redaction used by Output Guard and audit logger.

## 2. Implementation Options

| Option | Value | Cost and risk | Verdict |
|---|---|---|---|
| A. Lexical/BM25 | Adds genuine retrieval, explainable ranking and poisoning exposure measurement | Weak on paraphrases; FTS query syntax must be sanitized | **Best immediate option** |
| B. Lightweight vector | Better semantic matching | Model download, larger dependencies, embedding reproducibility and supply-chain risk | Later experiment |
| C. Hybrid | Best retrieval coverage and strongest thesis comparison | Score normalization, two indexes, tuning and larger evaluation burden | V3 after A |
| D. Mock retrieval + trust/DLP | Lowest implementation risk and improves leakage controls | Still cannot substantiate retrieval-specific claims | Useful only if schedule is extremely short |

## 3. Recommendation

Choose **Option A using SQLite FTS5/BM25**, then add small trust and DLP layers.

It provides actual offline retrieval without a framework, network access, model download or new heavy package. SQLite also gives persistence and transactional ingestion. Add a startup capability check for FTS5 and fail with a clear message if the local Python build lacks it.

Keep the mock provider. Real retrieval contributes more defensible value now than replacing a deterministic provider with a stochastic dependency.

## 4. File-Level Blueprint

| File | Purpose and structures | Required tests |
|---|---|---|
| `app/retrieval/models.py` | `DocumentRecord`, `ChunkRecord`, `RetrievalHit`, `RetrievalQuery` | Validation, stable IDs, metadata isolation |
| `app/retrieval/base.py` | `Retriever` protocol | Contract tests shared by implementations |
| `app/retrieval/sqlite_bm25.py` | SQLite schema, FTS5 index, parameterized CRUD and BM25 search | Ranking, tie ordering, upsert, rollback, malformed FTS input |
| `app/services/chunking.py` | Deterministic paragraph-aware chunker | Boundaries, overlap, empty/oversized text, repeatability |
| `app/services/ingestion.py` | Limits, hashing, deduplication, ingestion findings | Duplicate IDs, atomic batch failure, size limits |
| `app/services/rag_query.py` | Input guard → retrieval → RAG guard → existing gateway | Stop paths, top-k propagation, sanitized chunks |
| `app/guards/dlp_guard.py` | `DLPFinding`, detector IDs, classifications and redaction | Synthetic secrets, benign identifiers, overlapping findings |
| `app/core/pipeline.py` | `GuardProfile` and immutable layer configuration | Invalid profiles, full/default profile |
| `app/services/ablation_runner.py` | Scenario execution and profile comparison | Layer disabling, deterministic matrices, no provider/network calls |
| `app/services/evaluation_store.py` | Safely read approved generated summaries | Missing/malformed report, fixed-path enforcement |
| Existing config/schemas/routes | Retrieval path, top-k, request/response contracts and endpoints | Bounds, compatibility and API validation |
| Existing gateway/output/audit | Inject profile/retriever; delegate shared DLP redaction | Existing behavior unchanged under default profile |

`dataset_loader.py` should adapt loaded documents into `DocumentRecord`, but benchmark-only fields such as `is_poisoned` must remain outside the runtime index.

## 5. API Changes

- `POST /v1/documents/ingest`: JSON documents only; bounded batch size and text length; returns indexed, updated, quarantined and rejected counts.
- `POST /v1/rag/query`: accepts `query`, bounded `top_k`, and safe metadata; returns retrieval provenance plus the existing guard/provider response.
- `GET /v1/evaluation/summary`: reads a fixed generated artifact; it must not trigger evaluation or accept arbitrary filesystem paths.
- Preserve `/v1/gateway/chat` for direct-context regression tests and backward compatibility.
- Defer dashboard work. Swagger plus generated Markdown reports are sufficient until retrieval and evaluation are stable.

## 6. Evaluation Upgrade

Create a separate immutable `redteam/scenarios-v2.jsonl`; do not alter the existing 40 labels. Each scenario should carry query, candidate documents, expected relevant document IDs, poisoned document IDs, deterministic provider output and synthetic leakage canaries.

Ablation profiles:

`no_guards`, `input_only`, `rag_only`, `output_dlp_only`, `full`, and the three `full_minus_<layer>` profiles.

Report:

- Per-layer marginal contribution: full-system protected cases minus `full_minus_layer`.
- Unique catches, overlapping catches and decision-change matrices.
- Raw-provider leakage rate, returned-output leakage rate, redaction recall and benign over-redaction rate.
- Retrieval Recall@k, poisoned-hit rate at k, poisoned-context exposure after RAG Guard and clean-context retention.
- Keep `attack_success_proxy` explicitly decision-based unless a deterministic output scenario proves actual synthetic canary leakage.

## 7. Risks

- Raw user text passed to FTS `MATCH` can inject FTS operators even with SQL parameters; tokenize and quote accepted terms.
- Caller-provided trust metadata is spoofable. Trust must come from configured ingestion-source policy.
- SQLite global connections can fail under FastAPI threading; use short-lived connections, transactions and deterministic tie-breaking.
- Upsert bugs can leave stale FTS rows; test replacement and rollback.
- Character chunking can split attack indicators; move to paragraph-aware deterministic chunking.
- DLP rules can over-redact ordinary emails or identifiers; measure benign over-redaction separately.
- Vector dependencies introduce model-download, licensing, platform and reproducibility risks.
- Ablation on the current direct-guard benchmark would produce misleading contribution claims.
- A larger v2 benchmark must be versioned and evaluated as a new corpus, never presented as an extension of the original 40/40 result.

## 8. Incremental PR Plan

1. **PR1:** Extract retrieval models, deterministic chunker, `Retriever` protocol and compatibility adapters.
2. **PR2:** Add SQLite FTS5/BM25 store, ingestion service and `/v1/documents/ingest`.
3. **PR3:** Add `RAGQueryService`, `/v1/rag/query`, provenance responses and gateway integration.
4. **PR4:** Centralize DLP/redaction and add source trust policy without using benchmark labels.
5. **PR5:** Add v2 scenario runner, guard profiles, ablation and leakage/poisoning metrics.
6. **PR6:** Add read-only evaluation summary endpoint, documentation, evidence regeneration and optional latency measurement.

The strongest maintainable stopping point is PR5. A dashboard, vector retrieval and real LLM integration should remain separate, explicitly approved follow-up work.