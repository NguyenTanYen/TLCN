@echo off
chcp 65001 >nul
set PYTHONUTF8=1
call "%~dp0cau_hinh.bat"
if not defined MOODLE_DIR (echo Chua xac dinh Moodle 4.5 - xem scripts\cau_hinh_may.example.bat & pause & exit /b 1)
cd /d "%ROOT%\backend"
set "PY=..\.venv\Scripts\python.exe"
"%PY%" -c "import pymupdf" 2>nul || "%PY%" -m pip install -q pymupdf
"%PY%" "..\tools\moodle_e2e\run_real_moodle_e2e.py" "%MOODLE_DIR%" || (echo *** Loi tao du lieu demo. & pause & exit /b 1)
findstr /b /c:"DEMO_MODE" cau_hinh.env >nul 2>&1 || (echo.>>cau_hinh.env & echo DEMO_MODE=true>>cau_hinh.env)
echo Xong. Khoi dong lai scripts\chay.bat de ap dung.
pause
