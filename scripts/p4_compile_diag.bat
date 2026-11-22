@echo off
cd /d "%~dp0\.."
set OUT=logs\p4-check
echo compile-diag %date% %time% > %OUT%\compile_diag.txt
.venv\Scripts\python.exe -m py_compile scripts\seed_enterprise_knowledge_base.py >> %OUT%\compile_diag.txt 2>&1
echo py_compile exit %errorlevel% >> %OUT%\compile_diag.txt
icacls scripts\__pycache__ >> %OUT%\compile_diag.txt 2>&1
dir /q scripts\__pycache__\seed_enterprise_knowledge_base* >> %OUT%\compile_diag.txt 2>&1
dir /q /a .pytest-tmp >> %OUT%\compile_diag.txt 2>&1
whoami >> %OUT%\compile_diag.txt 2>&1
