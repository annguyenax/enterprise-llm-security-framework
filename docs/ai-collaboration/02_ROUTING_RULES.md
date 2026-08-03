# Routing Rules

Task loại nào thì gửi model nào. Mục tiêu: **model mạnh chỉ dùng khi thật sự
cần**, phần còn lại đẩy sang model rẻ hoặc local.

## Bảng định tuyến

| Loại task | Model | Kênh | Vì sao |
|---|---|---|---|
| Plan một phase mới | Claude Code, hoặc DeepSeek-R1 | Claude Code / Continue | Cần hiểu ngữ cảnh dài, ràng buộc chéo |
| Sửa logic guard / validator / benchmark | **Claude Code** | Claude Code | Lỗi ở đây là loại invariant tinh vi; model nhỏ bỏ sót |
| Viết test số lượng lớn, fixture, parametrize | DeepSeek Coder | Continue | Cơ học, rẻ, dễ kiểm chứng bằng pytest |
| Docstring, comment, format, rename | Qwen2.5-Coder local | Continue + Ollama | Miễn phí, offline, rủi ro bằng 0 |
| Đọc/tóm tắt tài liệu dài (methodology, ADR) | Gemini 3 Pro | Continue | Context 1M token |
| Tra cứu nhanh, hỏi đáp ngắn | Gemini 3 Flash | Continue | Rẻ, nhanh |
| **Audit kỹ thuật (gate)** | **Code X** | Web/CLI riêng | Phải là model KHÁC implementer |
| **Audit học thuật (gate)** | **Gemini** | Web riêng | Phải là model KHÁC implementer |
| **Audit red-team (gate)** | **Grok** | Web riêng | Phải là model KHÁC implementer |
| Sinh payload tấn công cho probe 12E | Hermes local | Ollama | Không từ chối nội dung adversarial; chạy offline |
| Chạy test / hash / determinism | **KHÔNG DÙNG LLM** | `verify_phase.ps1` | Script không ảo giác số liệu |

## Quy tắc chi phí

1. **Fallback theo chiều rẻ → mạnh**, không phải mạnh → rẻ. Thử DeepSeek trước;
   chỉ leo lên Claude khi DeepSeek bí.
2. **Không nạp cả repo.** Continue phải scope theo file/symbol. Cấm `cat` hàng
   loạt file hoặc `ls -R` toàn cây.
3. **Không nhồi transcript.** Agent mới đọc `00_PROJECT_STATE.md` + handoff
   YAML, không đọc lịch sử chat.
4. **Ép output ngắn** cho task cơ học. Không cần giải thích dài dòng khi đang
   sinh 20 fixture giống nhau.

## Quy tắc bảo mật (bắt buộc)

- **API key: chỉ qua biến môi trường.** `~/.continue/config.yaml` dùng
  `${{ env.DEEPSEEK_API_KEY }}`, không hardcode. Key từng bị lộ một lần trong
  file này — xem `04_DECISIONS.md`.
- **Không dùng router bên thứ ba** (OmniRoute / 9Router) để truy cập miễn phí
  model trả phí. Lý do đầy đủ trong `04_DECISIONS.md`.
- **Không bật prompt compression** (RTK/Caveman/LLMLingua) cho prompt chứa code
  hoặc diff. Compression bỏ token nó cho là dư thừa — với code, nó có thể lặng
  lẽ cắt mất một điều kiện, và bạn sẽ audit một đoạn code không tồn tại.
  Chỉ bật cho văn xuôi dài thuần tuý.
- **Code nhạy cảm không gửi cloud** nếu có thể xử lý bằng model local.

## Chi phí tham khảo

DeepSeek rẻ hơn Claude khoảng một bậc độ lớn cho cùng lượng token. Chiến lược:
để DeepSeek/local gánh khối lượng (viết test, docstring, refactor cơ học), giữ
Claude cho phần cần độ chính xác cao (logic guard, validator, audit resolution).
Ba auditor gate chạy qua giao diện web riêng nên không tính vào token của
Continue.
