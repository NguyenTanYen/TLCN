@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
if not exist logs mkdir logs
set "LOG=%~dp0logs\chay_tu_dong.log"
echo [%date% %time%] BAT DAU > "%LOG%"
call 0_CAU_HINH.bat
echo MOODLE_DIR=%MOODLE_DIR% PHP_BIN=%PHP_BIN% PORT=%APP_PORT% >> "%LOG%"
rem 1) Nang cap plugin local_clo len 1.5.0 + xoa bo nho dem Moodle
if defined MOODLE_DIR if defined PHP_BIN (
  echo --- Nang cap Moodle >> "%LOG%"
  "%PHP_BIN%" "%MOODLE_DIR%\admin\cli\upgrade.php" --non-interactive >> "%LOG%" 2>&1
  "%PHP_BIN%" "%MOODLE_DIR%\admin\cli\purge_caches.php" >> "%LOG%" 2>&1
)
rem 2) Khoi dong lai he thong (chay nen)
echo --- Khoi dong lai he thong >> "%LOG%"
start "he_thong" /min cmd /c 5b_CHAY_NEN_TU_KHOI_LAI.bat
ping -n 25 127.0.0.1 >nul
rem 3) Nap hoc lieu mau, tao goi y doc, day len Moodle
echo --- Nap hoc lieu + day len Moodle >> "%LOG%"
cd backend
"..\.venv\Scripts\python.exe" -c "import pymupdf, pptx, docx" 2>>"%LOG%" || "..\.venv\Scripts\python.exe" -m pip install -q pymupdf python-pptx python-docx >> "%LOG%" 2>&1
"..\.venv\Scripts\python.exe" "..\tools\demo\nap_hoc_lieu_mau.py" --moodle >> "%LOG%" 2>&1
echo [%date% %time%] XONG >> "%LOG%"
