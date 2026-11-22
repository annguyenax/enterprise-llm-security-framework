# P5 latency — mock-unguarded

Provider `mock` / model `mock-rag-guard-v1`; Semantic Judge LLM = `0`; commit `e0019857` (dirty); Intel64 Family 6 Model 191 Stepping 2, GenuineIntel (24 logical CPU).

## Tất cả request

| Stage | n | mean ms | p50 ms | p95 ms | p99 ms | max ms |
|---|---:|---:|---:|---:|---:|---:|
| e2e | 1275 | 16.79 | 16.40 | 22.56 | 27.92 | 37.80 |
| guard_overhead | 1275 | 0.01 | 0.01 | 0.01 | 0.02 | 0.12 |
| history_screen | 1275 | 0.01 | 0.01 | 0.01 | 0.02 | 0.12 |
| retrieval | 1275 | 2.82 | 2.31 | 6.05 | 8.28 | 9.69 |
| provider | 1275 | 0.01 | 0.00 | 0.01 | 0.02 | 0.19 |

## Request bị chặn trước LLM

| Stage | n | mean ms | p50 ms | p95 ms | p99 ms | max ms |
|---|---:|---:|---:|---:|---:|---:|

## Request đi tới LLM

| Stage | n | mean ms | p50 ms | p95 ms | p99 ms | max ms |
|---|---:|---:|---:|---:|---:|---:|
| e2e | 1275 | 16.79 | 16.40 | 22.56 | 27.92 | 37.80 |
| guard_overhead | 1275 | 0.01 | 0.01 | 0.01 | 0.02 | 0.12 |
| history_screen | 1275 | 0.01 | 0.01 | 0.01 | 0.02 | 0.12 |
| retrieval | 1275 | 2.82 | 2.31 | 6.05 | 8.28 | 9.69 |
| provider | 1275 | 0.01 | 0.00 | 0.01 | 0.02 | 0.19 |

p99 trong ngoặc = n < 100, nearest-rank p99 chỉ là max, không dùng làm số báo cáo.
`guard_overhead` = tổng các stage guard (không gồm retrieval và provider).
`semantic_judge_llm` lồng bên trong `semantic_input`/`semantic_output`.
