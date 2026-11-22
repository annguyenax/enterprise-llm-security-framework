# P5 × P4 — Đánh giá hiệu năng & độ trễ cho SQL Guard và Indirect Result Guard (Nhà Mộc Việt)

## 1. Direct P2SQL & RBAC SQL Guard (`app.sql_agent.guard.evaluate_sql` — SQLite EXPLAIN + Authorizer AST)

| Tập mẫu | TP / Mal | FP / Ben | TPR (Recall) | FPR | F1 | Số lượt đo (`n`) | Latency p50 (ms) | Latency p95 (ms) | Latency p99 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `redteam/sql/p2sql-direct` + `benign` (69 mẫu) | 38/38 | 0/31 | **100.0%** | **0.0%** | **100.0%** | 345 | **0.49** | **0.64** | **0.73** |

## 2. Indirect P2SQL Data-Cell Result Guard (`app.sql_agent.result_guard.guard_rows` — RAG Context Guard + SQL Rules + DLP)

| Tập mẫu | TP / Mal | FP / Ben | TPR (Recall) | FPR | F1 | Số lượt đo (`n`) | Latency p50 (ms) | Latency p95 (ms) | Latency p99 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `indirect-rows` (Dev split) | 24/24 | 0/32 | **100.0%** | **0.0%** | — | 350 | **0.18** | **0.29** | **0.42** |
| `indirect-rows` (Holdout split) | 14/14 | 0/32 | **100.0%** | **0.0%** | — | 350 | **0.18** | **0.29** | **0.42** |
| `indirect-rows` (Tổng hợp 70 mẫu) | 38/38 | 0/32 | **100.0%** | **0.0%** | **100.0%** | 350 | **0.18** | **0.29** | **0.42** |
