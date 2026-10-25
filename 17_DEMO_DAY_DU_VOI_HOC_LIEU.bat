@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
if not exist logs mkdir logs
set "LOG=%~dp0logs\demo_day_du.log"
echo [%date% %time%] BAT DAU > "%LOG%"
call 0_CAU_HINH.bat
rem 1) Tat he thong dang chay nen
taskkill /F /T /FI "WINDOWTITLE eq HE THONG PHAN TICH CDR*" >nul 2>&1
taskkill /F /T /FI "WINDOWTITLE eq he_thong*" >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like '*3. TLCN*HeThong*.venv*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
ping -n 4 127.0.0.1 >nul
cd backend
rem 2) Tao du lieu demo that tren Moodle (CSDL + khoa hoc + sinh vien lam bai + cham diem + phan tich)
echo --- Demo that tren Moodle >> "%LOG%"
"..\.venv\Scripts\python.exe" -u "..\tools\moodle_e2e\run_real_moodle_e2e.py" "%MOODLE_DIR%" >> "%LOG%" 2>&1
echo [%date% %time%] E2E ket thuc ma %errorlevel% >> "%LOG%"
findstr /b /c:"DEMO_MODE" cau_hinh.env >nul 2>&1 || (echo.>>cau_hinh.env & echo DEMO_MODE=true>>cau_hinh.env)
rem 3) Nap hoc lieu (neu chua co), tao goi y doc, day len Moodle
echo --- Hoc lieu + goi y doc >> "%LOG%"
"..\.venv\Scripts\python.exe" -u "..\tools\demo\nap_hoc_lieu_mau.py" --moodle >> "%LOG%" 2>&1
echo [%date% %time%] XONG >> "%LOG%"
cd ..
if not exist logs mkdir logs
del /q "logs\he_thong.log" >nul 2>&1
start "he_thong" /min cmd /c 5b_CHAY_NEN_TU_KHOI_LAI.bat
