@echo off
REM P4 Windows check: canonical verify_phase evidence + live smoke on local Ollama.
REM Writes everything to logs\p4-check\ (gitignored). No paid API is called.
cd /d "%~dp0\.."
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set OUT=logs\p4-check
if not exist %OUT% mkdir %OUT%
echo started %date% %time% > %OUT%\status.txt
for /f %%i in ('git rev-parse --short HEAD') do echo commit %%i >> %OUT%\status.txt
echo [1/4] build furniture db
.venv\Scripts\python.exe scripts\build_furniture_db.py --out data\furniture.db --force > %OUT%\build_db.txt 2>&1
echo build exit %errorlevel% >> %OUT%\status.txt
echo [1b] remove stale .pytest-tmp (user-approved cleanup)
if exist .pytest-tmp icacls .pytest-tmp /grant "%USERNAME%":(OI)(CI)F /T /C /Q > %OUT%\cleanup.txt 2>&1
if exist .pytest-tmp rmdir /s /q .pytest-tmp >> %OUT%\cleanup.txt 2>&1
if exist .pytest-tmp (echo pytest-tmp still present >> %OUT%\status.txt) else (echo pytest-tmp removed >> %OUT%\status.txt)
echo [2/4] verify_phase (full test suite)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify_phase.ps1 > %OUT%\verify_phase.txt 2>&1
echo verify exit %errorlevel% >> %OUT%\status.txt
echo [3/4] live smoke on local Ollama (see p4_live_ollama.bat)
call scripts\p4_live_ollama.bat
echo done %date% %time% >> %OUT%\status.txt
echo Finished. You can close this window.
