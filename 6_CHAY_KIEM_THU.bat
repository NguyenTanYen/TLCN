@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
echo ================================================================
echo  KIEM THU TOAN BO CHUC NANG: 129 ca kiem thu tu dong, do phu 147/148 API,
echo  do ben bo cham phieu (OMR) va bang ket qua Excel
echo  (docs\kiem_thu\KET_QUA_KIEM_THU.xlsx - co ca sheet kiem thu giao dien).
echo  LUU Y: kiem thu DUNG LAI CSDL assessment_db va tao CSDL moodle_sim rieng.
echo        Chay xong, hay chay lai 4_TAO_DU_LIEU_DEMO_TREN_MOODLE.bat de co lai du lieu demo.
echo ================================================================
pause
".venv\Scripts\python.exe" "tools\kiem_thu\chay_kiem_thu_toan_bo.py" --omr
if errorlevel 1 (echo. & echo *** CO CA KIEM THU KHONG DAT - xem bang ket qua) else (echo. & echo Tat ca cac ca kiem thu DAT.)
if exist "docs\kiem_thu\KET_QUA_KIEM_THU.xlsx" start "" "docs\kiem_thu\KET_QUA_KIEM_THU.xlsx"
echo Nho chay lai 4_TAO_DU_LIEU_DEMO_TREN_MOODLE.bat de khoi phuc du lieu demo truoc khi trinh bay.
pause
