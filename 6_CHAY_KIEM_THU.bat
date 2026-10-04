@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0backend"
echo Chay 77 ca kiem thu tu dong (se DUNG LAI CSDL assessment_db va tao CSDL moodle_sim rieng)...
echo LUU Y: du lieu demo trong assessment_db se bi thay bang du lieu kiem thu.
echo        Chay xong, hay chay lai 4_TAO_DU_LIEU_DEMO_TREN_MOODLE.bat de co lai du lieu demo.
pause
"..\.venv\Scripts\python.exe" -m pytest tests -q
echo.
echo Nho chay lai 4_TAO_DU_LIEU_DEMO_TREN_MOODLE.bat de khoi phuc du lieu demo truoc khi trinh bay.
pause
