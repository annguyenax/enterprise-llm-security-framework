# P5 latency — mock-judge-off

Provider `mock` / model `mock-rag-guard-v1`; Semantic Judge LLM = `0`; commit `e0019857` (dirty); Intel64 Family 6 Model 191 Stepping 2, GenuineIntel (24 logical CPU).

## Tất cả request

| Stage | n | mean ms | p50 ms | p95 ms | p99 ms | max ms |
|---|---:|---:|---:|---:|---:|---:|
| e2e | 1275 | 17.10 | 16.68 | 22.65 | 27.82 | 55.60 |
| guard_overhead | 1275 | 0.53 | 0.42 | 1.21 | 1.39 | 1.74 |
| history_screen | 1275 | 0.01 | 0.01 | 0.01 | 0.02 | 0.06 |
| input_guard | 1275 | 0.17 | 0.14 | 0.35 | 0.47 | 1.18 |
| semantic_input | 693 | 0.13 | 0.12 | 0.20 | 0.24 | 0.30 |
| rag_context_guard | 648 | 0.53 | 0.37 | 0.96 | 1.20 | 1.41 |
| output_guard | 693 | 0.02 | 0.02 | 0.03 | 0.04 | 0.11 |
| retrieval | 1275 | 2.57 | 2.08 | 5.27 | 6.66 | 8.46 |
| provider | 693 | 0.01 | 0.00 | 0.01 | 0.01 | 0.02 |

## Request bị chặn trước LLM

| Stage | n | mean ms | p50 ms | p95 ms | p99 ms | max ms |
|---|---:|---:|---:|---:|---:|---:|
| e2e | 582 | 16.88 | 16.60 | 21.57 | 28.39 | 55.60 |
| guard_overhead | 582 | 0.26 | 0.22 | 0.41 | 0.61 | 1.19 |
| history_screen | 582 | 0.01 | 0.01 | 0.01 | 0.02 | 0.03 |
| input_guard | 582 | 0.25 | 0.21 | 0.40 | 0.60 | 1.18 |
| retrieval | 582 | 2.51 | 1.96 | 5.20 | 6.71 | 8.17 |

## Request đi tới LLM

| Stage | n | mean ms | p50 ms | p95 ms | p99 ms | max ms |
|---|---:|---:|---:|---:|---:|---:|
| e2e | 693 | 17.28 | 16.79 | 23.61 | 27.82 | 33.91 |
| guard_overhead | 693 | 0.76 | 0.62 | 1.28 | 1.52 | 1.74 |
| history_screen | 693 | 0.01 | 0.01 | 0.01 | 0.02 | 0.06 |
| input_guard | 693 | 0.11 | 0.11 | 0.17 | 0.20 | 0.25 |
| semantic_input | 693 | 0.13 | 0.12 | 0.20 | 0.24 | 0.30 |
| rag_context_guard | 648 | 0.53 | 0.37 | 0.96 | 1.20 | 1.41 |
| output_guard | 693 | 0.02 | 0.02 | 0.03 | 0.04 | 0.11 |
| retrieval | 693 | 2.62 | 2.17 | 5.33 | 6.51 | 8.46 |
| provider | 693 | 0.01 | 0.00 | 0.01 | 0.01 | 0.02 |

p99 trong ngoặc = n < 100, nearest-rank p99 chỉ là max, không dùng làm số báo cáo.
`guard_overhead` = tổng các stage guard (không gồm retrieval và provider).
`semantic_judge_llm` lồng bên trong `semantic_input`/`semantic_output`.
