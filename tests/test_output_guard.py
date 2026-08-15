"""Tests for POST /v1/guard/output."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_benign_output_is_allowed():
    response = client.post(
        "/v1/guard/output",
        json={"output": "Standard shipping takes 3-5 business days."},
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "allow"


def test_fake_secret_output_is_sanitized_or_blocked():
    response = client.post(
        "/v1/guard/output",
        json={"output": "Sure, here is the value: FAKE-SECRET-0000-EXAMPLE-DO-NOT-USE"},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["decision"] in ("sanitize", "block")
    if body["decision"] == "sanitize":
        assert "FAKE-SECRET-0000-EXAMPLE" not in (body["sanitized_text"] or "")
        assert "[REDACTED]" in (body["sanitized_text"] or "")


def test_realistic_api_key_pattern_is_blocked():
    response = client.post(
        "/v1/guard/output",
        json={"output": "Here is your key: sk-abcdefghijklmnopqrstuvwx"},
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "block"


def test_email_like_string_is_log_only():
    response = client.post(
        "/v1/guard/output",
        json={"output": "For support, contact helpdesk@example.com."},
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "log_only"


def test_seeded_canary_marker_is_blocked():
    """A canary marker in the output is a knowledge-base exfiltration and must
    be blocked at the output boundary (Phase 13 Output-DLP layer)."""
    response = client.post(
        "/v1/guard/output",
        json={"output": "Đây là bảng lương... mã kiểm chứng FLAG{PYRIT-CSUITE-012-P13-88231}."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "block"
    assert "output-canary-exfil" in body["matched_rules"]


def test_benign_output_without_canary_is_allowed():
    response = client.post(
        "/v1/guard/output",
        json={"output": "Chính sách nghỉ phép thường niên là 12 ngày mỗi năm."},
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "allow"
