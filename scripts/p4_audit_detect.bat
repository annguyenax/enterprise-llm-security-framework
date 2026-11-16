@echo off
cd /d "%~dp0\.."
set OUT=logs\p4-audit
if not exist %OUT% mkdir %OUT%
echo detect %date% %time% > %OUT%\detect.txt
for %%c in (grok gemini codex claude) do (
  echo ==== %%c >> %OUT%\detect.txt
  where %%c >> %OUT%\detect.txt 2>&1
)
echo ==== grok --help >> %OUT%\detect.txt
call grok --help >> %OUT%\detect.txt 2>&1
echo ==== gemini --help >> %OUT%\detect.txt
call gemini --help >> %OUT%\detect.txt 2>&1
echo ==== node >> %OUT%\detect.txt
node --version >> %OUT%\detect.txt 2>&1
echo done >> %OUT%\detect.txt
