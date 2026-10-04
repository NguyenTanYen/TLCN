@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0..\backend"
echo Xuat CSDL assessment_db (cau truc + du lieu + view + thu tuc) ra thu muc NopBai\SQL (canh thu muc HeThong) ...
"..\.venv\Scripts\python.exe" "..\tools\xuat_sql.py" "%~dp0..\..\NopBai\SQL"
pause
