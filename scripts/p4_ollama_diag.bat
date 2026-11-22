@echo off
cd /d "%~dp0\.."
set OUT=logs\p4-check
set OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe
echo diag %date% %time% > %OUT%\diag.txt
"%OLLAMA%" --version >> %OUT%\diag.txt 2>&1
set OLLAMA >> %OUT%\diag.txt 2>&1
tasklist /fi "imagename eq ollama*" >> %OUT%\diag.txt 2>&1
netstat -ano -p tcp | findstr LISTENING >> %OUT%\diag.txt 2>&1
echo --- curl 127.0.0.1 >> %OUT%\diag.txt
curl -s -m 5 http://127.0.0.1:11434/api/version >> %OUT%\diag.txt 2>&1
echo. >> %OUT%\diag.txt
echo --- curl localhost >> %OUT%\diag.txt
curl -s -m 5 http://localhost:11434/api/version >> %OUT%\diag.txt 2>&1
echo. >> %OUT%\diag.txt
echo --- curl ::1 >> %OUT%\diag.txt
curl -s -m 5 http://[::1]:11434/api/version >> %OUT%\diag.txt 2>&1
echo. >> %OUT%\diag.txt
echo done >> %OUT%\diag.txt
