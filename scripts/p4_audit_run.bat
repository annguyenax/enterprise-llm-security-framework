@echo off
REM Independent read-only audits via local CLIs (Grok = security, Codex = artifact integrity).
cd /d "%~dp0\.."
set OUT=logs\p4-audit
if not exist %OUT% mkdir %OUT%
echo audit-started %date% %time% > %OUT%\status.txt
for /f %%i in ('git rev-parse --short HEAD') do echo commit %%i >> %OUT%\status.txt
start "grok-audit" /min cmd /c "call grok --prompt-file docs\p4-claude-sql\audit\prompt-grok-security.md --permission-mode plan --disable-web-search --no-subagents --max-turns 60 --output-format plain > %OUT%\grok-security.md 2> %OUT%\grok-security.err & echo grok exit %%errorlevel%% >> %OUT%\status.txt"
start "codex-audit" /min cmd /c "codex exec --sandbox read-only -m gpt-6-luna --output-last-message %OUT%\codex-integrity.md - < docs\p4-claude-sql\audit\prompt-codex-integrity.md > %OUT%\codex-integrity.log 2>&1 & echo codex exit %%errorlevel%% >> %OUT%\status.txt"
echo launched >> %OUT%\status.txt
