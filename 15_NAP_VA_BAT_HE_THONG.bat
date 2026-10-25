@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
if not exist logs mkdir logs
set "LOG=%~dp0logs\nap_hoc_lieu.log"
echo [%date% %time%] BAT DAU > "%LOG%"
call 0_CAU_HINH.bat
cd backend
"..\.venv\Scripts\python.exe" -c "import pymupdf, pptx, docx" >> "%LOG%" 2>&1 || "..\.venv\Scripts\python.exe" -m pip install -q pymupdf python-pptx python-docx >> "%LOG%" 2>&1
echo --- Nap hoc lieu (khong day Moodle) >> "%LOG%"
"..\.venv\Scripts\python.exe" -u "..\tools\demo\nap_hoc_lieu_mau.py" >> "%LOG%" 2>&1
echo --- Day hoc lieu + ket qua len Moodle >> "%LOG%"
"..\.venv\Scripts\python.exe" -u "..\tools\demo\nap_hoc_lieu_mau.py" --moodle >> "%LOG%" 2>&1
echo [%date% %time%] XONG NAP >> "%LOG%"
cd ..
