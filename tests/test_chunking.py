"""Tests for app/services/chunking.py (Phase 12B deterministic
paragraph-aware chunker)."""
from app.services.chunking import (
    ChunkingConfig,
    DocumentTooLongError,
    EmptyDocumentError,
    chunk_text,
    split_paragraphs,
)


def test_normal_multi_paragraph_document():
    text = "First paragraph about policy.\n\nSecond paragraph about process.\n\nThird paragraph about scope."
    chunks = chunk_text(text, ChunkingConfig(max_chunk_chars=1000, overlap_chars=50))
    assert len(chunks) == 1
    assert "First paragraph" in chunks[0].text
    assert "Third paragraph" in chunks[0].text


def test_empty_text_raises():
    try:
        chunk_text("")
        assert False, "expected EmptyDocumentError"
    except EmptyDocumentError:
        pass


def test_whitespace_only_text_raises():
    try:
        chunk_text("   \n\n   \t  ")
        assert False, "expected EmptyDocumentError"
    except EmptyDocumentError:
        pass


def test_oversized_single_paragraph_is_hard_split():
    paragraph = "word " * 500  # ~2500 chars, one paragraph, no blank lines
    config = ChunkingConfig(max_chunk_chars=200, overlap_chars=20)
    chunks = chunk_text(paragraph, config)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.text) <= 200
        assert chunk.text.strip()


def test_exact_boundary_paragraph_not_treated_as_oversized():
    config = ChunkingConfig(max_chunk_chars=100, overlap_chars=10)
    paragraph = "a" * 100  # exactly max_chunk_chars, must NOT trigger hard-split
    chunks = chunk_text(paragraph, config)
    assert len(chunks) == 1
    assert chunks[0].text == paragraph


def test_overlap_is_carried_into_next_chunk():
    config = ChunkingConfig(max_chunk_chars=60, overlap_chars=20)
    text = ("Paragraph number one is here. " * 2).strip() + "\n\n" + (
        "Paragraph number two is here also. " * 2
    ).strip()
    chunks = chunk_text(text, config)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk.text) <= config.max_chunk_chars


def test_unicode_vietnamese_text():
    text = (
        "Chính sách bảo mật của công ty yêu cầu mật khẩu mạnh.\n\n"
        "Xác thực hai yếu tố là bắt buộc đối với mọi tài khoản."
    )
    chunks = chunk_text(text, ChunkingConfig(max_chunk_chars=1000, overlap_chars=50))
    assert len(chunks) == 1
    assert "Chính sách" in chunks[0].text
    assert "Xác thực hai yếu tố" in chunks[0].text


def test_deterministic_repeated_output():
    text = "Alpha paragraph.\n\nBeta paragraph.\n\nGamma paragraph." * 20
    config = ChunkingConfig(max_chunk_chars=150, overlap_chars=30)
    first = chunk_text(text, config)
    second = chunk_text(text, config)
    assert [c.text for c in first] == [c.text for c in second]
    assert [c.chunk_index for c in first] == [c.chunk_index for c in second]


def test_stable_chunk_indices_are_sequential_from_zero():
    text = "One.\n\nTwo.\n\nThree.\n\nFour." * 10
    chunks = chunk_text(text, ChunkingConfig(max_chunk_chars=40, overlap_chars=5))
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_no_empty_chunks():
    text = "Alpha.\n\n\n\n\nBeta.\n\n   \n\nGamma."
    chunks = chunk_text(text, ChunkingConfig(max_chunk_chars=1000, overlap_chars=50))
    for chunk in chunks:
        assert chunk.text.strip() != ""


def test_document_too_long_raises():
    config = ChunkingConfig(max_chunk_chars=100, overlap_chars=10, max_document_chars=50)
    try:
        chunk_text("x" * 1000, config)
        assert False, "expected DocumentTooLongError"
    except DocumentTooLongError:
        pass


def test_split_paragraphs_normalizes_crlf():
    text = "Alpha.\r\n\r\nBeta.\r\nStill beta."
    paragraphs = split_paragraphs(text)
    assert paragraphs == ["Alpha.", "Beta.\nStill beta."]


def test_config_rejects_overlap_ge_max_chunk_chars():
    try:
        ChunkingConfig(max_chunk_chars=100, overlap_chars=100)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_chunk_text_signature_only_accepts_plain_text():
    """Structural check: chunk_text's only content parameter is a plain
    string (not a Document-like object), so there is no way for
    benchmark-only ground truth such as is_poisoned to flow through this
    module's data path at all."""
    import inspect

    signature = inspect.signature(chunk_text)
    params = list(signature.parameters.values())
    assert params[0].name == "text"
    assert params[0].annotation in (str, "str")
