@echo off
cd /d "%~dp0\.."
set PYTHONUTF8=1
set OUT=logs\p4-check
if not exist %OUT% mkdir %OUT%
echo verify-started %date% %time% > %OUT%\verify_status.txt
for /f %%i in ('git rev-parse --short HEAD') do echo commit %%i >> %OUT%\verify_status.txt
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify_phase.ps1 > %OUT%\verify_phase.txt 2>&1
echo verify exit %errorlevel% >> %OUT%\verify_status.txt
echo done %date% %time% >> %OUT%\verify_status.txt
