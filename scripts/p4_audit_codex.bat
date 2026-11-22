@echo off
REM Code X (Codex CLI) read-only artifact-integrity audit only.
cd /d "%~dp0\.."
set OUT=logs\p4-audit
if not exist %OUT% mkdir %OUT%
echo codex-audit %date% %time% > %OUT%\codex_status.txt
for /f %%i in ('git rev-parse --short HEAD') do echo commit %%i >> %OUT%\codex_status.txt
codex exec --sandbox read-only -m gpt-6-luna --output-last-message %OUT%\codex-integrity.md - < docs\p4-claude-sql\audit\prompt-codex-integrity.md > %OUT%\codex-integrity.log 2>&1
echo codex exit %errorlevel% >> %OUT%\codex_status.txt
