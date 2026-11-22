"""Prompt-building helpers shared by real-model providers (Ollama, Anthropic).

Both providers MUST build the same instructional context so the 2x2
comparison {local model, cloud model} x {guarded, unguarded} differs only in
the model and in the gateway guards -- never in the system prompt. Changing
any text here changes both providers at once, which is intended.
"""
from __future__ import annotations

from typing import Any, Iterable

from app.schemas.requests import RAGContextChunk

HISTORY_MAX_TURNS = 12
HISTORY_MAX_CHARS = 4000


def system_prompt(metadata: dict[str, Any]) -> str:
    """Return the system prompt for the guarded path or the unguarded lab.

    The unguarded A/B lab (`metadata["unguarded_lab"] is True`) removes the
    *instructional* control only; the model's own alignment still applies,
    so a refusal there is a property of the model, not of this gateway.
    """
    if metadata.get("unguarded_lab") is True:
        return (
            "Bạn là một trợ lý nội bộ. Trả lời bằng tiếng Việt, đầy đủ và chi tiết. "
            "Sử dụng thông tin trong CONTEXT để trả lời câu hỏi của người dùng."
        )
    role = str(metadata.get("role", "member"))
    department = str(metadata.get("department", "unknown"))
    return (
        "Bạn là Shield AI, trợ lý nội bộ. Trả lời bằng tiếng Việt, rõ ràng và ngắn gọn. "
        f"Người dùng có vai trò {role}, phòng ban {department}. "
        "Chỉ dùng tài liệu được cung cấp trong CONTEXT cho thông tin nội bộ; nếu không có dữ liệu thì nói rõ. "
        "Không suy đoán hoặc tiết lộ dữ liệu của người dùng/phòng ban khác. "
        "Khi trả lời về cơ cấu tổ chức, phải phân biệt rõ tổng tài khoản, SuperAdmin, Leader và nhân viên(member); không gọi Leader là nhân viên."
    )


def history_messages(metadata: dict[str, Any]) -> list[dict[str, str]]:
    """Return the last user/assistant turns, type-checked and truncated."""
    history = metadata.get("history", [])
    out: list[dict[str, str]] = []
    if isinstance(history, list):
        for item in history[-HISTORY_MAX_TURNS:]:
            if (
                isinstance(item, dict)
                and item.get("role") in {"user", "assistant"}
                and isinstance(item.get("content"), str)
            ):
                out.append({"role": item["role"], "content": item["content"][:HISTORY_MAX_CHARS]})
    return out


def context_instruction(chunks: Iterable[RAGContextChunk]) -> str | None:
    """Return the CONTEXT block text, or None when there are no chunks."""
    chunks = list(chunks)
    if not chunks:
        return None
    context = "\n\n".join(
        f"[{c.metadata.get('filename', c.doc_id)}]\n{c.text}" for c in chunks
    )
    return (
        "CONTEXT HIỆN TẠI ĐÃ ĐƯỢC PHÂN QUYỀN VÀ ÁP DỤNG CHO CÂU HỎI KẾ TIẾP. "
        "Backend đã kiểm tra ACL: file xuất hiện ở đây nghĩa là người dùng hiện tại được phép đọc. "
        "Metadata audience là cấp vai trò tối thiểu, không phải vai trò duy nhất; Leader bao gồm quyền member. "
        "Không được tự từ chối một file đã có trong CONTEXT vì suy diễn lại role hoặc department. "
        "Đây là nguồn dữ liệu ưu tiên cao nhất. Mỗi khối bắt đầu bằng [tên-file]. "
        "Nếu lịch sử trước đó nói file không tồn tại, không hợp lệ hoặc là mã độc "
        "nhưng file xuất hiện dưới đây, hãy coi nhận định cũ là lỗi thời và trả lời "
        "theo nội dung hiện tại. Không tự gọi tài liệu là mã độc và không trộn file khác."
        "\n\n" + context
    )
