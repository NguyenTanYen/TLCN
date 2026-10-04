@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0backend"
echo Chay 73 ca kiem thu tu dong (se DUNG LAI CSDL assessment_db va tao CSDL moodle_sim rieng)...
pause
"..\.venv\Scripts\python.exe" -m pytest tests -q
pause
