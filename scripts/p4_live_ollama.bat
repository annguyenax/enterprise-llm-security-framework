@echo off
REM P4 live smoke against local Ollama only (free). Pulls the model if missing.
cd /d "%~dp0\.."
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set OUT=logs\p4-check
set OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe
if not exist %OUT% mkdir %OUT%
echo live-started %date% %time% > %OUT%\live_status.txt
if not exist "%OLLAMA%" (echo ollama-not-installed >> %OUT%\live_status.txt & goto :end)
REM The project provider only talks to 127.0.0.1. If the user's OLLAMA_HOST points
REM elsewhere (e.g. a LAN IP), start a second server bound to loopback for this run.
curl -s -m 5 http://127.0.0.1:11434/api/tags > nul 2>&1
if errorlevel 1 (
  echo starting loopback ollama serve >> %OUT%\live_status.txt
  start "ollama-loopback" /min cmd /c "set OLLAMA_HOST=127.0.0.1:11434&& "%OLLAMA%" serve"
  timeout /t 15 /nobreak > nul
)
curl -s -m 5 http://127.0.0.1:11434/api/version >> %OUT%\live_status.txt 2>&1
echo. >> %OUT%\live_status.txt
set OLLAMA_HOST=127.0.0.1:11434
"%OLLAMA%" list > %OUT%\ollama_list.txt 2>&1
findstr /c:"qwen3:4b-instruct" %OUT%\ollama_list.txt > nul
if errorlevel 1 (
  echo pulling qwen3:4b-instruct >> %OUT%\live_status.txt
  "%OLLAMA%" pull qwen3:4b-instruct > %OUT%\ollama_pull.txt 2>&1
  echo pull exit %errorlevel% >> %OUT%\live_status.txt
)
"%OLLAMA%" list > %OUT%\ollama_list.txt 2>&1
.venv\Scripts\python.exe scripts\p4_live_smoke.py --provider ollama --repeat 3 %* > %OUT%\live_smoke.txt 2>&1
echo live exit %errorlevel% >> %OUT%\live_status.txt
:end
echo done %date% %time% >> %OUT%\live_status.txt
echo Finished. You can close this window.
