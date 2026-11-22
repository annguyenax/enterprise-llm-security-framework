# P5 latency — mock-judge-on-e2b

Provider `mock` / model `mock-rag-guard-v1`; Semantic Judge LLM = `1`; commit `e0019857` (dirty); Intel64 Family 6 Model 191 Stepping 2, GenuineIntel (24 logical CPU).

## Tất cả request

| Stage | n | mean ms | p50 ms | p95 ms | p99 ms | max ms |
|---|---:|---:|---:|---:|---:|---:|
| e2e | 425 | 61.16 | 20.97 | 131.16 | 141.86 | 451.17 |
| guard_overhead | 425 | 43.94 | 0.73 | 110.89 | 121.42 | 438.84 |
| history_screen | 425 | 0.01 | 0.01 | 0.01 | 0.02 | 0.02 |
| input_guard | 425 | 0.18 | 0.15 | 0.35 | 0.41 | 0.47 |
| semantic_input | 231 | 79.90 | 96.52 | 114.03 | 130.11 | 438.66 |
| rag_context_guard | 210 | 0.62 | 0.48 | 1.13 | 1.18 | 1.21 |
| output_guard | 225 | 0.03 | 0.03 | 0.03 | 0.04 | 0.05 |
| retrieval | 425 | 2.96 | 2.52 | 5.98 | 7.21 | 9.65 |
| provider | 225 | 0.01 | 0.01 | 0.01 | 0.01 | 0.03 |
| semantic_judge_llm | 184 | 100.12 | 99.79 | 114.73 | 156.82 | 438.47 |

## Request bị chặn trước LLM

| Stage | n | mean ms | p50 ms | p95 ms | p99 ms | max ms |
|---|---:|---:|---:|---:|---:|---:|
| e2e | 200 | 21.30 | 16.24 | 25.58 | 141.86 | 451.17 |
| guard_overhead | 200 | 5.27 | 0.23 | 0.42 | 128.81 | 438.84 |
| history_screen | 200 | 0.01 | 0.01 | 0.01 | 0.02 | 0.02 |
| input_guard | 200 | 0.24 | 0.21 | 0.37 | 0.42 | 0.47 |
| semantic_input | 6 | 167.36 | 114.71 | 438.66 | (438.66) | 438.66 |
| retrieval | 200 | 2.67 | 2.14 | 5.55 | 7.39 | 9.65 |
| semantic_judge_llm | 6 | 167.17 | 114.58 | 438.47 | (438.47) | 438.47 |

## Request đi tới LLM

| Stage | n | mean ms | p50 ms | p95 ms | p99 ms | max ms |
|---|---:|---:|---:|---:|---:|---:|
| e2e | 225 | 96.59 | 114.40 | 133.07 | 135.50 | 176.37 |
| guard_overhead | 225 | 78.31 | 97.18 | 113.27 | 120.30 | 158.04 |
| history_screen | 225 | 0.01 | 0.01 | 0.01 | 0.01 | 0.02 |
| input_guard | 225 | 0.13 | 0.12 | 0.19 | 0.23 | 0.25 |
| semantic_input | 225 | 77.56 | 96.16 | 112.15 | 120.17 | 156.99 |
| rag_context_guard | 210 | 0.62 | 0.48 | 1.13 | 1.18 | 1.21 |
| output_guard | 225 | 0.03 | 0.03 | 0.03 | 0.04 | 0.05 |
| retrieval | 225 | 3.23 | 2.80 | 6.06 | 7.11 | 8.98 |
| provider | 225 | 0.01 | 0.01 | 0.01 | 0.01 | 0.03 |
| semantic_judge_llm | 178 | 97.86 | 99.77 | 113.24 | 120.06 | 156.82 |

p99 trong ngoặc = n < 100, nearest-rank p99 chỉ là max, không dùng làm số báo cáo.
`guard_overhead` = tổng các stage guard (không gồm retrieval và provider).
`semantic_judge_llm` lồng bên trong `semantic_input`/`semantic_output`.
