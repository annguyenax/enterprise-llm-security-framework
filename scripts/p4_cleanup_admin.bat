@echo off
REM Run with right-click > "Run as administrator".
REM Removes the stale .pytest-tmp folder owned by the Codex sandbox account
REM (MSI\CodexSandboxOffline), which normal users cannot delete.
cd /d "%~dp0\.."
if not exist .pytest-tmp (echo .pytest-tmp not present & pause & exit /b 0)
takeown /f .pytest-tmp /r /d y > nul
icacls .pytest-tmp /grant "%USERNAME%":(OI)(CI)F /T /C /Q
rmdir /s /q .pytest-tmp
if exist .pytest-tmp (echo FAILED: .pytest-tmp still present) else (echo OK: .pytest-tmp removed)
pause
