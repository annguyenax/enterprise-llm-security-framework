# P5-W3 — Kết quả chạy trực tiếp Garak (`v0.17.1`) & PyRIT Adaptive Multi-Turn vào API

Đáp ứng nhận xét số 3 của giảng viên (*"Chưa chạy trực tiếp công cụ độc lập garak, PyRIT gốc vào endpoint `/v1/rag/query`*):

## 1. Chạy trực tiếp NVIDIA `garak v0.17.1` qua HTTP REST vào `/v1/rag/query` và `/v1/gateway/chat`

| Endpoint | Probe Garak gốc | Tổng probe | Bị từ chối bởi giới hạn độ dài schema (>2000 ký tự) | Hợp lệ đi vào Guard | Guard chặn (Input/Context) | Tỉ lệ Guard chặn (trên mẫu hợp lệ) | Lọt qua Guard tới Retrieval/Provider |
|---|---|---:|---:|---:|---:|---:|---:|
| `POST /v1/rag/query` | `dan.DanInTheWild` | 256 | 96 | 160 | **33** | **20.6%** | 127 |
| `POST /v1/rag/query` | `encoding.InjectBase64` | 256 | 0 | 256 | **0** | **0.0%** | 256 |
| `POST /v1/rag/query` | `latentinjection.LatentJailbreak` | 256 | 0 | 256 | **0** | **0.0%** | 256 |
| `POST /v1/rag/query` | `promptinject.HijackHateHumans` | 256 | 0 | 256 | **205** | **80.1%** | 51 |
| `POST /v1/gateway/chat` | `dan.DanInTheWild` | 256 | 40 | 216 | **105** | **48.6%** | 111 |
| `POST /v1/gateway/chat` | `encoding.InjectBase64` | 256 | 0 | 256 | **0** | **0.0%** | 256 |
| `POST /v1/gateway/chat` | `latentinjection.LatentJailbreak` | 256 | 0 | 256 | **0** | **0.0%** | 256 |
| `POST /v1/gateway/chat` | `promptinject.HijackHateHumans` | 256 | 0 | 256 | **198** | **77.3%** | 58 |

## 2. PyRIT-style Converter Matrix (35 biến thể mã hóa/biến đổi prompt trên 5 mục tiêu tấn công)

| Converter (biến đổi payload) | Tổng | Rule-Only chặn | Rule-Only lọt Guard | Rule + Judge (`gemma4:e2b`) chặn | Rule + Judge lọt Guard | Rò rỉ canary/mục tiêu |
|---|---:|---:|---:|---:|---:|---:|
| `baseline_direct` | 5 | 4/5 | **1/5** | 5/5 | **0/5** | 0/5 |
| `base64_converter` | 5 | 0/5 | **5/5** | 3/5 | **2/5** | 0/5 |
| `rot13_converter` | 5 | 0/5 | **5/5** | 0/5 | **5/5** | 0/5 |
| `leetspeak_converter` | 5 | 1/5 | **4/5** | 5/5 | **0/5** | 0/5 |
| `zero_width_perturbation` | 5 | 4/5 | **1/5** | 5/5 | **0/5** | 0/5 |
| `academic_audit_framing` | 5 | 4/5 | **1/5** | 5/5 | **0/5** | 0/5 |
| `json_payload_encapsulation` | 5 | 4/5 | **1/5** | 5/5 | **0/5** | 0/5 |

## 3. PyRIT-style Adaptive Multi-Turn (Attacker LLM tự động viết lại prompt qua 4 lượt chat khi thấy bị chặn)

| Cấu hình phòng thủ | Số mục tiêu (Objectives) | Bị chặn ở Lượt 1 (Template tĩnh) | Attacker thích nghi vượt qua Input Guard ở lượt 2–4 | Rò rỉ dữ liệu mục tiêu/canary |
|---|---:|---:|---:|---:|
| **Shield AI (Rule-Only, Judge OFF)** | 5 | 4/5 (80%) | **5/5** | 0/5 |
| **Shield AI (Rule + Semantic Judge ON)** | 5 | 5/5 (100%) | **5/5** | 0/5 |
