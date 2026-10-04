@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "%~dp0backend\cau_hinh.env" copy /y "%~dp0backend\cau_hinh.env.example" "%~dp0backend\cau_hinh.env" >nul
echo [1/2] Tao moi truong ao Python (.venv)...
where py >nul 2>nul
if %errorlevel%==0 (py -3 -m venv .venv) else (python -m venv .venv)
if not exist ".venv\Scripts\python.exe" (
  echo Khong tim thay Python. Hay cai Python 3.10+ tu https://www.python.org va tick "Add python.exe to PATH".
  pause & exit /b 1
)
echo [2/2] Cai thu vien (FastAPI, SQLAlchemy, Pandas, openpyxl...)...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt || (echo *** Loi cai thu vien - kiem tra ket noi mang roi chay lai. & pause & exit /b 1)
echo.
echo Xong. Tiep theo chay 2_KHOI_TAO_CSDL.bat
pause
