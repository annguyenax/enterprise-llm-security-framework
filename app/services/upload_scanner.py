"""Pre-parse upload security checks for the workspace document endpoint.

This is a deterministic, dependency-free scanner for the lab-scale PoC.  It
closes format-confusion and obvious executable-content paths before any
parser or persistence code sees the bytes.  It is deliberately exposed
through a small protocol so a deployment can replace or chain it with a real
antivirus engine without coupling that engine to the HTTP route.

It is not a signature database, sandbox, or substitute for an antivirus.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


DOCUMENT_TEXT_SUFFIXES = frozenset(
    {".txt", ".md", ".csv", ".json", ".jsonl", ".html", ".htm"}
)
CODE_SUFFIXES = frozenset({".py", ".js", ".ts", ".sh", ".ps1", ".bat", ".cmd"})
TEXT_SUFFIXES = DOCUMENT_TEXT_SUFFIXES | CODE_SUFFIXES

# Signatures are checked on the original bytes, so changing only the filename
# cannot turn an executable into an accepted text document.
EXECUTABLE_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"MZ", "windows-pe"),
    (b"\x7fELF", "elf"),
    (b"\xfe\xed\xfa\xce", "mach-o"),
    (b"\xce\xfa\xed\xfe", "mach-o"),
    (b"\xfe\xed\xfa\xcf", "mach-o"),
    (b"\xcf\xfa\xed\xfe", "mach-o"),
)

BINARY_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"PK\x03\x04", "zip"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"Rar!\x1a\x07", "rar"),
    (b"7z\xbc\xaf\x27\x1c", "7zip"),
)

SYSTEM_CODE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:os\.system|subprocess\.(?:run|popen|call|check_output))\s*\(", re.I),
    re.compile(r"\b(?:cmd(?:\.exe)?\s*/c|powershell(?:\.exe)?\b|invoke-expression\b|start-process\b)", re.I),
    re.compile(r"\b(?:child_process\.(?:exec|spawn)|require\s*\(\s*['\"]child_process['\"]\s*\))", re.I),
    re.compile(r"\bRuntime\.getRuntime\s*\(\s*\)\.exec\s*\(", re.I),
    re.compile(r"^\s*#!\s*/(?:usr/)?bin/(?:ba|z|k)?sh\b", re.I | re.M),
)

# A process API alone is not malicious: build scripts, deployment helpers,
# and code documentation use them legitimately. Block only high-confidence
# harmful behavior, while reporting benign code as ``system-code``.
DANGEROUS_CODE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "encoded-or-dynamic-command",
        re.compile(
            r"\b(?:powershell(?:\.exe)?\s+-(?:encodedcommand|enc)\b|invoke-expression\b)",
            re.I,
        ),
    ),
    (
        "destructive-system-command",
        re.compile(
            r"\b(?:rm\s+-[a-z]*r[a-z]*f[a-z]*\s+[/~]"
            r"|remove-item\b[^\r\n]{0,100}-(?:recurse|force)\b"
            r"|(?:del|rmdir|rd)\s+/[sq]\b"
            r"|format\s+[a-z]:|mkfs(?:\.[a-z0-9]+)?\b"
            r"|shutdown\s+/(?:s|r)\b)",
            re.I,
        ),
    ),
    (
        "download-and-execute",
        re.compile(
            r"(?:curl|wget)\b[^\r\n|]{0,180}\|\s*(?:ba)?sh\b"
            r"|invoke-webrequest\b[^\r\n]{0,180}\|\s*invoke-expression\b",
            re.I,
        ),
    ),
    (
        "credential-or-security-control-tampering",
        re.compile(
            r"\b(?:mimikatz|sekurlsa::logonpasswords|set-mppreference\s+-disablerealtimemonitoring\s+\$?true)\b",
            re.I,
        ),
    ),
)

ACTIVE_HTML_PATTERN = re.compile(
    r"<\s*(?:script|iframe|object|embed|applet)\b|\bon\w+\s*=|javascript\s*:",
    re.I,
)

ACTIVE_PDF_PATTERN = re.compile(
    rb"/S\s*/(?:JavaScript|Launch)\b|/JavaScript\s*<<|/EmbeddedFile\b",
    re.I,
)


@dataclass(frozen=True)
class UploadScanResult:
    allowed: bool
    engine: str
    rule_id: str | None = None
    reason: str | None = None
    detected_type: str | None = None
    checks: tuple[dict[str, object], ...] = ()


class UploadScanner(Protocol):
    """Seam for chaining a real antivirus scanner in a deployment."""

    def scan(self, filename: str, content: bytes) -> UploadScanResult: ...


class BuiltinUploadScanner:
    engine = "builtin-upload-policy-v1"

    def scan(self, filename: str, content: bytes) -> UploadScanResult:
        suffix = Path(filename).suffix.lower()

        for signature, detected_type in EXECUTABLE_SIGNATURES:
            if content.startswith(signature):
                return self._blocked(
                    "executable-signature",
                    "Tệp có chữ ký của định dạng thực thi và không được phép tải lên.",
                    detected_type,
                )

        for signature, detected_type in BINARY_SIGNATURES:
            if content.startswith(signature):
                return self._blocked(
                    "binary-format-mismatch",
                    "Nội dung nhị phân không khớp với định dạng tài liệu được phép.",
                    detected_type,
                )

        pdf_header_offset = content[:1024].find(b"%PDF-")
        if suffix == ".pdf" and pdf_header_offset < 0:
            return self._blocked(
                "invalid-pdf-signature",
                "Tệp PDF không có chữ ký PDF hợp lệ.",
                "unknown",
            )
        if suffix != ".pdf" and pdf_header_offset >= 0:
            return self._blocked(
                "pdf-extension-mismatch",
                "Nội dung PDF phải sử dụng phần mở rộng .pdf.",
                "pdf",
            )

        if suffix in TEXT_SUFFIXES:
            if b"\x00" in content:
                return self._blocked(
                    "nul-byte-in-text",
                    "Tệp văn bản chứa byte NUL hoặc nội dung nhị phân.",
                    "binary",
                )
            decoded = content.decode("utf-8", errors="ignore")
            if suffix in {".html", ".htm"} and ACTIVE_HTML_PATTERN.search(decoded):
                return self._blocked(
                    "active-html-content",
                    "HTML chứa nội dung chủ động hoặc mã script không được phép.",
                    "active-html",
                )
            for rule_id, pattern in DANGEROUS_CODE_PATTERNS:
                if pattern.search(decoded):
                    return self._blocked(
                        rule_id,
                        "Phát hiện mã hệ thống có hành vi nguy hiểm rõ ràng.",
                        "dangerous-system-code",
                    )

            code_detected = suffix in CODE_SUFFIXES or any(
                pattern.search(decoded) for pattern in SYSTEM_CODE_PATTERNS
            )
        else:
            code_detected = False

        if suffix == ".pdf" and ACTIVE_PDF_PATTERN.search(content):
            return self._blocked(
                "active-pdf-content",
                "PDF chứa JavaScript, Launch action hoặc tệp nhúng không được phép.",
                "active-pdf",
            )

        detected_type = "pdf" if suffix == ".pdf" else ("system-code" if code_detected else "text")
        return UploadScanResult(allowed=True, engine=self.engine, detected_type=detected_type)

    def _blocked(
        self, rule_id: str, reason: str, detected_type: str
    ) -> UploadScanResult:
        return UploadScanResult(
            allowed=False,
            engine=self.engine,
            rule_id=rule_id,
            reason=reason,
            detected_type=detected_type,
        )


_DEFAULT_SCANNER: UploadScanner = BuiltinUploadScanner()


def scan_upload(filename: str, content: bytes) -> UploadScanResult:
    """Scan bytes with built-in policy and an optional local ClamAV process."""
    builtin = _DEFAULT_SCANNER.scan(filename, content)
    builtin_check = {
        "stage": "upload_scanner",
        "engine": builtin.engine,
        "decision": "allow" if builtin.allowed else "block",
        "rule_ids": [builtin.rule_id] if builtin.rule_id else [],
        "reasons": [builtin.reason] if builtin.reason else [],
        "detected_type": builtin.detected_type,
    }
    if not builtin.allowed:
        return UploadScanResult(**{**builtin.__dict__, "checks": (builtin_check,)})

    mode = os.getenv("UPLOAD_ANTIVIRUS_MODE", "optional").strip().lower()
    if mode not in {"off", "optional", "required"}:
        return UploadScanResult(
            allowed=False,
            engine="antivirus-configuration",
            rule_id="invalid-antivirus-mode",
            reason="Cấu hình antivirus không hợp lệ; tệp bị từ chối an toàn.",
            detected_type=builtin.detected_type,
            checks=(builtin_check, {
                "stage": "antivirus", "engine": "clamav", "decision": "block",
                "rule_ids": ["invalid-antivirus-mode"],
                "reasons": ["UPLOAD_ANTIVIRUS_MODE phải là off, optional hoặc required."],
            }),
        )
    if mode == "off":
        return UploadScanResult(**{**builtin.__dict__, "checks": (builtin_check, {
            "stage": "antivirus", "engine": "clamav", "decision": "disabled",
            "rule_ids": [], "reasons": ["ClamAV đang tắt bởi cấu hình."],
        })})

    antivirus = _scan_with_clamav(filename, content)
    antivirus_check = {
        "stage": "antivirus",
        "engine": antivirus.engine,
        "decision": "allow" if antivirus.allowed else "block",
        "rule_ids": [antivirus.rule_id] if antivirus.rule_id else [],
        "reasons": [antivirus.reason] if antivirus.reason else [],
    }
    unavailable = antivirus.rule_id in {"clamav-unavailable", "clamav-error"}
    if unavailable and mode == "optional":
        antivirus_check["decision"] = "unavailable"
        return UploadScanResult(**{**builtin.__dict__, "checks": (builtin_check, antivirus_check)})
    if not antivirus.allowed:
        return UploadScanResult(
            allowed=False,
            engine=antivirus.engine,
            rule_id=antivirus.rule_id,
            reason=antivirus.reason,
            detected_type=builtin.detected_type,
            checks=(builtin_check, antivirus_check),
        )
    return UploadScanResult(**{**builtin.__dict__, "checks": (builtin_check, antivirus_check)})


def _scan_with_clamav(filename: str, content: bytes) -> UploadScanResult:
    """Scan one temporary file without invoking a command shell."""
    configured = os.getenv("CLAMAV_COMMAND", "clamscan").strip() or "clamscan"
    executable = shutil.which(configured)
    if executable is None:
        return UploadScanResult(
            allowed=False,
            engine="clamav",
            rule_id="clamav-unavailable",
            reason="ClamAV chưa được cài đặt hoặc không có trong PATH.",
        )
    timeout_seconds = int(os.getenv("CLAMAV_TIMEOUT_SECONDS", "20"))
    database_path = os.getenv("CLAMAV_DATABASE_PATH", "").strip()
    safe_name = Path(filename).name or "upload.bin"
    try:
        with tempfile.TemporaryDirectory(prefix="shield-av-") as directory:
            target = Path(directory) / safe_name
            target.write_bytes(content)
            command = [executable, "--no-summary", "--infected"]
            if database_path:
                command.append(f"--database={database_path}")
            command.append(str(target))
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                shell=False,
            )
    except (OSError, subprocess.SubprocessError, ValueError):
        return UploadScanResult(
            allowed=False,
            engine="clamav",
            rule_id="clamav-error",
            reason="ClamAV không thể hoàn tất kiểm tra tệp.",
        )
    if completed.returncode == 0:
        return UploadScanResult(allowed=True, engine="clamav")
    if completed.returncode == 1:
        return UploadScanResult(
            allowed=False,
            engine="clamav",
            rule_id="clamav-signature-detected",
            reason="ClamAV phát hiện chữ ký mã độc; tệp không được lưu.",
        )
    return UploadScanResult(
        allowed=False,
        engine="clamav",
        rule_id="clamav-error",
        reason="ClamAV trả về lỗi khi kiểm tra tệp.",
    )
