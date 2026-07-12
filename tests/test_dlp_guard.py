"""Tests for app/guards/dlp_guard.py (Phase 12C centralized DLP)."""
from __future__ import annotations

from app.guards import output_guard
from app.services import audit_logger
from app.guards.dlp_guard import (
    AWS_KEY_PATTERN,
    FAKE_SECRET_PATTERN,
    GITHUB_TOKEN_PATTERN,
    OPENAI_KEY_PATTERN,
    OUTPUT_GUARD_REALISTIC_SECRET_PATTERN,
    PRIVATE_KEY_BLOCK_PATTERN,
    scan_and_redact,
)


def test_no_secret_returns_text_unchanged_with_no_findings():
    result = scan_and_redact("The warranty period is two years.", max_chars=1000)
    assert result.redacted_text == "The warranty period is two years."
    assert result.findings == ()
    assert result.redaction_count == 0
    assert result.truncated is False


def test_single_secret_is_redacted():
    result = scan_and_redact("Here is the key: sk-abcdefghij1234567890", max_chars=1000)
    assert "sk-abcdefghij1234567890" not in result.redacted_text
    assert "[REDACTED]" in result.redacted_text
    assert result.redaction_count == 1
    assert result.findings[0].category == "api_key"


def test_multiple_secret_types_all_redacted_with_separate_findings():
    text = (
        "canary: FAKE-SECRET-0000-EXAMPLE-DO-NOT-USE\n"
        "openai: sk-abcdefghij1234567890\n"
        "aws: AKIAABCDEFGHIJKLMNOP\n"
        "github: ghp_abcdefghij1234567890ab\n"
        "bearer: Bearer abcdef1234567890xyz\n"
        "password: password=SuperSecretValue123\n"
    )
    result = scan_and_redact(text, max_chars=2000)
    categories = {f.category for f in result.findings}
    assert categories == {
        "canary_secret", "api_key", "bearer_token", "secret_assignment",
    }
    assert "FAKE-SECRET" not in result.redacted_text
    assert "sk-abcdefghij1234567890" not in result.redacted_text
    assert "AKIAABCDEFGHIJKLMNOP" not in result.redacted_text
    assert "ghp_abcdefghij1234567890ab" not in result.redacted_text
    assert "Bearer abcdef1234567890xyz" not in result.redacted_text
    assert "SuperSecretValue123" not in result.redacted_text
    assert result.redaction_count == 6


def test_repeated_secret_counted_and_redacted_every_occurrence():
    text = "sk-abcdefghij1234567890 appears twice: sk-abcdefghij1234567890"
    result = scan_and_redact(text, max_chars=1000)
    assert "sk-" not in result.redacted_text
    api_key_findings = [f for f in result.findings if f.category == "api_key"]
    assert len(api_key_findings) == 1
    assert api_key_findings[0].count == 2
    assert result.redaction_count == 2


def test_private_key_block_fully_redacted_including_end_marker():
    text = (
        "before\n"
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEAtESTKEYDATAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\n"
        "-----END RSA PRIVATE KEY-----\n"
        "after"
    )
    result = scan_and_redact(text, max_chars=2000)
    assert "MIIEowIBAAKCAQEA" not in result.redacted_text
    assert "-----BEGIN" not in result.redacted_text
    assert "-----END" not in result.redacted_text
    assert "before" in result.redacted_text
    assert "after" in result.redacted_text
    assert any(f.category == "private_key" for f in result.findings)


def test_benign_identifiers_are_not_over_redacted():
    benign = (
        "Please update your password before Friday. "
        "The api key field is required on the settings page. "
        "Order number: order-2024-000123. "
        "Contact support at help@example.com for the secret menu item."
    )
    result = scan_and_redact(benign, max_chars=2000)
    assert result.redacted_text == benign
    assert result.findings == ()
    assert result.redaction_count == 0


def test_vietnamese_surrounding_text_is_preserved_and_secret_still_redacted():
    text = (
        "Chính sách bảo hành sản phẩm: khóa API của bạn là sk-abcdefghij1234567890, "
        "vui lòng giữ bí mật thông tin này."
    )
    result = scan_and_redact(text, max_chars=2000)
    assert "sk-abcdefghij1234567890" not in result.redacted_text
    assert "Chính sách bảo hành sản phẩm" in result.redacted_text
    assert "vui lòng giữ bí mật thông tin này" in result.redacted_text
    assert result.redaction_count == 1


def test_bounded_input_size_truncates_inspection():
    long_prefix = "x" * 50
    secret_beyond_bound = "sk-abcdefghij1234567890"
    text = long_prefix + secret_beyond_bound
    result = scan_and_redact(text, max_chars=10)
    assert result.truncated is True
    # The secret sits beyond the inspected window and is passed through
    # unredacted -- a documented, bounded-input-size limitation, not a bug.
    assert secret_beyond_bound in result.redacted_text


def test_findings_never_carry_the_raw_secret_value():
    result = scan_and_redact("sk-abcdefghij1234567890", max_chars=1000)
    for finding in result.findings:
        assert not hasattr(finding, "value")
        assert "sk-abcdefghij1234567890" not in str(finding)


# -- Consolidation parity: behavior must be byte-identical after Phase --
# -- 12C centralized these patterns into this module -------------------


def test_output_guard_realistic_secret_pattern_is_shared_and_case_insensitive():
    """app.guards.output_guard now imports this exact pattern instead of
    redefining its own copy -- confirm the shared pattern still matches
    the same case-insensitive behavior the original inline regex had
    (original output_guard rules were all compiled with re.IGNORECASE via
    its local _rx() helper)."""
    assert output_guard.FAKE_SECRET_PATTERN is FAKE_SECRET_PATTERN
    assert OUTPUT_GUARD_REALISTIC_SECRET_PATTERN.search("-----begin rsa private key-----") is not None


def test_output_guard_redaction_unchanged_after_consolidation():
    """Fixture-based parity check: the existing output_guard.evaluate_output
    behavior on its own documented fixtures is unchanged now that it
    delegates to app.guards.dlp_guard for its shared patterns."""
    fake_secret_result = output_guard.evaluate_output(
        "Sure, here is the value: FAKE-SECRET-0000-EXAMPLE-DO-NOT-USE"
    )
    assert fake_secret_result.decision.value == "sanitize"
    assert "FAKE-SECRET-0000-EXAMPLE" not in (fake_secret_result.sanitized_text or "")

    realistic_key_result = output_guard.evaluate_output("here is sk-abcdefghij1234567890 for you")
    assert realistic_key_result.decision.value == "block"

    private_key_result = output_guard.evaluate_output(
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEow==\n"
    )
    assert private_key_result.decision.value == "block"

    benign_result = output_guard.evaluate_output("The warranty period is two years.")
    assert benign_result.decision.value == "allow"


def test_audit_logger_redaction_unchanged_after_consolidation():
    """audit_logger._redact_secrets now sources its five patterns from
    app.guards.dlp_guard instead of a locally-defined tuple; behavior on
    every previously-covered format must be unchanged."""
    samples = {
        "FAKE-SECRET-0000-EXAMPLE-DO-NOT-USE": True,
        "sk-abcdefghij1234567890": True,
        "AKIAABCDEFGHIJKLMNOP": True,
        "ghp_abcdefghij1234567890ab": True,
        "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----": True,
        "an ordinary sentence with no secrets": False,
    }
    for sample, should_redact in samples.items():
        redacted = audit_logger._redact_secrets(sample)
        if should_redact:
            assert redacted != sample, f"expected {sample!r} to be redacted"
            assert "[REDACTED]" in redacted
        else:
            assert redacted == sample


def test_dlp_patterns_are_the_single_source_audit_logger_now_uses():
    assert audit_logger._SECRET_PATTERNS == (
        FAKE_SECRET_PATTERN,
        OPENAI_KEY_PATTERN,
        AWS_KEY_PATTERN,
        GITHUB_TOKEN_PATTERN,
        PRIVATE_KEY_BLOCK_PATTERN,
    )
