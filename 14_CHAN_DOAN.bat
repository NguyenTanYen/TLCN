@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
if not exist logs mkdir logs
".venv\Scripts\python.exe" "tools\chan_doan.py" > "logs\chan_doan.log" 2>&1
echo XONG >> "logs\chan_doan.log"
