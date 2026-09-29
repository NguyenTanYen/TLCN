@echo off
chcp 65001 >nul
title HE THONG PHAN TICH CDR - KHONG DONG CUA SO NAY
set PYTHONUTF8=1
cd /d "%~dp0"
call 0_CAU_HINH.bat
cd backend
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
