# Workspace upload security

`POST /v1/documents` applies controls in this order:

1. request size and extension allowlist;
2. `app.services.upload_scanner` on the original bytes;
3. optional local ClamAV signature scan;
4. text/PDF parsing;
5. RAG Context Guard inspection;
6. persistence only after every required stage allows the upload.

The built-in upload scanner rejects executable magic bytes even when a file
is renamed to an allowed extension, binary/NUL content disguised as text,
active HTML/PDF content, and high-confidence destructive, encoded/dynamic,
download-and-execute, or credential-tampering commands. Benign source and
automation scripts are accepted and reported as `system-code`; the mere use
of a process API is not treated as malicious. A rejection returns HTTP 422
and happens before parsing and storage. Any RAG Guard `SANITIZE`, `BLOCK`, or
`HUMAN_REVIEW` result also rejects the entire upload: unsafe files are never
partially rewritten and stored.

The ClamAV adapter writes bytes only to an isolated temporary directory, invokes
the local executable without a command shell, and removes the temporary file
after scanning. `UPLOAD_ANTIVIRUS_MODE=required` fails closed if ClamAV is absent
or errors. `optional` preserves local development availability but reports the
antivirus stage as `unavailable`; `off` reports it as `disabled`. No uploaded
bytes are included in the security report.

The built-in rules remain deterministic heuristics for this lab-scale
proof-of-concept. ClamAV is signature scanning, not behavioral detonation. A
full execution sandbox is not included and files are never executed by this
application.

The upload response (including HTTP 422 responses) includes `security_report`
with the stage, engine, decision, matched rule IDs and human-readable reasons.
The chat upload bubble renders these details directly.

Run the focused verification with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_upload_scanner.py tests\test_workspace_file_parsing.py -q --basetemp=.pytest-tmp\upload-security
```
