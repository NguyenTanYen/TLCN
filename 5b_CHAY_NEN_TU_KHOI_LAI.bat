@echo off
chcp 65001 >nul
title HE THONG PHAN TICH CDR (chay nen, tu khoi dong lai khi loi)
set PYTHONUTF8=1
cd /d "%~dp0"
call 0_CAU_HINH.bat
cd backend
if not exist "..\logs" mkdir "..\logs"
rem Tat ban cu dang giu cong (neu co)
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:"127.0.0.1:%APP_PORT% .*LISTENING"') do taskkill /F /PID %%p >nul 2>&1
:lap
echo [%date% %time%] Khoi dong he thong tai http://localhost:%APP_PORT% >> "..\logs\he_thong.log"
"..\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port %APP_PORT% >> "..\logs\he_thong.log" 2>&1
echo [%date% %time%] He thong dung, tu khoi dong lai sau 5 giay >> "..\logs\he_thong.log"
timeout /t 5 /nobreak >nul
goto lap
