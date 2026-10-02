@echo off
chcp 65001 >nul
title HE THONG PHAN TICH CDR - KHONG DONG CUA SO NAY
set PYTHONUTF8=1
cd /d "%~dp0"
call 0_CAU_HINH.bat
cd backend
rem Tat ban he thong cu con chay ngam (cua so da dong nhung tien trinh van giu cong) de ban moi khoi dong duoc
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:"127.0.0.1:%APP_PORT% .*LISTENING"') do (
  echo Tat tien trinh cu dang giu cong %APP_PORT% ^(PID %%p^)...
  taskkill /F /PID %%p >nul 2>&1
)
echo ================================================================
echo  He thong phan tich CDR dang chay tai http://localhost:%APP_PORT%
echo  KHONG DONG cua so nay khi dang dung (dong = tat he thong,
echo  nut "Phan tich CDR" tren Moodle se khong vao duoc).
echo  Co the thu nho cua so xuong thanh tac vu.
echo ================================================================
start "" "http://localhost:%APP_PORT%"
"..\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port %APP_PORT%
echo.
echo He thong da dung. Chay lai 5_CHAY_HE_THONG.bat de bat lai.
pause
