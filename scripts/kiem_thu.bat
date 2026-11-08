@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0.."
echo Kiem thu se dung lai CSDL assessment_db. Sau khi xong chay scripts\tao_du_lieu_demo.bat de co lai du lieu demo.
pause
".venv\Scripts\python.exe" "tools\kiem_thu\chay_kiem_thu_toan_bo.py" --omr
if errorlevel 1 (echo Co ca kiem thu khong dat.) else (echo Tat ca ca kiem thu dat.)
if exist "docs\kiem_thu\KET_QUA_KIEM_THU.xlsx" start "" "docs\kiem_thu\KET_QUA_KIEM_THU.xlsx"
pause
