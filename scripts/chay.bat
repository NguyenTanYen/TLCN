@echo off
chcp 65001 >nul
set PYTHONUTF8=1
title He thong phan tich CDR
call "%~dp0cau_hinh.bat"
cd /d "%ROOT%\backend"
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:"127.0.0.1:%APP_PORT% .*LISTENING"') do taskkill /F /PID %%p >nul 2>&1
echo He thong chay tai http://localhost:%APP_PORT% - giu cua so nay khi dang dung.
start "" "http://localhost:%APP_PORT%"
"..\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port %APP_PORT%
pause
